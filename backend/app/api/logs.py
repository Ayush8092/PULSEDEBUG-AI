"""
PulseDebug AI — Logs API Router
==================================
File: backend/app/api/logs.py
Purpose:
    Log query and SSE streaming endpoints.
    Upgrade: source filtering on all query endpoints.

Author: PulseDebug AI Hackathon Team
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.database import get_connection
from app.services.anomaly_detector import AnomalyDetector

router = APIRouter()
_detector = AnomalyDetector()


def _row_to_dict(row) -> dict:
    return dict(row)


@router.get("")
def get_logs(
    page:         int  = Query(1, ge=1),
    per_page:     int  = Query(50, ge=1, le=200),
    service:      str  = None,
    anomaly_only: bool = False,
    source:       str  = None,
):
    conn = get_connection()
    try:
        offset     = (page - 1) * per_page
        conditions = []
        params     = []

        if service:
            conditions.append("service = ?")
            params.append(service)
        if anomaly_only:
            conditions.append("is_anomaly = 1")
        if source:
            conditions.append("source = ?")
            params.append(source)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM api_logs {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM api_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()

        return {
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "items":    [_row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/recent")
def get_recent_logs(limit: int = Query(50, ge=1, le=500), source: str = None):
    conn = get_connection()
    try:
        if source:
            rows = conn.execute(
                "SELECT * FROM api_logs WHERE source=? ORDER BY id DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM api_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/anomalies")
def get_anomalies(limit: int = Query(100, ge=1, le=500), source: str = None):
    conn = get_connection()
    try:
        if source:
            rows = conn.execute(
                "SELECT * FROM api_logs WHERE is_anomaly=1 AND source=? ORDER BY id DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM api_logs WHERE is_anomaly=1 ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/stats")
def get_stats():
    return _detector.get_endpoint_stats()


@router.get("/timeseries")
def get_timeseries(minutes: int = Query(10, ge=1, le=60)):
    conn = get_connection()
    try:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=minutes)
        ).isoformat()

        rows = conn.execute(
            """
            SELECT
                strftime('%Y-%m-%dT%H:%M:00Z', timestamp) AS minute,
                COUNT(*) AS total,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
                AVG(latency_ms) AS avg_latency
            FROM api_logs WHERE timestamp >= ?
            GROUP BY minute ORDER BY minute ASC
            """,
            (cutoff,),
        ).fetchall()

        return [
            {
                "minute":      r["minute"],
                "total":       r["total"],
                "errors":      r["errors"],
                "avg_latency": round(r["avg_latency"] or 0, 1),
            }
            for r in rows
        ]
    finally:
        conn.close()


async def _sse_generator(source_filter: str = None):
    """
    True Server-Sent Events generator.
    Polls for new log events every second and pushes them immediately.
    Filters by source if specified.
    """
    last_id = 0
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(id) FROM api_logs").fetchone()
        last_id = row[0] or 0
    finally:
        conn.close()

    while True:
        await asyncio.sleep(1)
        conn = get_connection()
        try:
            if source_filter:
                rows = conn.execute(
                    "SELECT * FROM api_logs WHERE id > ? AND source=? ORDER BY id ASC LIMIT 20",
                    (last_id, source_filter),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM api_logs WHERE id > ? ORDER BY id ASC LIMIT 20",
                    (last_id,),
                ).fetchall()

            for row in rows:
                d = _row_to_dict(row)
                last_id = d["id"]
                yield f"data: {json.dumps(d)}\n\n"

            # Heartbeat every cycle to keep connection alive
            yield ": heartbeat\n\n"
        except Exception:
            pass
        finally:
            conn.close()


@router.get("/stream")
async def stream_logs(source: str = None):
    """True SSE endpoint — pushes new events instantly as they arrive."""
    return StreamingResponse(
        _sse_generator(source_filter=source),
        media_type="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":      "keep-alive",
        },
    )