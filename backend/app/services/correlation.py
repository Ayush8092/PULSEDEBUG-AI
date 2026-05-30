"""
PulseDebug AI — Incident Correlation Engine
============================================
File: backend/app/services/correlation.py
Purpose:
    Automatically correlates related incidents to build a root-cause
    chain graph. Uses rule-based logic on timestamps, services, error
    signatures, and latency patterns.

    Correlation rules:
        1. Temporal proximity   — incidents within 5 minutes of each other
        2. Service dependency   — known upstream/downstream service pairs
        3. Error cascade        — DB_TIMEOUT → 503 → retry storm pattern
        4. Deployment burst     — multiple incidents after same deployment

    Output feeds:
        - incident_correlations table
        - /api/incidents/correlations/{id} endpoint
        - frontend root-cause chain graph

Author: PulseDebug AI Hackathon Team
"""

from datetime import datetime, timezone, timedelta
from app.core.database import get_connection


# Known service dependency chains
SERVICE_DEPS = {
    "Orders API":       ["Inventory API", "Payment API", "Notification API"],
    "Payment API":      ["Notification API"],
    "Auth API":         ["Orders API", "Payment API"],
    "Notification API": [],
    "Inventory API":    ["Orders API"],
}

# Error signature cascade patterns
CASCADE_PATTERNS = [
    ("DB_TIMEOUT",           "INTERNAL_ERROR",        "caused_by",  0.90),
    ("DB_TIMEOUT",           "UPSTREAM_UNAVAILABLE",  "triggered",  0.85),
    ("INTERNAL_ERROR",       "UPSTREAM_UNAVAILABLE",  "triggered",  0.75),
    ("UPSTREAM_UNAVAILABLE", "RATE_LIMITED",          "triggered",  0.80),
    ("JWT_MISMATCH",         "INTERNAL_ERROR",        "caused_by",  0.70),
    ("MALFORMED_PAYLOAD",    "INTERNAL_ERROR",        "caused_by",  0.65),
]


def run_correlation_engine(incident_id: int) -> None:
    """
    Analyse a new incident and create correlation edges to related incidents.
    Called as a background task after each new incident is created.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            return

        incident = dict(row)
        _correlate_temporal(conn, incident)
        _correlate_cascade(conn, incident)
        _correlate_deployment(conn, incident)

    except Exception as exc:
        print(f"[Correlation] Error: {exc}")
    finally:
        conn.close()


def _correlate_temporal(conn, incident: dict) -> None:
    """Find incidents within 5 minutes that affect dependent services."""
    cutoff_before = (
        datetime.fromisoformat(incident["first_detected"].replace("Z", "+00:00"))
        - timedelta(minutes=5)
    ).isoformat()
    cutoff_after = (
        datetime.fromisoformat(incident["first_detected"].replace("Z", "+00:00"))
        + timedelta(minutes=5)
    ).isoformat()

    related = conn.execute(
        """
        SELECT id, service, error_signature, severity FROM incidents
        WHERE id != ?
          AND status = 'open'
          AND first_detected BETWEEN ? AND ?
        ORDER BY first_detected ASC
        LIMIT 5
        """,
        (incident["id"], cutoff_before, cutoff_after),
    ).fetchall()

    deps = SERVICE_DEPS.get(incident["service"], [])

    for r in related:
        r = dict(r)
        if r["service"] in deps or incident["service"] in SERVICE_DEPS.get(r["service"], []):
            _upsert_correlation(
                conn,
                from_incident=r["id"],
                to_incident=incident["id"],
                relation_type="triggered",
                confidence=0.75,
            )


def _correlate_cascade(conn, incident: dict) -> None:
    """Match known error cascade patterns."""
    sig = (incident.get("error_signature") or "").split(":", 1)
    error_type = sig[1] if len(sig) > 1 else sig[0]

    for from_sig, to_sig, rel_type, confidence in CASCADE_PATTERNS:
        if to_sig.upper() in error_type.upper():
            # Find recent incident with from_sig
            cutoff = (
                datetime.now(timezone.utc) - timedelta(minutes=15)
            ).isoformat()
            row = conn.execute(
                """
                SELECT id FROM incidents
                WHERE error_signature LIKE ?
                  AND id != ?
                  AND first_detected >= ?
                  AND status = 'open'
                ORDER BY first_detected DESC
                LIMIT 1
                """,
                (f"%{from_sig}%", incident["id"], cutoff),
            ).fetchone()
            if row:
                _upsert_correlation(
                    conn,
                    from_incident=row["id"],
                    to_incident=incident["id"],
                    relation_type=rel_type,
                    confidence=confidence,
                )


def _correlate_deployment(conn, incident: dict) -> None:
    """Group incidents linked to the same deployment."""
    if not incident.get("deployment_id"):
        return

    siblings = conn.execute(
        """
        SELECT id FROM incidents
        WHERE deployment_id = ?
          AND id != ?
          AND status = 'open'
        ORDER BY first_detected ASC
        LIMIT 5
        """,
        (incident["deployment_id"], incident["id"]),
    ).fetchall()

    for sib in siblings:
        _upsert_correlation(
            conn,
            from_incident=sib["id"],
            to_incident=incident["id"],
            relation_type="co_deployment",
            confidence=0.80,
        )


def _upsert_correlation(conn, from_incident: int, to_incident: int,
                         relation_type: str, confidence: float) -> None:
    exists = conn.execute(
        """
        SELECT id FROM incident_correlations
        WHERE from_incident = ? AND to_incident = ?
        """,
        (from_incident, to_incident),
    ).fetchone()

    if not exists:
        conn.execute(
            """
            INSERT INTO incident_correlations
                (from_incident, to_incident, relation_type, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (from_incident, to_incident, relation_type, confidence),
        )
        conn.commit()


def get_correlation_graph(incident_id: int) -> dict:
    """Return nodes and edges for the root-cause chain graph."""
    conn = get_connection()
    try:
        # Get all correlations involving this incident (as source or target)
        edges = conn.execute(
            """
            SELECT * FROM incident_correlations
            WHERE from_incident = ? OR to_incident = ?
            """,
            (incident_id, incident_id),
        ).fetchall()

        node_ids = set([incident_id])
        for e in edges:
            node_ids.add(e["from_incident"])
            node_ids.add(e["to_incident"])

        nodes = []
        for nid in node_ids:
            row = conn.execute(
                "SELECT id, title, service, severity, error_signature, status FROM incidents WHERE id = ?",
                (nid,)
            ).fetchone()
            if row:
                nodes.append({
                    **dict(row),
                    "is_root": nid == incident_id,
                })

        edge_list = [
            {
                "from":          e["from_incident"],
                "to":            e["to_incident"],
                "relation_type": e["relation_type"],
                "confidence":    e["confidence"],
            }
            for e in edges
        ]

        return {"nodes": nodes, "edges": edge_list}
    finally:
        conn.close()