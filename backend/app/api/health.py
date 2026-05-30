"""
PulseDebug AI — Health & Status Router
=========================================
File: backend/app/api/health.py
Purpose:
    Health check and system status endpoints.
    Updated to include external incident count in status.

Author: PulseDebug AI Hackathon Team
"""

from fastapi import APIRouter
from app.core.database import get_connection
from app.services.ai_service import ai_status

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "PulseDebug AI"}


@router.get("/status")
def system_status():
    conn = get_connection()
    try:
        total_requests = conn.execute(
            "SELECT COUNT(*) FROM api_logs"
        ).fetchone()[0]

        failed_requests = conn.execute(
            "SELECT COUNT(*) FROM api_logs WHERE status_code >= 400"
        ).fetchone()[0]

        avg_latency = conn.execute(
            "SELECT AVG(latency_ms) FROM api_logs"
        ).fetchone()[0] or 0

        active_incidents = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE status = 'open'"
        ).fetchone()[0]

        critical_incidents = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE status='open' AND severity='critical'"
        ).fetchone()[0]

        external_incidents = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE status='open' AND source='external'"
        ).fetchone()[0]

        return {
            "total_requests":      total_requests,
            "failed_requests":     failed_requests,
            "avg_latency_ms":      round(avg_latency, 1),
            "active_incidents":    active_incidents,
            "critical_incidents":  critical_incidents,
            "external_incidents":  external_incidents,
            "error_rate":          round(failed_requests / max(total_requests, 1), 4),
            "ai":                  ai_status(),
        }
    finally:
        conn.close()