"""
PulseDebug AI — Incident Correlation Engine
============================================
File: backend/app/services/correlation.py
Purpose:
    Automatically correlates related incidents to build causal chains.
    Fixed: replaced all conn.execute() calls with database.execute()
    helper so correlation works with both SQLite and PostgreSQL.

Author: PulseDebug AI Hackathon Team
"""

from datetime import datetime, timezone, timedelta
from app.core.database import get_connection, execute, fetchone, fetchall, commit


SERVICE_DEPS = {
    "Orders API":       ["Inventory API", "Payment API", "Notification API"],
    "Payment API":      ["Notification API"],
    "Auth API":         ["Orders API", "Payment API"],
    "Notification API": [],
    "Inventory API":    ["Orders API"],
}

CASCADE_PATTERNS = [
    ("DB_TIMEOUT",           "INTERNAL_ERROR",       "caused_by", 0.90),
    ("DB_TIMEOUT",           "UPSTREAM_UNAVAILABLE", "triggered", 0.85),
    ("INTERNAL_ERROR",       "UPSTREAM_UNAVAILABLE", "triggered", 0.75),
    ("UPSTREAM_UNAVAILABLE", "RATE_LIMITED",         "triggered", 0.80),
    ("JWT_MISMATCH",         "INTERNAL_ERROR",       "caused_by", 0.70),
    ("MALFORMED_PAYLOAD",    "INTERNAL_ERROR",       "caused_by", 0.65),
]


def run_correlation_engine(incident_id: int) -> None:
    conn = get_connection()
    try:
        row = fetchone(
            execute(conn, "SELECT * FROM incidents WHERE id = ?", (incident_id,))
        )
        if not row:
            return
        _correlate_temporal(conn, row)
        _correlate_cascade(conn, row)
        _correlate_deployment(conn, row)
    except Exception as exc:
        print(f"[Correlation] Error: {exc}")
    finally:
        conn.close()


def _correlate_temporal(conn, incident: dict) -> None:
    try:
        ts = incident["first_detected"].replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
    except Exception:
        return

    cutoff_before = (dt - timedelta(minutes=5)).isoformat()
    cutoff_after  = (dt + timedelta(minutes=5)).isoformat()

    related = fetchall(
        execute(conn,
            """
            SELECT id, service, error_signature, severity FROM incidents
            WHERE id != ?
              AND status = 'open'
              AND first_detected BETWEEN ? AND ?
            ORDER BY first_detected ASC
            LIMIT 5
            """,
            (incident["id"], cutoff_before, cutoff_after),
        )
    )

    deps = SERVICE_DEPS.get(incident["service"], [])
    for r in related:
        if r["service"] in deps or incident["service"] in SERVICE_DEPS.get(r["service"], []):
            _upsert_correlation(conn, r["id"], incident["id"], "triggered", 0.75)


def _correlate_cascade(conn, incident: dict) -> None:
    sig        = (incident.get("error_signature") or "").split(":", 1)
    error_type = sig[1] if len(sig) > 1 else sig[0]
    cutoff     = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

    for from_sig, to_sig, rel_type, confidence in CASCADE_PATTERNS:
        if to_sig.upper() in error_type.upper():
            row = fetchone(
                execute(conn,
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
                )
            )
            if row:
                _upsert_correlation(conn, row["id"], incident["id"], rel_type, confidence)


def _correlate_deployment(conn, incident: dict) -> None:
    if not incident.get("deployment_id"):
        return

    siblings = fetchall(
        execute(conn,
            """
            SELECT id FROM incidents
            WHERE deployment_id = ?
              AND id != ?
              AND status = 'open'
            ORDER BY first_detected ASC
            LIMIT 5
            """,
            (incident["deployment_id"], incident["id"]),
        )
    )
    for sib in siblings:
        _upsert_correlation(conn, sib["id"], incident["id"], "co_deployment", 0.80)


def _upsert_correlation(
    conn,
    from_incident: int,
    to_incident: int,
    relation_type: str,
    confidence: float,
) -> None:
    exists = fetchone(
        execute(conn,
            """
            SELECT id FROM incident_correlations
            WHERE from_incident = ? AND to_incident = ?
            """,
            (from_incident, to_incident),
        )
    )
    if not exists:
        execute(conn,
            """
            INSERT INTO incident_correlations
                (from_incident, to_incident, relation_type, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (from_incident, to_incident, relation_type, confidence),
        )
        commit(conn)


def get_correlation_graph(incident_id: int) -> dict:
    conn = get_connection()
    try:
        edges = fetchall(
            execute(conn,
                """
                SELECT * FROM incident_correlations
                WHERE from_incident = ? OR to_incident = ?
                """,
                (incident_id, incident_id),
            )
        )

        node_ids = {incident_id}
        for e in edges:
            node_ids.add(e["from_incident"])
            node_ids.add(e["to_incident"])

        nodes = []
        for nid in node_ids:
            row = fetchone(
                execute(conn,
                    "SELECT id, title, service, severity, error_signature, status "
                    "FROM incidents WHERE id = ?",
                    (nid,),
                )
            )
            if row:
                nodes.append({**row, "is_root": nid == incident_id})

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