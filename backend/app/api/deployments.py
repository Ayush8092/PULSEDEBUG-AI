"""
PulseDebug AI — Deployments API Router
=========================================
File: backend/app/api/deployments.py
Purpose:
    Deployment event endpoints.
    Updated to use database.execute(), fetchone(), fetchall() helpers
    for PostgreSQL and SQLite compatibility.

Author: PulseDebug AI Hackathon Team
"""

from fastapi import APIRouter, HTTPException, Query
from app.core.database import get_connection, execute, fetchone, fetchall

router = APIRouter()


@router.get("")
def list_deployments(limit: int = Query(20, ge=1, le=100)):
    conn = get_connection()
    try:
        rows = fetchall(
            execute(conn,
                "SELECT * FROM deployments ORDER BY deployed_at DESC LIMIT ?",
                (limit,),
            )
        )
        return rows
    finally:
        conn.close()


@router.get("/recent")
def recent_deployments(limit: int = Query(5, ge=1, le=20)):
    conn = get_connection()
    try:
        rows = fetchall(
            execute(conn,
                "SELECT * FROM deployments ORDER BY deployed_at DESC LIMIT ?",
                (limit,),
            )
        )
        result = []
        for d in rows:
            count_row = fetchone(
                execute(conn,
                    "SELECT COUNT(*) as cnt FROM incidents WHERE deployment_id = ?",
                    (d["id"],),
                )
            )
            d["linked_incident_count"] = count_row["cnt"] if count_row else 0
            result.append(d)
        return result
    finally:
        conn.close()


@router.get("/{deployment_id}")
def get_deployment(deployment_id: int):
    conn = get_connection()
    try:
        row = fetchone(
            execute(conn, "SELECT * FROM deployments WHERE id = ?", (deployment_id,))
        )
        if not row:
            raise HTTPException(status_code=404, detail="Deployment not found")

        incidents = fetchall(
            execute(conn,
                "SELECT id, title, severity, status, occurrence_count "
                "FROM incidents WHERE deployment_id = ?",
                (deployment_id,),
            )
        )
        row["incidents"] = incidents
        return row
    finally:
        conn.close()