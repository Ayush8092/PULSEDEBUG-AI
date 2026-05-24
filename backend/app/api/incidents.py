"""
PulseDebug AI — Incidents API Router
=======================================
File: backend/app/api/incidents.py
Purpose:
    CRUD-ish endpoints for the incident records created by the clustering
    engine. The frontend uses these to render the Incident Feed and
    Incident Detail Panel.

Endpoints:
    GET  /api/incidents              — list all open incidents (newest first)
    GET  /api/incidents/{id}         — single incident detail
    GET  /api/incidents/{id}/logs    — log events belonging to this incident
    POST /api/incidents/{id}/resolve — mark an incident as resolved

Author: PulseDebug AI Hackathon Team
"""

from fastapi import APIRouter, HTTPException

from app.core.database import get_connection

router = APIRouter()


def _row_to_dict(row) -> dict:
    return dict(row)


@router.get("")
def list_incidents(status: str = "open", limit: int = 50):
    """Return incidents filtered by status, newest first."""
    conn = get_connection()
    try:
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY last_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE status = ? ORDER BY last_seen DESC LIMIT ?",
                (status, limit),
            ).fetchall()

        items = []
        for r in rows:
            d = _row_to_dict(r)
            if d.get("deployment_id"):
                dep = conn.execute(
                    "SELECT * FROM deployments WHERE id = ?", (d["deployment_id"],)
                ).fetchone()
                d["deployment"] = _row_to_dict(dep) if dep else None
            else:
                d["deployment"] = None
            items.append(d)

        return items
    finally:
        conn.close()


@router.get("/{incident_id}")
def get_incident(incident_id: int):
    """Return full detail for a single incident."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        d = _row_to_dict(row)
        if d.get("deployment_id"):
            dep = conn.execute(
                "SELECT * FROM deployments WHERE id = ?", (d["deployment_id"],)
            ).fetchone()
            d["deployment"] = _row_to_dict(dep) if dep else None
        else:
            d["deployment"] = None

        return d
    finally:
        conn.close()


@router.get("/{incident_id}/logs")
def get_incident_logs(incident_id: int, limit: int = 50):
    """Return the raw log events associated with this incident."""
    conn = get_connection()
    try:
        incident = conn.execute(
            "SELECT service, endpoint, error_signature, first_detected, last_seen "
            "FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        sig_parts = incident["error_signature"].split(":", 1)
        status_code = int(sig_parts[0]) if sig_parts[0].isdigit() else None
        error_type  = sig_parts[1] if len(sig_parts) > 1 else None

        query = """
            SELECT * FROM api_logs
            WHERE service = ?
              AND endpoint = ?
              AND timestamp BETWEEN ? AND ?
        """
        params = [
            incident["service"],
            incident["endpoint"],
            incident["first_detected"],
            incident["last_seen"],
        ]
        if status_code:
            query += " AND status_code = ?"
            params.append(status_code)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/{incident_id}/resolve")
def resolve_incident(incident_id: int):
    """Mark an incident as resolved."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        conn.execute(
            "UPDATE incidents SET status = 'resolved', updated_at = datetime('now') WHERE id = ?",
            (incident_id,),
        )
        conn.commit()
        return {"success": True, "incident_id": incident_id, "status": "resolved"}
    finally:
        conn.close()