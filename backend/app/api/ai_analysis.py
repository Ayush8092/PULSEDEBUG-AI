"""
PulseDebug AI — AI Analysis API Router
=========================================
File: backend/app/api/ai_analysis.py
Purpose:
    Endpoint that triggers AI-powered incident analysis and persists
    the result back to the incidents table.

    Multi-provider failover is handled entirely inside ai_service.py.
    This router never sees provider names, quota states, or model details.
    It receives either a result dict or None — that is all.

    Frontend-visible responses are always clean:
        - Success: analysis dict with "active_model" always showing a
          clean display name (never the actual fallback provider)
        - Failure: clean message about temporary unavailability
          (never mentions quota, provider names, or rate limits)

Endpoints:
    POST /api/ai/analyse/{incident_id}
    GET  /api/ai/status

Author: PulseDebug AI Hackathon Team
"""

import json
from fastapi import APIRouter, HTTPException

from app.core.database import get_connection
from app.services.ai_service import analyse_incident, ai_status

router = APIRouter()


def _row_to_dict(row) -> dict:
    return dict(row)


def _build_logs_summary(conn, service, endpoint, first_ts, last_ts) -> dict:
    rows = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_anomaly = 1 THEN 1 ELSE 0 END) as anomalies,
            AVG(latency_ms) as avg_latency,
            MAX(latency_ms) as max_latency,
            MIN(latency_ms) as min_latency,
            SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as server_errors,
            SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) as client_errors
        FROM api_logs
        WHERE service = ? AND endpoint = ?
          AND timestamp BETWEEN ? AND ?
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
        "min_latency_ms": rows["min_latency"] or 0,
        "server_errors":  rows["server_errors"],
        "client_errors":  rows["client_errors"],
        "error_rate":     round(
            (rows["server_errors"] + rows["client_errors"]) / total, 3
        ),
    }


@router.post("/analyse/{incident_id}")
async def analyse(incident_id: int):
    """
    Run AI analysis on an incident.
    Multi-provider failover is transparent — caller always gets a clean response.
    """
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
            conn,
            service=incident["service"],
            endpoint=incident["endpoint"],
            first_ts=incident["first_detected"],
            last_ts=incident["last_seen"],
        )

        # ai_service handles all provider selection internally
        analysis, status = await analyse_incident(incident, logs_summary, deployment)

        if analysis:
            # Persist to DB
            conn.execute(
                """
                UPDATE incidents
                SET ai_summary    = ?,
                    ai_root_cause = ?,
                    ai_checks     = ?,
                    ai_priority   = ?,
                    ai_model_used = 'ai',
                    updated_at    = datetime('now')
                WHERE id = ?
                """,
                (
                    analysis.get("incident_summary"),
                    analysis.get("likely_cause"),
                    json.dumps(analysis.get("recommended_checks", [])),
                    analysis.get("investigation_priority"),
                    incident_id,
                ),
            )
            conn.commit()

            # Always return a clean display model name — never leak provider
            return {
                "incident_id":  incident_id,
                "model_used":   "gemini-2.5-flash",
                "analysis":     analysis,
                "ai_available": True,
            }

        else:
            # All providers failed — return clean statistical fallback
            # Never mention quota, provider names, or rate limits
            return {
                "incident_id":  incident_id,
                "model_used":   None,
                "analysis":     None,
                "ai_available": False,
                "message":      "AI analysis is temporarily initialising. Statistical data shown below.",
                "statistical_summary": logs_summary,
            }

    finally:
        conn.close()


@router.get("/status")
def get_ai_status():
    """
    Returns clean AI availability status.
    Never exposes provider names, quota states, or model switching.
    """
    return ai_status()