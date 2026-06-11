"""
PulseDebug AI — AI Analysis API Router
=========================================
File: backend/app/api/ai_analysis.py
Purpose:
    AI analysis endpoint with confidence scoring, fix command generation,
    and deployment regression detection.
    Updated to use database.execute(), fetchone(), fetchall() helpers
    for PostgreSQL and SQLite compatibility.

Author: PulseDebug AI Hackathon Team
"""

import json
import re
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from app.core.database import get_connection, execute, fetchone, fetchall, commit
from app.services.ai_service import analyse_incident, ai_status, run_analyzer_prompt
from app.services.timeline import add_timeline_event

router = APIRouter()

CONFIDENCE_MAP = {
    "High Likelihood":     0.85,
    "Moderate Likelihood": 0.60,
    "Needs Investigation": 0.35,
    "Not Related":         0.15,
}

FIX_COMMANDS_PROMPT = """You are PulseDebug AI, a senior SRE reliability engineer.
Based on this incident, generate concrete implementation fix commands.
Return a JSON array with objects having these exact keys:

[
  {{
    "language": "python",
    "title": "short title",
    "code": "actual runnable code here"
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


def _build_logs_summary(conn, service, endpoint, first_ts, last_ts) -> dict:
    row = fetchone(
        execute(conn,
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_anomaly=1 THEN 1 ELSE 0 END) as anomalies,
                   AVG(latency_ms) as avg_latency,
                   MAX(latency_ms) as max_latency,
                   SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) as server_errors,
                   SUM(CASE WHEN status_code>=400 AND status_code<500 THEN 1 ELSE 0 END) as client_errors
            FROM api_logs
            WHERE service=? AND endpoint=? AND timestamp BETWEEN ? AND ?
            """,
            (service, endpoint, first_ts, last_ts),
        )
    )
    if not row or not row["total"]:
        return {}
    total = row["total"]
    return {
        "total_events":   total,
        "anomaly_count":  row["anomalies"],
        "avg_latency_ms": round(row["avg_latency"] or 0, 1),
        "max_latency_ms": row["max_latency"] or 0,
        "server_errors":  row["server_errors"],
        "client_errors":  row["client_errors"],
        "error_rate":     round((row["server_errors"] + row["client_errors"]) / total, 3),
    }


def _detect_deployment_regression(conn, incident: dict) -> dict:
    if not incident.get("deployment_id"):
        return {}

    dep = fetchone(
        execute(conn, "SELECT * FROM deployments WHERE id = ?", (incident["deployment_id"],))
    )
    if not dep:
        return {}

    before = fetchone(
        execute(conn,
            """
            SELECT COUNT(*) as cnt FROM api_logs
            WHERE service = ? AND status_code >= 400
              AND timestamp < ?
              AND timestamp >= ?
            """,
            (incident["service"], dep["deployed_at"],
             (datetime.fromisoformat(dep["deployed_at"].replace("Z", "+00:00"))
              - timedelta(minutes=30)).isoformat()),
        )
    )

    after = fetchone(
        execute(conn,
            """
            SELECT COUNT(*) as cnt FROM api_logs
            WHERE service = ? AND status_code >= 400
              AND timestamp >= ?
              AND timestamp <= ?
            """,
            (incident["service"], dep["deployed_at"],
             (datetime.fromisoformat(dep["deployed_at"].replace("Z", "+00:00"))
              + timedelta(minutes=30)).isoformat()),
        )
    )

    before_count = before["cnt"] if before else 0
    after_count  = after["cnt"]  if after  else 0

    if before_count == 0 and after_count > 3:
        regression, increase_pct = True, 100.0
    elif before_count > 0:
        increase_pct = ((after_count - before_count) / before_count) * 100
        regression   = increase_pct > 100
    else:
        regression, increase_pct = False, 0.0

    return {
        "regression_detected": regression,
        "errors_before":       before_count,
        "errors_after":        after_count,
        "increase_pct":        round(increase_pct, 1),
        "deployment_version":  dep["version"],
        "deployed_at":         dep["deployed_at"],
    }


@router.post("/analyse/{incident_id}")
async def analyse(incident_id: int):
    conn = get_connection()
    try:
        row = fetchone(
            execute(conn, "SELECT * FROM incidents WHERE id = ?", (incident_id,))
        )
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        deployment = None
        if row.get("deployment_id"):
            dep = fetchone(
                execute(conn, "SELECT * FROM deployments WHERE id = ?", (row["deployment_id"],))
            )
            deployment = dep

        logs_summary    = _build_logs_summary(
            conn, row["service"], row["endpoint"],
            row["first_detected"], row["last_seen"],
        )
        regression_info = _detect_deployment_regression(conn, row)

        analysis, _ = await analyse_incident(row, logs_summary, deployment)

        if analysis:
            confidence  = CONFIDENCE_MAP.get(
                analysis.get("confidence_labels", {}).get("likely_cause", ""), 0.50
            )

            fix_commands = []
            try:
                fix_prompt = FIX_COMMANDS_PROMPT.format(
                    service=row["service"],
                    error_signature=row["error_signature"],
                    root_cause=analysis.get("likely_cause", ""),
                    priority=analysis.get("investigation_priority", "Medium"),
                )
                raw_fixes = await run_analyzer_prompt(fix_prompt)
                if raw_fixes:
                    cleaned      = re.sub(r"```(?:json)?", "", raw_fixes).strip().rstrip("`").strip()
                    fix_commands = json.loads(cleaned)
            except Exception:
                fix_commands = []

            execute(conn,
                """
                UPDATE incidents
                SET ai_summary=?, ai_root_cause=?, ai_checks=?,
                    ai_priority=?, ai_model_used='ai',
                    ai_confidence=?, ai_fix_commands=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    analysis.get("incident_summary"),
                    analysis.get("likely_cause"),
                    json.dumps(analysis.get("recommended_checks", [])),
                    analysis.get("investigation_priority"),
                    confidence,
                    json.dumps(fix_commands),
                    datetime.now(timezone.utc).isoformat(),
                    incident_id,
                ),
            )
            commit(conn)

            add_timeline_event(
                conn, incident_id,
                event_type="ai_analysis",
                title="AI analysis generated",
                detail=f"Priority: {analysis.get('investigation_priority')} — "
                       f"{analysis.get('likely_cause', '')[:80]}",
            )

            return {
                "incident_id":     incident_id,
                "model_used":      "gemini-2.5-flash",
                "analysis":        analysis,
                "ai_available":    True,
                "confidence_score": confidence,
                "fix_commands":    fix_commands,
                "regression_info": regression_info,
            }

        else:
            return {
                "incident_id":        incident_id,
                "model_used":         None,
                "analysis":           None,
                "ai_available":       False,
                "message":            "AI analysis is temporarily initialising.",
                "statistical_summary": logs_summary,
                "regression_info":    regression_info,
            }

    finally:
        conn.close()


@router.get("/status")
def get_ai_status():
    return ai_status()