"""
PulseDebug AI — Deployments API Router
=========================================
File: backend/app/api/deployments.py
Purpose:
    Endpoints for deployment event records.
    The dashboard uses these to show the deployment timeline and to
    highlight which incidents correlate with a specific deploy.

Endpoints:
    GET  /api/deployments          — list all deployment events
    GET  /api/deployments/recent   — last N deployments
    GET  /api/deployments/{id}     — single deployment detail with linked incidents

Author: PulseDebug AI Hackathon Team
"""

from fastapi import APIRouter, HTTPException, Query

from app.core.database import get_connection

router = APIRouter()


def _row_to_dict(row) -> dict:
    return dict(row)


@router.get("")
def list_deployments(limit: int = Query(20, ge=1, le=100)):
    """Return all deployment events, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM deployments ORDER BY deployed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/recent")
def recent_deployments(limit: int = Query(5, ge=1, le=20)):
    """Return the N most recent deployments — used in the timeline widget."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM deployments ORDER BY deployed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            d = _row_to_dict(r)
            incident_count = conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE deployment_id = ?",
                (d["id"],),
            ).fetchone()[0]
            d["linked_incident_count"] = incident_count
            result.append(d)
        return result
    finally:
        conn.close()


@router.get("/{deployment_id}")
def get_deployment(deployment_id: int):
    """Return a single deployment with linked incidents."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Deployment not found")

        d = _row_to_dict(row)
        incidents = conn.execute(
            "SELECT id, title, severity, status, occurrence_count FROM incidents "
            "WHERE deployment_id = ?",
            (deployment_id,),
        ).fetchall()
        d["incidents"] = [_row_to_dict(i) for i in incidents]
        return d
    finally:
        conn.close()