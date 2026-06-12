"""
PulseDebug AI — Log Simulator Service
========================================
File: backend/app/services/simulator.py
Purpose:
    Generates synthetic API traffic and injects failure scenarios.
    Fixed: replaced all conn.execute() calls with database.execute()
    helper so the simulator works with both SQLite and PostgreSQL.

Author: PulseDebug AI Hackathon Team
"""

import asyncio
import random
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_connection, execute, commit, lastrowid, USING_POSTGRES
from app.core.config import settings
from app.services.anomaly_detector import AnomalyDetector
from app.services.clustering import IncidentClusterer


SERVICES = [
    {
        "name": "Auth API",
        "endpoints": ["/auth/login", "/auth/token", "/auth/refresh"],
        "normal_latency": (40, 150),
        "normal_codes": [200, 200, 200, 204],
    },
    {
        "name": "Payment API",
        "endpoints": ["/payments/charge", "/payments/refund", "/payments/status"],
        "normal_latency": (80, 220),
        "normal_codes": [200, 200, 201],
    },
    {
        "name": "Orders API",
        "endpoints": ["/orders", "/orders/create", "/orders/status"],
        "normal_latency": (60, 180),
        "normal_codes": [200, 200, 201, 200],
    },
    {
        "name": "Inventory API",
        "endpoints": ["/inventory/check", "/inventory/reserve", "/inventory/release"],
        "normal_latency": (30, 120),
        "normal_codes": [200, 200, 204],
    },
    {
        "name": "Notification API",
        "endpoints": ["/notify/email", "/notify/sms", "/notify/push"],
        "normal_latency": (50, 160),
        "normal_codes": [200, 202, 202],
    },
]

_deploy_version = [1, 4, 0]


def _next_deploy_version() -> str:
    _deploy_version[2] += 1
    return f"v{_deploy_version[0]}.{_deploy_version[1]}.{_deploy_version[2]}"


SCENARIOS = [
    {
        "name": "auth_secret_mismatch",
        "service": "Auth API",
        "endpoint": "/auth/token",
        "status_code": 401,
        "latency_range": (3800, 4500),
        "error_type": "JWT_MISMATCH",
        "error_msg": "JWT signing key mismatch — token verification failed",
        "burst": 8,
        "deploy_service": "Auth API",
        "deploy_notes": "Rotated JWT signing keys without restarting all replicas",
    },
    {
        "name": "db_timeout",
        "service": "Orders API",
        "endpoint": "/orders/create",
        "status_code": 504,
        "latency_range": (5000, 9000),
        "error_type": "DB_TIMEOUT",
        "error_msg": "Database connection pool exhausted — query timed out",
        "burst": 6,
        "deploy_service": "Orders API",
        "deploy_notes": "Deployed new ORM version — connection pool size changed",
    },
    {
        "name": "malformed_payload",
        "service": "Payment API",
        "endpoint": "/payments/charge",
        "status_code": 400,
        "latency_range": (20, 80),
        "error_type": "MALFORMED_PAYLOAD",
        "error_msg": "Request body validation failed — unexpected field types",
        "burst": 10,
        "deploy_service": "Payment API",
        "deploy_notes": "Updated payment schema — client SDK not updated yet",
    },
    {
        "name": "deployment_regression",
        "service": "Orders API",
        "endpoint": "/orders",
        "status_code": 500,
        "latency_range": (1200, 2800),
        "error_type": "INTERNAL_ERROR",
        "error_msg": "Unhandled exception in order processing pipeline",
        "burst": 7,
        "deploy_service": "Orders API",
        "deploy_notes": "Hot-fix deployment — introduced null pointer in order handler",
    },
    {
        "name": "dependency_outage",
        "service": "Notification API",
        "endpoint": "/notify/email",
        "status_code": 503,
        "latency_range": (6000, 12000),
        "error_type": "UPSTREAM_UNAVAILABLE",
        "error_msg": "Upstream SMTP relay unreachable — connection refused",
        "burst": 9,
        "deploy_service": "Notification API",
        "deploy_notes": "Migrated SMTP provider — DNS not yet propagated",
    },
    {
        "name": "retry_storm",
        "service": "Orders API",
        "endpoint": "/orders/status",
        "status_code": 429,
        "latency_range": (200, 600),
        "error_type": "RATE_LIMITED",
        "error_msg": "Too many retries from upstream consumer — rate limit exceeded",
        "burst": 15,
        "deploy_service": "Orders API",
        "deploy_notes": "Retry logic change in consumer service — no back-off implemented",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_log(
    conn,
    service: str,
    endpoint: str,
    method: str,
    status_code: int,
    latency_ms: int,
    error_type: Optional[str] = None,
    error_msg: Optional[str] = None,
    is_anomaly: bool = False,
    scenario: Optional[str] = None,
    source: str = "demo",
) -> int:
    """Insert a log event. Works with both SQLite and PostgreSQL."""
    if USING_POSTGRES:
        cur = execute(conn,
            """
            INSERT INTO api_logs
                (timestamp, service, endpoint, method, status_code, latency_ms,
                 error_type, error_msg, is_anomaly, scenario, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (_now_iso(), service, endpoint, method, status_code, latency_ms,
             error_type, error_msg, 1 if is_anomaly else 0, scenario, source),
        )
        row_id = lastrowid(cur)
    else:
        cur = execute(conn,
            """
            INSERT INTO api_logs
                (timestamp, service, endpoint, method, status_code, latency_ms,
                 error_type, error_msg, is_anomaly, scenario, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_now_iso(), service, endpoint, method, status_code, latency_ms,
             error_type, error_msg, 1 if is_anomaly else 0, scenario, source),
        )
        row_id = lastrowid(cur)

    commit(conn)
    return row_id


def _insert_deployment(conn, version: str, service: str, notes: str) -> int:
    """Insert a deployment event. Works with both SQLite and PostgreSQL."""
    if USING_POSTGRES:
        cur = execute(conn,
            """
            INSERT INTO deployments (version, service, deployed_at, status, notes)
            VALUES (?, ?, ?, 'success', ?)
            RETURNING id
            """,
            (version, service, _now_iso(), notes),
        )
        row_id = lastrowid(cur)
    else:
        cur = execute(conn,
            """
            INSERT INTO deployments (version, service, deployed_at, status, notes)
            VALUES (?, ?, ?, 'success', ?)
            """,
            (version, service, _now_iso(), notes),
        )
        row_id = lastrowid(cur)

    commit(conn)
    return row_id


def _auto_resolve_low_severity(conn) -> None:
    """Randomly auto-resolve one low-severity incident for natural fluctuation."""
    if random.random() > 0.25:
        return

    from app.core.database import fetchone
    row = fetchone(
        execute(conn,
            """
            SELECT id FROM incidents
            WHERE status = 'open'
              AND severity IN ('investigate', 'warning')
            ORDER BY RANDOM()
            LIMIT 1
            """,
        )
    )

    if row:
        execute(conn,
            "UPDATE incidents SET status='resolved', updated_at=? WHERE id=?",
            (_now_iso(), row["id"]),
        )
        commit(conn)
        print(f"[Simulator] Auto-resolved incident #{row['id']}")


class LogSimulator:
    """Async background task that generates log events and injects failure scenarios."""

    def __init__(self):
        self.detector  = AnomalyDetector()
        self.clusterer = IncidentClusterer()

        self._scenario_index              = 0
        self._ticks_since_last_scenario   = 0
        self._ticks_since_last_autoresolve = 0

        self._ticks_per_scenario = int(
            settings.SCENARIO_INJECTION_INTERVAL_SEC
            / settings.SIMULATOR_INTERVAL_SEC
        )
        self._ticks_per_autoresolve = int(
            90.0 / settings.SIMULATOR_INTERVAL_SEC
        )

    async def run(self):
        print("[Simulator] Starting log simulation...")
        while True:
            try:
                await self._tick()
            except Exception as exc:
                print(f"[Simulator] Error in tick: {exc}")
            await asyncio.sleep(settings.SIMULATOR_INTERVAL_SEC)

    async def _tick(self):
        conn = get_connection()
        try:
            self._ticks_since_last_scenario    += 1
            self._ticks_since_last_autoresolve += 1

            if self._ticks_since_last_scenario >= self._ticks_per_scenario:
                self._ticks_since_last_scenario = 0
                await self._inject_scenario(conn)

            if self._ticks_since_last_autoresolve >= self._ticks_per_autoresolve:
                self._ticks_since_last_autoresolve = 0
                _auto_resolve_low_severity(conn)

            # Generate normal traffic events
            for _ in range(random.randint(1, 3)):
                svc      = random.choice(SERVICES)
                endpoint = random.choice(svc["endpoints"])
                status   = random.choice(svc["normal_codes"])
                latency  = random.randint(*svc["normal_latency"])

                if random.random() < 0.05:
                    latency = random.randint(250, 450)

                log_id = _insert_log(
                    conn,
                    service=svc["name"],
                    endpoint=endpoint,
                    method="GET" if "status" in endpoint else "POST",
                    status_code=status,
                    latency_ms=latency,
                    source="demo",
                )

                self.detector.evaluate(
                    conn,
                    log_id=log_id,
                    service=svc["name"],
                    endpoint=endpoint,
                    status_code=status,
                    latency_ms=latency,
                )
        finally:
            conn.close()

    async def _inject_scenario(self, conn):
        scenario  = SCENARIOS[self._scenario_index % len(SCENARIOS)]
        self._scenario_index += 1

        version   = _next_deploy_version()
        deploy_id = _insert_deployment(
            conn,
            version=version,
            service=scenario["deploy_service"],
            notes=scenario["deploy_notes"],
        )
        print(f"[Simulator] Deployment {version} — {scenario['deploy_service']}")

        await asyncio.sleep(1.5)

        for _ in range(scenario["burst"]):
            latency_ms = random.randint(*scenario["latency_range"])
            _insert_log(
                conn,
                service=scenario["service"],
                endpoint=scenario["endpoint"],
                method="POST",
                status_code=scenario["status_code"],
                latency_ms=latency_ms,
                error_type=scenario["error_type"],
                error_msg=scenario["error_msg"],
                is_anomaly=True,
                scenario=scenario["name"],
                source="demo",
            )
            await asyncio.sleep(0.2)

        print(f"[Simulator] Injected '{scenario['name']}' — {scenario['burst']} events")

        conn2 = get_connection()
        try:
            self.clusterer.cluster_recent(
                conn2,
                scenario=scenario["name"],
                deployment_id=deploy_id,
                source="demo",
            )
        finally:
            conn2.close()