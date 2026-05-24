"""
PulseDebug AI — Database Layer
================================
File: backend/app/core/database.py
Purpose:
    Creates and manages the SQLite database used for persisting API log
    events, detected incidents, and deployment records.

    SQLite is used here intentionally — it is 100% free, requires no
    external service, and is more than sufficient for a hackathon demo
    that does not need multi-process write concurrency.

    Tables created:
        api_logs        — individual API request/response events
        incidents       — clustered failure groups
        deployments     — deployment metadata events

Author: PulseDebug AI Hackathon Team
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pulsedebug.db"


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with Row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

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
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

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
            ai_summary         TEXT,
            ai_root_cause      TEXT,
            ai_checks          TEXT,
            ai_priority        TEXT,
            ai_model_used      TEXT,
            created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

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

    conn.commit()
    conn.close()
    print(f"[DB] Initialised SQLite database at {DB_PATH}")