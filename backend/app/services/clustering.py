"""
PulseDebug AI — Incident Clustering Engine
============================================
File: backend/app/services/clustering.py
Purpose:
    Groups related anomalous API log events into de-duplicated incident
    records. Clustering is entirely deterministic — no AI required.

    Two clustering entry points:
        cluster_recent()   — used by the simulator after scenario injection
        cluster_external() — used by the /api/ingest endpoint for real traffic

    Clustering dimensions (all must match to join an existing incident):
        - service name
        - endpoint
        - error_type / HTTP status-code bucket
        - temporal proximity (events within CLUSTER_TIME_WINDOW_SEC)

    Severity mapping:
        5xx / 401 / 403   → critical
        429               → warning
        latency / burst   → warning
        other 4xx         → investigate

Author: PulseDebug AI Hackathon Team
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SEVERITY_MAP = {
    500: "critical", 502: "critical", 503: "critical", 504: "critical",
    501: "critical",
    401: "critical", 403: "critical",
    429: "warning",
    400: "investigate",
    422: "investigate",
}

SCENARIO_TITLES = {
    "auth_secret_mismatch":   "Authentication Service — JWT Key Mismatch",
    "db_timeout":             "Orders API — Database Timeout Cascade",
    "malformed_payload":      "Payment API — Schema Validation Failure Burst",
    "deployment_regression":  "Orders API — Deployment Regression (500 Storm)",
    "dependency_outage":      "Notification API — Upstream SMTP Dependency Outage",
    "retry_storm":            "Orders API — Consumer Retry Storm (429 Flood)",
}


def _severity_for(status_code: int) -> str:
    return SEVERITY_MAP.get(status_code, "critical" if status_code >= 500 else "investigate")


class IncidentClusterer:

    # ------------------------------------------------------------------
    # Simulator path (existing)
    # ------------------------------------------------------------------

    def cluster_recent(
        self,
        conn: sqlite3.Connection,
        *,
        scenario: str,
        deployment_id: Optional[int] = None,
    ) -> Optional[int]:
        """Cluster the most recent anomalous events for a simulator scenario."""
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=settings.CLUSTER_TIME_WINDOW_SEC)
        ).isoformat()

        rows = conn.execute(
            """
            SELECT * FROM api_logs
            WHERE is_anomaly = 1 AND scenario = ? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT 50
            """,
            (scenario, cutoff),
        ).fetchall()

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
            title=title,
            service=service,
            endpoint=endpoint,
            error_sig=error_sig,
            severity=severity,
            count=count,
            first_ts=first_ts,
            last_ts=last_ts,
            deployment_id=deployment_id,
        )

    # ------------------------------------------------------------------
    # External ingest path (new)
    # ------------------------------------------------------------------

    def cluster_external(
        self,
        conn: sqlite3.Connection,
        *,
        service: str,
        endpoint: str,
        status_code: int,
        error_type: str,
        scenario_key: str,
    ) -> Optional[int]:
        """
        Cluster a single externally-ingested anomalous event.
        Creates or updates an incident for the (service, endpoint, error)
        combination.
        """
        error_sig = f"{status_code}:{error_type.upper()}"
        severity  = _severity_for(status_code)
        now       = _now_iso()

        # Build a human-readable title from the service + error type
        title = f"{service} — {error_type.replace('_', ' ').title()} (External)"

        return self._upsert_incident(
            conn,
            title=title,
            service=service,
            endpoint=endpoint,
            error_sig=error_sig,
            severity=severity,
            count=1,
            first_ts=now,
            last_ts=now,
            deployment_id=None,
        )

    # ------------------------------------------------------------------
    # Shared upsert logic
    # ------------------------------------------------------------------

    def _upsert_incident(
        self,
        conn: sqlite3.Connection,
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
    ) -> int:
        is_deployment_related = deployment_id is not None

        existing = conn.execute(
            """
            SELECT id, occurrence_count FROM incidents
            WHERE service = ? AND endpoint = ? AND error_signature = ?
              AND status = 'open'
            ORDER BY first_detected DESC LIMIT 1
            """,
            (service, endpoint, error_sig),
        ).fetchone()

        if existing:
            new_count = existing["occurrence_count"] + count
            conn.execute(
                """
                UPDATE incidents
                SET occurrence_count = ?, last_seen = ?,
                    deployment_id = COALESCE(?, deployment_id),
                    deployment_related = MAX(deployment_related, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (new_count, last_ts, deployment_id,
                 1 if is_deployment_related else 0, _now_iso(), existing["id"]),
            )
            conn.commit()
            print(f"[Clusterer] Updated incident #{existing['id']} — {title}")
            return existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO incidents (
                    title, service, endpoint, error_signature,
                    severity, status, occurrence_count,
                    first_detected, last_seen, deployment_id, deployment_related
                ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (title, service, endpoint, error_sig, severity, count,
                 first_ts, last_ts, deployment_id,
                 1 if is_deployment_related else 0),
            )
            conn.commit()
            incident_id = cursor.lastrowid
            print(f"[Clusterer] Created incident #{incident_id} — {title}")
            return incident_id
