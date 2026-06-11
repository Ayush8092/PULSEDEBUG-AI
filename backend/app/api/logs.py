"""
PulseDebug AI — Logs API Router
==================================
File: backend/app/api/logs.py
Purpose:
    Log query and SSE streaming endpoints.
    Updated to use database.execute() and database.fetchall() helpers
    so all queries work with both SQLite and PostgreSQL.
    SSE streaming unchanged — uses asyncio generator as before.

Author: PulseDebug AI Hackathon Team
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.database import get_connection, execute, fetchone, fetchall
from app.services.anomaly_detector import AnomalyDetector

router    = APIRouter()
_detector = AnomalyDetector()


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

        total_row = fetchone(
            execute(conn, f"SELECT COUNT(*) as cnt FROM api_logs {where}", params)
        )
        total = total_row["cnt"]

        rows = fetchall(
            execute(conn,
                f"SELECT * FROM api_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            )
        )

        return {"total": total, "page": page, "per_page": per_page, "items": rows}
    finally:
        conn.close()


@router.get("/recent")
def get_recent_logs(
    limit:  int = Query(50, ge=1, le=500),
    source: str = None,
):
    conn = get_connection()
    try:
        if source:
            rows = fetchall(
                execute(conn,
                    "SELECT * FROM api_logs WHERE source=? ORDER BY id DESC LIMIT ?",
                    (source, limit),
                )
            )
        else:
            rows = fetchall(
                execute(conn,
                    "SELECT * FROM api_logs ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            )
        return rows
    finally:
        conn.close()


@router.get("/anomalies")
def get_anomalies(
    limit:  int = Query(100, ge=1, le=500),
    source: str = None,
):
    conn = get_connection()
    try:
        if source:
            rows = fetchall(
                execute(conn,
                    "SELECT * FROM api_logs WHERE is_anomaly=1 AND source=? ORDER BY id DESC LIMIT ?",
                    (source, limit),
                )
            )
        else:
            rows = fetchall(
                execute(conn,
                    "SELECT * FROM api_logs WHERE is_anomaly=1 ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            )
        return rows
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

        # strftime works in SQLite; to_char works in PostgreSQL
        # Use a compatible approach: fetch raw timestamps and bucket in Python
        rows = fetchall(
            execute(conn,
                "SELECT timestamp, status_code, latency_ms FROM api_logs "
                "WHERE timestamp >= ? ORDER BY timestamp ASC",
                (cutoff,),
            )
        )

        # Bucket by minute in Python — works for both SQLite and PostgreSQL
        buckets: dict = {}
        for r in rows:
            try:
                ts     = r["timestamp"][:16] + ":00Z"   # 2024-01-01T10:05:00Z
                minute = ts
            except Exception:
                continue

            if minute not in buckets:
                buckets[minute] = {"total": 0, "errors": 0, "latencies": []}

            buckets[minute]["total"] += 1
            if r["status_code"] >= 400:
                buckets[minute]["errors"] += 1
            buckets[minute]["latencies"].append(r["latency_ms"])

        result = []
        for minute in sorted(buckets.keys()):
            b = buckets[minute]
            avg_lat = sum(b["latencies"]) / len(b["latencies"]) if b["latencies"] else 0
            result.append({
                "minute":      minute,
                "total":       b["total"],
                "errors":      b["errors"],
                "avg_latency": round(avg_lat, 1),
            })

        return result
    finally:
        conn.close()


async def _sse_generator(source_filter: str = None):
    """
    Server-Sent Events generator.
    Polls for new log events every second and pushes them instantly.
    """
    last_id = 0
    conn    = get_connection()
    try:
        row     = fetchone(execute(conn, "SELECT MAX(id) as mx FROM api_logs"))
        last_id = row["mx"] or 0
    finally:
        conn.close()

    while True:
        await asyncio.sleep(1)
        conn = get_connection()
        try:
            if source_filter:
                rows = fetchall(
                    execute(conn,
                        "SELECT * FROM api_logs WHERE id > ? AND source=? ORDER BY id ASC LIMIT 20",
                        (last_id, source_filter),
                    )
                )
            else:
                rows = fetchall(
                    execute(conn,
                        "SELECT * FROM api_logs WHERE id > ? ORDER BY id ASC LIMIT 20",
                        (last_id,),
                    )
                )

            for d in rows:
                last_id = d["id"]
                yield f"data: {json.dumps(d)}\n\n"

            yield ": heartbeat\n\n"
        except Exception:
            pass
        finally:
            conn.close()


@router.get("/stream")
async def stream_logs(source: str = None):
    return StreamingResponse(
        _sse_generator(source_filter=source),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )