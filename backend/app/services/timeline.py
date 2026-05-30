"""
PulseDebug AI — Incident Timeline Service
==========================================
File: backend/app/services/timeline.py
Purpose:
    Manages incident lifecycle timeline events for the Timeline Replay feature.
    Creates, reads, and streams timeline events per incident.

    Event types:
        anomaly_detected    — first anomaly flagged
        cluster_formed      — incidents grouped
        deployment_linked   — linked to a deployment
        ai_analysis         — Gemini RCA generated
        escalated           — severity upgraded
        retry_storm         — retry pattern detected
        latency_spike       — latency threshold breached
        resolved            — incident closed

Author: PulseDebug AI Hackathon Team
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_timeline_event(
    conn: sqlite3.Connection,
    incident_id: int,
    event_type: str,
    title: str,
    detail: Optional[str] = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO timeline_events (incident_id, timestamp, event_type, title, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (_now_iso(), incident_id, event_type, title, detail),
    )
    # Note: parameter order matches (incident_id, timestamp, event_type, title, detail)
    # but INSERT order is (incident_id, timestamp, ...) - fix column order
    conn.execute("DELETE FROM timeline_events WHERE id = ?", (cursor.lastrowid,))

    cursor2 = conn.execute(
        """
        INSERT INTO timeline_events (incident_id, timestamp, event_type, title, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (incident_id, _now_iso(), event_type, title, detail),
    )
    conn.commit()
    return cursor2.lastrowid


def get_timeline(incident_id: int) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM timeline_events
            WHERE incident_id = ?
            ORDER BY timestamp ASC
            """,
            (incident_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Event type metadata for frontend display
EVENT_META = {
    "anomaly_detected":  {"icon": "alert",   "color": "#f85149", "label": "Anomaly Detected"},
    "cluster_formed":    {"icon": "layers",  "color": "#d29922", "label": "Incident Cluster Formed"},
    "deployment_linked": {"icon": "git",     "color": "#d29922", "label": "Deployment Correlated"},
    "ai_analysis":       {"icon": "brain",   "color": "#a371f7", "label": "AI Analysis Generated"},
    "escalated":         {"icon": "trending","color": "#f85149", "label": "Incident Escalated"},
    "retry_storm":       {"icon": "refresh", "color": "#fb8f44", "label": "Retry Storm Detected"},
    "latency_spike":     {"icon": "clock",   "color": "#d29922", "label": "Latency Spike Detected"},
    "resolved":          {"icon": "check",   "color": "#3fb950", "label": "Incident Resolved"},
}