"""
PulseDebug AI — Incident Clustering Engine
============================================
File: backend/app/services/clustering.py
Purpose:
    Groups anomalous events into deduplicated incidents.
    Fixed: replaced all conn.execute() calls with database.execute()
    helper so clustering works with both SQLite and PostgreSQL.

Author: PulseDebug AI Hackathon Team
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.config import settings
from app.core.database import execute, fetchone, commit, lastrowid, USING_POSTGRES


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SEVERITY_MAP = {
    500: "critical", 502: "critical", 503: "critical", 504: "critical",
    501: "critical", 401: "critical", 403: "critical",
    429: "warning",  400: "investigate", 422: "investigate",
}

SCENARIO_TITLES = {
    "auth_secret_mismatch":  "Authentication Service — JWT Key Mismatch",
    "db_timeout":            "Orders API — Database Timeout Cascade",
    "malformed_payload":     "Payment API — Schema Validation Failure Burst",
    "deployment_regression": "Orders API — Deployment Regression (500 Storm)",
    "dependency_outage":     "Notification API — Upstream SMTP Dependency Outage",
    "retry_storm":           "Orders API — Consumer Retry Storm (429 Flood)",
}


def _severity_for(status_code: int) -> str:
    return SEVERITY_MAP.get(
        status_code,
        "critical" if status_code >= 500 else "investigate"
    )


class IncidentClusterer:

    def cluster_recent(
        self,
        conn,
        *,
        scenario: str,
        deployment_id: Optional[int] = None,
        source: str = "demo",
    ) -> Optional[int]:
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=settings.CLUSTER_TIME_WINDOW_SEC)
        ).isoformat()

        rows_cur = execute(conn,
            """
            SELECT * FROM api_logs
            WHERE is_anomaly = 1 AND scenario = ? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT 50
            """,
            (scenario, cutoff),
        )
        from app.core.database import fetchall
        rows = fetchall(rows_cur)

        if not rows:
            return None

        service     = rows[0]["service"]
        endpoint    = rows[0]["endpoint"]
        error_type  = rows[0]["error_type"] or "UNKNOWN"
        status_code = rows[0]["status_code"]
        first_ts    = min(r["timestamp"] for r in rows)
        last_ts     = max(r["timestamp"] for r in rows)
        count       = len(rows)

        error_sig = f"{status_code}:{error_type}"
        severity  = _severity_for(status_code)
        title     = SCENARIO_TITLES.get(scenario, f"{service} — Incident Detected")

        return self._upsert_incident(
            conn,
            title=title, service=service, endpoint=endpoint,
            error_sig=error_sig, severity=severity, count=count,
            first_ts=first_ts, last_ts=last_ts,
            deployment_id=deployment_id, source=source,
        )

    def cluster_external(
        self,
        conn,
        *,
        service: str,
        endpoint: str,
        status_code: int,
        error_type: str,
        scenario_key: str,
        source: str = "external",
    ) -> Optional[int]:
        error_sig = f"{status_code}:{error_type.upper()}"
        severity  = _severity_for(status_code)
        now       = _now_iso()
        title     = f"{service} — {error_type.replace('_', ' ').title()} ({source.title()})"

        return self._upsert_incident(
            conn,
            title=title, service=service, endpoint=endpoint,
            error_sig=error_sig, severity=severity, count=1,
            first_ts=now, last_ts=now,
            deployment_id=None, source=source,
        )

    def _upsert_incident(
        self,
        conn,
        *,
        title: str,
        service: str,
        endpoint: str,
        error_sig: str,
        severity: str,
        count: int,
        first_ts: str,
        last_ts: str,
        deployment_id: Optional[int],
        source: str = "demo",
    ) -> int:
        is_deployment_related = deployment_id is not None

        existing = fetchone(
            execute(conn,
                """
                SELECT id, occurrence_count FROM incidents
                WHERE service = ? AND endpoint = ? AND error_signature = ?
                  AND status = 'open'
                ORDER BY first_detected DESC LIMIT 1
                """,
                (service, endpoint, error_sig),
            )
        )

        if existing:
            new_count = existing["occurrence_count"] + count
            execute(conn,
                """
                UPDATE incidents
                SET occurrence_count = ?, last_seen = ?,
                    deployment_id = COALESCE(?, deployment_id),
                    deployment_related = GREATEST(deployment_related, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (new_count, last_ts, deployment_id,
                 1 if is_deployment_related else 0,
                 _now_iso(), existing["id"]),
            ) if USING_POSTGRES else execute(conn,
                """
                UPDATE incidents
                SET occurrence_count = ?, last_seen = ?,
                    deployment_id = COALESCE(?, deployment_id),
                    deployment_related = MAX(deployment_related, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (new_count, last_ts, deployment_id,
                 1 if is_deployment_related else 0,
                 _now_iso(), existing["id"]),
            )
            commit(conn)
            print(f"[Clusterer] Updated incident #{existing['id']} — {title}")
            return existing["id"]

        else:
            if USING_POSTGRES:
                cur = execute(conn,
                    """
                    INSERT INTO incidents (
                        title, service, endpoint, error_signature,
                        severity, status, occurrence_count,
                        first_detected, last_seen, deployment_id,
                        deployment_related, source
                    ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (title, service, endpoint, error_sig, severity, count,
                     first_ts, last_ts, deployment_id,
                     1 if is_deployment_related else 0, source),
                )
                incident_id = lastrowid(cur)
            else:
                cur = execute(conn,
                    """
                    INSERT INTO incidents (
                        title, service, endpoint, error_signature,
                        severity, status, occurrence_count,
                        first_detected, last_seen, deployment_id,
                        deployment_related, source
                    ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
                    """,
                    (title, service, endpoint, error_sig, severity, count,
                     first_ts, last_ts, deployment_id,
                     1 if is_deployment_related else 0, source),
                )
                incident_id = lastrowid(cur)

            commit(conn)
            print(f"[Clusterer] Created incident #{incident_id} — {title}")
            return incident_id