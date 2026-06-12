"""
PulseDebug AI — Incident Timeline Service
==========================================
File: backend/app/services/timeline.py
Purpose:
    Manages incident lifecycle timeline events.
    Fixed: replaced all conn.execute() calls with database.execute()
    helper so timeline works with both SQLite and PostgreSQL.

Author: PulseDebug AI Hackathon Team
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_connection, execute, fetchall, commit, lastrowid, USING_POSTGRES


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_timeline_event(
    conn,
    incident_id: int,
    event_type: str,
    title: str,
    detail: Optional[str] = None,
) -> int:
    if USING_POSTGRES:
        cur = execute(conn,
            """
            INSERT INTO timeline_events (incident_id, timestamp, event_type, title, detail)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            (incident_id, _now_iso(), event_type, title, detail),
        )
        row_id = lastrowid(cur)
    else:
        cur = execute(conn,
            """
            INSERT INTO timeline_events (incident_id, timestamp, event_type, title, detail)
            VALUES (?, ?, ?, ?, ?)
            """,
            (incident_id, _now_iso(), event_type, title, detail),
        )
        row_id = lastrowid(cur)

    commit(conn)
    return row_id


def get_timeline(incident_id: int) -> list:
    conn = get_connection()
    try:
        rows = fetchall(
            execute(conn,
                """
                SELECT * FROM timeline_events
                WHERE incident_id = ?
                ORDER BY timestamp ASC
                """,
                (incident_id,),
            )
        )
        return rows
    finally:
        conn.close()


EVENT_META = {
    "anomaly_detected":  {"icon": "alert",    "color": "#f85149", "label": "Anomaly Detected"},
    "cluster_formed":    {"icon": "layers",   "color": "#d29922", "label": "Incident Cluster Formed"},
    "deployment_linked": {"icon": "git",      "color": "#d29922", "label": "Deployment Correlated"},
    "ai_analysis":       {"icon": "brain",    "color": "#a371f7", "label": "AI Analysis Generated"},
    "escalated":         {"icon": "trending", "color": "#f85149", "label": "Incident Escalated"},
    "retry_storm":       {"icon": "refresh",  "color": "#fb8f44", "label": "Retry Storm Detected"},
    "latency_spike":     {"icon": "clock",    "color": "#d29922", "label": "Latency Spike Detected"},
    "resolved":          {"icon": "check",    "color": "#3fb950", "label": "Incident Resolved"},
}