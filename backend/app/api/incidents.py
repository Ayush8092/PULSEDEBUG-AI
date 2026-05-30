"""
PulseDebug AI — Incidents API Router
=======================================
File: backend/app/api/incidents.py
Purpose:
    Incident CRUD + new endpoints for:
        - filtered feeds (all / external / critical / ai-analyzed)
        - incident timeline replay
        - root-cause correlation graph
        - deployment regression detection

Endpoints:
    GET  /api/incidents                   — list with filter support
    GET  /api/incidents/{id}              — single detail
    GET  /api/incidents/{id}/logs         — related logs
    GET  /api/incidents/{id}/timeline     — lifecycle timeline
    GET  /api/incidents/{id}/correlation  — root-cause graph
    POST /api/incidents/{id}/resolve      — resolve

Author: PulseDebug AI Hackathon Team
"""

from fastapi import APIRouter, HTTPException, Query
from app.core.database import get_connection
from app.services.timeline import get_timeline, EVENT_META
from app.services.correlation import get_correlation_graph

router = APIRouter()


def _row_to_dict(row) -> dict:
    return dict(row)


@router.get("")
def list_incidents(
    status:       str = Query("open"),
    source:       str = Query("all"),
    severity:     str = Query("all"),
    ai_analyzed:  bool = Query(False),
    limit:        int  = Query(50, ge=1, le=200),
):
    """
    List incidents with flexible filtering.
    source:      all | demo | external | manual
    severity:    all | critical | warning | investigate
    ai_analyzed: only incidents with AI diagnosis
    """
    conn = get_connection()
    try:
        conditions = []
        params     = []

        if status != "all":
            conditions.append("status = ?")
            params.append(status)

        if source != "all":
            conditions.append("source = ?")
            params.append(source)

        if severity != "all":
            conditions.append("severity = ?")
            params.append(severity)

        if ai_analyzed:
            conditions.append("ai_summary IS NOT NULL")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = conn.execute(
            f"""
            SELECT * FROM incidents
            {where}
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            params + [limit],
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
    conn = get_connection()
    try:
        incident = conn.execute(
            "SELECT service, endpoint, error_signature, first_detected, last_seen "
            "FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        sig_parts   = incident["error_signature"].split(":", 1)
        status_code = int(sig_parts[0]) if sig_parts[0].isdigit() else None

        query = """
            SELECT * FROM api_logs
            WHERE service = ? AND endpoint = ?
              AND timestamp BETWEEN ? AND ?
        """
        params = [
            incident["service"], incident["endpoint"],
            incident["first_detected"], incident["last_seen"],
        ]
        if status_code:
            query  += " AND status_code = ?"
            params.append(status_code)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/{incident_id}/timeline")
def get_incident_timeline(incident_id: int):
    """
    Return the chronological lifecycle timeline for an incident.
    Each event has type metadata for frontend icon/color rendering.
    """
    events = get_timeline(incident_id)
    enriched = []
    for ev in events:
        meta = EVENT_META.get(ev.get("event_type", ""), {})
        enriched.append({**ev, **meta})
    return enriched


@router.get("/{incident_id}/correlation")
def get_incident_correlation(incident_id: int):
    """
    Return the root-cause chain graph nodes and edges.
    Used by the frontend D3/React Flow visualization.
    """
    return get_correlation_graph(incident_id)


@router.post("/{incident_id}/resolve")
def resolve_incident(incident_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        conn.execute(
            "UPDATE incidents SET status='resolved', updated_at=datetime('now') WHERE id=?",
            (incident_id,),
        )
        conn.commit()
        return {"success": True, "incident_id": incident_id, "status": "resolved"}
    finally:
        conn.close()