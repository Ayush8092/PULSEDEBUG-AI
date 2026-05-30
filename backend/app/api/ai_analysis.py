"""
PulseDebug AI — AI Analysis API Router
=========================================
File: backend/app/api/ai_analysis.py
Purpose:
    AI analysis endpoint with upgrade additions:
        - AI confidence score computation and storage
        - AI-generated fix commands (code snippets)
        - Deployment regression detection
        - Timeline event creation on analysis completion

Author: PulseDebug AI Hackathon Team
"""

import json
from fastapi import APIRouter, HTTPException
from app.core.database import get_connection
from app.services.ai_service import analyse_incident, ai_status, run_analyzer_prompt
from app.services.timeline import add_timeline_event

router = APIRouter()

# Confidence score mapping from qualitative labels
CONFIDENCE_MAP = {
    "High Likelihood":     0.85,
    "Moderate Likelihood": 0.60,
    "Needs Investigation": 0.35,
    "Not Related":         0.15,
}

# Fix command generation prompt template
FIX_COMMANDS_PROMPT = """You are PulseDebug AI, a senior SRE reliability engineer.
Based on this incident, generate concrete implementation fix commands.
Return a JSON array with objects having these exact keys:

[
  {{
    "language": "python",
    "title": "Retry with exponential backoff",
    "code": "from tenacity import retry, wait_exponential\\n\\n@retry(wait=wait_exponential(min=1, max=10))\\ndef call_service():\\n    pass"
  }},
  {{
    "language": "yaml",
    "title": "Kubernetes timeout config",
    "code": "timeout: 5s\\nretries: 3\\nbackoff:\\n  baseDelay: 1s\\n  maxDelay: 10s"
  }}
]

Requirements:
- Generate 2-4 fix snippets relevant to the specific incident
- Each snippet must be immediately usable code
- Support: python, yaml, bash, javascript
- Return ONLY the JSON array — no markdown fences, no explanation

Incident:
Service: {service}
Error: {error_signature}
Root cause: {root_cause}
Priority: {priority}
"""


def _row_to_dict(row) -> dict:
    return dict(row)


def _build_logs_summary(conn, service, endpoint, first_ts, last_ts) -> dict:
    rows = conn.execute(
        """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN is_anomaly=1 THEN 1 ELSE 0 END) as anomalies,
               AVG(latency_ms) as avg_latency, MAX(latency_ms) as max_latency,
               SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) as server_errors,
               SUM(CASE WHEN status_code>=400 AND status_code<500 THEN 1 ELSE 0 END) as client_errors
        FROM api_logs
        WHERE service=? AND endpoint=? AND timestamp BETWEEN ? AND ?
        """,
        (service, endpoint, first_ts, last_ts),
    ).fetchone()

    if not rows or rows["total"] == 0:
        return {}

    total = rows["total"]
    return {
        "total_events":   total,
        "anomaly_count":  rows["anomalies"],
        "avg_latency_ms": round(rows["avg_latency"] or 0, 1),
        "max_latency_ms": rows["max_latency"] or 0,
        "server_errors":  rows["server_errors"],
        "client_errors":  rows["client_errors"],
        "error_rate":     round(
            (rows["server_errors"] + rows["client_errors"]) / total, 3
        ),
    }


def _detect_deployment_regression(conn, incident: dict) -> dict:
    """
    Check if incident occurred shortly after a deployment.
    Returns regression info if detected.
    """
    if not incident.get("deployment_id"):
        return {}

    dep = conn.execute(
        "SELECT * FROM deployments WHERE id = ?",
        (incident["deployment_id"],)
    ).fetchone()

    if not dep:
        return {}

    # Count errors before and after deployment
    before = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM api_logs
        WHERE service = ? AND status_code >= 400
          AND timestamp < ?
          AND timestamp >= datetime(?, '-30 minutes')
        """,
        (incident["service"], dep["deployed_at"], dep["deployed_at"]),
    ).fetchone()

    after = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM api_logs
        WHERE service = ? AND status_code >= 400
          AND timestamp >= ?
          AND timestamp <= datetime(?, '+30 minutes')
        """,
        (incident["service"], dep["deployed_at"], dep["deployed_at"]),
    ).fetchone()

    before_count = before["cnt"] if before else 0
    after_count  = after["cnt"]  if after  else 0

    if before_count == 0 and after_count > 3:
        regression = True
        increase_pct = 100.0
    elif before_count > 0:
        increase_pct = ((after_count - before_count) / before_count) * 100
        regression = increase_pct > 100
    else:
        regression = False
        increase_pct = 0

    return {
        "regression_detected": regression,
        "errors_before":       before_count,
        "errors_after":        after_count,
        "increase_pct":        round(increase_pct, 1),
        "deployment_version":  dep["version"],
        "deployment_service":  dep["service"],
        "deployed_at":         dep["deployed_at"],
    }


@router.post("/analyse/{incident_id}")
async def analyse(incident_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        incident = _row_to_dict(row)

        deployment = None
        if incident.get("deployment_id"):
            dep_row = conn.execute(
                "SELECT * FROM deployments WHERE id = ?",
                (incident["deployment_id"],)
            ).fetchone()
            deployment = _row_to_dict(dep_row) if dep_row else None

        logs_summary = _build_logs_summary(
            conn, incident["service"], incident["endpoint"],
            incident["first_detected"], incident["last_seen"],
        )

        # Detect deployment regression
        regression_info = _detect_deployment_regression(conn, incident)

        # Run AI analysis
        analysis, _ = await analyse_incident(incident, logs_summary, deployment)

        if analysis:
            # Compute confidence score
            confidence = CONFIDENCE_MAP.get(
                analysis.get("confidence_labels", {}).get("likely_cause", ""),
                0.50
            )

            # Generate fix commands
            fix_commands = []
            try:
                fix_prompt = FIX_COMMANDS_PROMPT.format(
                    service=incident["service"],
                    error_signature=incident["error_signature"],
                    root_cause=analysis.get("likely_cause", ""),
                    priority=analysis.get("investigation_priority", "Medium"),
                )
                raw_fixes = await run_analyzer_prompt(fix_prompt)
                if raw_fixes:
                    import re
                    cleaned = re.sub(r"```(?:json)?", "", raw_fixes).strip().rstrip("`").strip()
                    fix_commands = json.loads(cleaned)
            except Exception:
                fix_commands = []

            # Persist everything
            conn.execute(
                """
                UPDATE incidents
                SET ai_summary=?, ai_root_cause=?, ai_checks=?,
                    ai_priority=?, ai_model_used='ai',
                    ai_confidence=?, ai_fix_commands=?,
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (
                    analysis.get("incident_summary"),
                    analysis.get("likely_cause"),
                    json.dumps(analysis.get("recommended_checks", [])),
                    analysis.get("investigation_priority"),
                    confidence,
                    json.dumps(fix_commands),
                    incident_id,
                ),
            )
            conn.commit()

            # Add timeline event
            add_timeline_event(
                conn, incident_id,
                event_type="ai_analysis",
                title="AI analysis generated",
                detail=f"Priority: {analysis.get('investigation_priority')} — {analysis.get('likely_cause', '')[:80]}",
            )

            return {
                "incident_id":        incident_id,
                "model_used":         "gemini-2.5-flash",
                "analysis":           analysis,
                "ai_available":       True,
                "confidence_score":   confidence,
                "fix_commands":       fix_commands,
                "regression_info":    regression_info,
            }

        else:
            return {
                "incident_id":        incident_id,
                "model_used":         None,
                "analysis":           None,
                "ai_available":       False,
                "message":            "AI analysis is temporarily initialising. Statistical data shown below.",
                "statistical_summary": logs_summary,
                "regression_info":    regression_info,
            }

    finally:
        conn.close()


@router.get("/status")
def get_ai_status():
    return ai_status()