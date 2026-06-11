"""
PulseDebug AI — Health & Status Router
=========================================
File: backend/app/api/health.py
Purpose:
    Health check and system status.
    Updated to use database.execute() and database.fetchone()
    so it works identically with both SQLite and PostgreSQL.

Author: PulseDebug AI Hackathon Team
"""

from fastapi import APIRouter
from app.core.database import get_connection, execute, fetchone
from app.services.ai_service import ai_status

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "PulseDebug AI"}


@router.get("/status")
def system_status():
    conn = get_connection()
    try:
        total_requests = fetchone(
            execute(conn, "SELECT COUNT(*) as cnt FROM api_logs")
        )["cnt"]

        failed_requests = fetchone(
            execute(conn, "SELECT COUNT(*) as cnt FROM api_logs WHERE status_code >= 400")
        )["cnt"]

        avg_row = fetchone(
            execute(conn, "SELECT AVG(latency_ms) as avg FROM api_logs")
        )
        avg_latency = avg_row["avg"] or 0

        active_incidents = fetchone(
            execute(conn, "SELECT COUNT(*) as cnt FROM incidents WHERE status = 'open'")
        )["cnt"]

        critical_incidents = fetchone(
            execute(conn,
                "SELECT COUNT(*) as cnt FROM incidents WHERE status='open' AND severity='critical'"
            )
        )["cnt"]

        external_incidents = fetchone(
            execute(conn,
                "SELECT COUNT(*) as cnt FROM incidents WHERE status='open' AND source='external'"
            )
        )["cnt"]

        return {
            "total_requests":     total_requests,
            "failed_requests":    failed_requests,
            "avg_latency_ms":     round(avg_latency, 1),
            "active_incidents":   active_incidents,
            "critical_incidents": critical_incidents,
            "external_incidents": external_incidents,
            "error_rate":         round(failed_requests / max(total_requests, 1), 4),
            "ai":                 ai_status(),
        }
    finally:
        conn.close()