"""
PulseDebug AI — Real API Log Ingestion Endpoint
=================================================
File: backend/app/api/ingest.py
Purpose:
    Accepts real telemetry from external projects via POST /api/ingest.
    When a payload arrives it is validated, stored, run through anomaly
    detection, clustered into incidents, correlated with deployments, and
    — if the incident crosses a severity threshold — queued for Gemini RCA.

    This is the endpoint that makes PulseDebug a real monitoring backend
    rather than a simulation-only demo.

    Expected payload:
        {
            "service":         "Orders API",
            "endpoint":        "/orders/create",
            "status":          500,
            "latency":         4100,
            "error_signature": "DB_TIMEOUT",     (optional)
            "error_msg":       "...",            (optional)
            "method":          "POST"            (optional, default GET)
        }

Author: PulseDebug AI Hackathon Team
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator

from app.core.database import get_connection
from app.services.anomaly_detector import AnomalyDetector
from app.services.clustering import IncidentClusterer
from app.services.ai_service import analyse_incident, ai_status
import json

router = APIRouter()
_detector  = AnomalyDetector()
_clusterer = IncidentClusterer()


# ---------------------------------------------------------------------------
# Pydantic schema for inbound telemetry
# ---------------------------------------------------------------------------

class IngestPayload(BaseModel):
    service:          str            = Field(..., min_length=1, max_length=100)
    endpoint:         str            = Field(..., min_length=1, max_length=200)
    status:           int            = Field(..., ge=100, le=599)
    latency:          int            = Field(..., ge=0, le=300_000)
    error_signature:  Optional[str]  = Field(None, max_length=200)
    error_msg:        Optional[str]  = Field(None, max_length=1000)
    method:           Optional[str]  = Field("GET", max_length=10)

    @field_validator("method")
    @classmethod
    def uppercase_method(cls, v: str) -> str:
        return v.upper() if v else "GET"


class IngestResponse(BaseModel):
    received:       bool
    log_id:         int
    is_anomaly:     bool
    incident_id:    Optional[int]
    ai_queued:      bool
    message:        str


# ---------------------------------------------------------------------------
# Background task — run Gemini RCA on a new/updated incident
# ---------------------------------------------------------------------------

async def _maybe_run_rca(incident_id: int) -> None:
    """
    Runs in the background after a high-severity incident is created or
    updated.  Persists AI result back to the incident row.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            return

        incident = dict(row)

        # Only run RCA for critical/warning incidents without existing analysis
        if incident.get("ai_summary"):
            return
        if incident["severity"] not in ("critical", "warning"):
            return

        deployment = None
        if incident.get("deployment_id"):
            dep = conn.execute(
                "SELECT * FROM deployments WHERE id = ?",
                (incident["deployment_id"],)
            ).fetchone()
            deployment = dict(dep) if dep else None

        # Build log statistics
        rows = conn.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_anomaly=1 THEN 1 ELSE 0 END) as anomalies,
                   AVG(latency_ms) as avg_lat,
                   MAX(latency_ms) as max_lat,
                   SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) as srv_err,
                   SUM(CASE WHEN status_code>=400 AND status_code<500 THEN 1 ELSE 0 END) as cli_err
            FROM api_logs
            WHERE service=? AND endpoint=?
              AND timestamp BETWEEN ? AND ?
            """,
            (incident["service"], incident["endpoint"],
             incident["first_detected"], incident["last_seen"])
        ).fetchone()

        logs_summary = {}
        if rows and rows["total"]:
            logs_summary = {
                "total_events":   rows["total"],
                "anomaly_count":  rows["anomalies"],
                "avg_latency_ms": round(rows["avg_lat"] or 0, 1),
                "max_latency_ms": rows["max_lat"] or 0,
                "server_errors":  rows["srv_err"],
                "client_errors":  rows["cli_err"],
                "error_rate":     round(
                    (rows["srv_err"] + rows["cli_err"]) / rows["total"], 3
                ),
            }

        analysis, model_used = await analyse_incident(incident, logs_summary, deployment)

        if analysis:
            conn.execute(
                """
                UPDATE incidents
                SET ai_summary=?, ai_root_cause=?, ai_checks=?,
                    ai_priority=?, ai_model_used=?, updated_at=datetime('now')
                WHERE id=?
                """,
                (
                    analysis.get("incident_summary"),
                    analysis.get("likely_cause"),
                    json.dumps(analysis.get("recommended_checks", [])),
                    analysis.get("investigation_priority"),
                    model_used,
                    incident_id,
                )
            )
            conn.commit()
            print(f"[Ingest] RCA complete for incident #{incident_id} via {model_used}")

    except Exception as exc:
        print(f"[Ingest] RCA background task error: {exc}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ingest endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=IngestResponse)
async def ingest_event(
    payload: IngestPayload,
    background_tasks: BackgroundTasks,
):
    """
    Accept a single telemetry event from an external service.
    Runs anomaly detection synchronously, clustering asynchronously.
    Returns immediately so the caller is not blocked.
    """
    conn = get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()

        # ------------------------------------------------------------------
        # 1. Store the raw event
        # ------------------------------------------------------------------
        cursor = conn.execute(
            """
            INSERT INTO api_logs
                (timestamp, service, endpoint, method, status_code,
                 latency_ms, error_type, error_msg, is_anomaly, scenario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'external_ingest')
            """,
            (
                now,
                payload.service,
                payload.endpoint,
                payload.method,
                payload.status,
                payload.latency,
                payload.error_signature,
                payload.error_msg,
            )
        )
        conn.commit()
        log_id = cursor.lastrowid

        # ------------------------------------------------------------------
        # 2. Run anomaly detection
        # ------------------------------------------------------------------
        is_anomaly = _detector.evaluate(
            conn,
            log_id=log_id,
            service=payload.service,
            endpoint=payload.endpoint,
            status_code=payload.status,
            latency_ms=payload.latency,
        )

        # ------------------------------------------------------------------
        # 3. Cluster if anomalous
        # ------------------------------------------------------------------
        incident_id  = None
        ai_queued    = False

        if is_anomaly:
            # Use a synthetic scenario key based on service + error signature
            scenario_key = (
                payload.error_signature
                or f"ext_{payload.service.lower().replace(' ', '_')}_{payload.status}"
            )
            incident_id = _clusterer.cluster_external(
                conn,
                service=payload.service,
                endpoint=payload.endpoint,
                status_code=payload.status,
                error_type=payload.error_signature or "UNKNOWN",
                scenario_key=scenario_key,
            )

            # ------------------------------------------------------------------
            # 4. Queue background RCA for critical incidents
            # ------------------------------------------------------------------
            if incident_id and ai_status()["available"]:
                inc_row = conn.execute(
                    "SELECT severity, occurrence_count FROM incidents WHERE id=?",
                    (incident_id,)
                ).fetchone()
                if inc_row and inc_row["severity"] in ("critical", "warning"):
                    background_tasks.add_task(_maybe_run_rca, incident_id)
                    ai_queued = True

        return IngestResponse(
            received=True,
            log_id=log_id,
            is_anomaly=is_anomaly,
            incident_id=incident_id,
            ai_queued=ai_queued,
            message=(
                f"Event stored. Anomaly detected — incident #{incident_id} updated."
                if is_anomaly and incident_id
                else "Event stored. No anomaly detected."
            ),
        )

    finally:
        conn.close()


@router.get("/schema")
def ingest_schema():
    """Returns the expected ingest payload schema — useful for SDK docs."""
    return {
        "endpoint":  "POST /api/ingest",
        "fields": {
            "service":         "string  (required) — e.g. 'Orders API'",
            "endpoint":        "string  (required) — e.g. '/orders/create'",
            "status":          "integer (required) — HTTP status code 100-599",
            "latency":         "integer (required) — response time in ms",
            "error_signature": "string  (optional) — e.g. 'DB_TIMEOUT'",
            "error_msg":       "string  (optional) — full error message",
            "method":          "string  (optional) — HTTP method, default GET",
        },
        "example": {
            "service":         "Orders API",
            "endpoint":        "/orders/create",
            "status":          500,
            "latency":         4100,
            "error_signature": "DB_TIMEOUT",
            "error_msg":       "Connection pool exhausted after 4100ms",
            "method":          "POST",
        }
    }
