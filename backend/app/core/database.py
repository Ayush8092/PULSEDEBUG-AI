"""
PulseDebug AI — Database Layer
================================
File: backend/app/core/database.py
Purpose:
    Creates and manages the SQLite database.
    Upgrade additions:
        - source column on api_logs (demo / external / manual)
        - timeline_events table for incident lifecycle replay
        - incident_correlations table for root-cause chain graph
        - deployments table unchanged

Author: PulseDebug AI Hackathon Team
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pulsedebug.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    # api_logs — added source column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            service     TEXT    NOT NULL,
            endpoint    TEXT    NOT NULL,
            method      TEXT    NOT NULL DEFAULT 'GET',
            status_code INTEGER NOT NULL,
            latency_ms  INTEGER NOT NULL,
            error_type  TEXT,
            error_msg   TEXT,
            is_anomaly  INTEGER NOT NULL DEFAULT 0,
            scenario    TEXT,
            source      TEXT    NOT NULL DEFAULT 'demo',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Add source column if it doesn't exist (migration for existing DBs)
    try:
        cursor.execute("ALTER TABLE api_logs ADD COLUMN source TEXT NOT NULL DEFAULT 'demo'")
        conn.commit()
    except Exception:
        pass

    # incidents — added source column and ai_confidence
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            title              TEXT    NOT NULL,
            service            TEXT    NOT NULL,
            endpoint           TEXT    NOT NULL,
            error_signature    TEXT    NOT NULL,
            severity           TEXT    NOT NULL DEFAULT 'warning',
            status             TEXT    NOT NULL DEFAULT 'open',
            occurrence_count   INTEGER NOT NULL DEFAULT 1,
            first_detected     TEXT    NOT NULL,
            last_seen          TEXT    NOT NULL,
            deployment_id      INTEGER,
            deployment_related INTEGER NOT NULL DEFAULT 0,
            source             TEXT    NOT NULL DEFAULT 'demo',
            ai_summary         TEXT,
            ai_root_cause      TEXT,
            ai_checks          TEXT,
            ai_priority        TEXT,
            ai_model_used      TEXT,
            ai_confidence      REAL    DEFAULT NULL,
            ai_fix_commands    TEXT,
            created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Add new columns to incidents if they don't exist
    for col_def in [
        ("source",          "TEXT NOT NULL DEFAULT 'demo'"),
        ("ai_confidence",   "REAL DEFAULT NULL"),
        ("ai_fix_commands", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE incidents ADD COLUMN {col_def[0]} {col_def[1]}")
            conn.commit()
        except Exception:
            pass

    # deployments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deployments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            version     TEXT    NOT NULL,
            service     TEXT    NOT NULL,
            deployed_at TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'success',
            notes       TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # timeline_events — incident lifecycle replay
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            timestamp   TEXT    NOT NULL,
            event_type  TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            detail      TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        )
    """)

    # incident_correlations — root-cause chain graph
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incident_correlations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            from_incident INTEGER NOT NULL,
            to_incident   INTEGER NOT NULL,
            relation_type TEXT    NOT NULL DEFAULT 'caused_by',
            confidence    REAL    NOT NULL DEFAULT 0.8,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialised database at {DB_PATH}")