"""
PulseDebug AI — Database Layer
================================
File: backend/app/core/database.py
Purpose:
    Supports both SQLite (local development) and PostgreSQL (production).
    The DATABASE_URL environment variable controls which is used.

    If DATABASE_URL is set:
        Uses PostgreSQL via psycopg2.
        Suitable for Neon, Render PostgreSQL, Railway, Azure, AWS RDS.

    If DATABASE_URL is not set:
        Falls back to SQLite at backend/data/pulsedebug.db.
        Suitable for local development and demos.

    All existing tables and queries are preserved exactly.
    The only change is the connection mechanism and placeholder syntax.

    SQLite uses  ?  as placeholder.
    PostgreSQL uses  %s  as placeholder.
    This module handles the difference transparently.

Author: PulseDebug AI Hackathon Team
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Detect database mode from environment
# ---------------------------------------------------------------------------

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL", "").strip() or None
USING_POSTGRES: bool        = DATABASE_URL is not None

if USING_POSTGRES:
    import psycopg2
    import psycopg2.extras
    print(f"[DB] Using PostgreSQL")
else:
    SQLITE_PATH = Path(__file__).parent.parent.parent / "data" / "pulsedebug.db"
    print(f"[DB] Using SQLite at {SQLITE_PATH}")


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection():
    """
    Return a database connection.
    For PostgreSQL: psycopg2 connection with RealDictCursor (row-as-dict).
    For SQLite: sqlite3 connection with Row factory.
    Both behave identically from the caller's perspective.
    """
    if USING_POSTGRES:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        conn.autocommit = False
        return conn
    else:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


# ---------------------------------------------------------------------------
# SQL dialect adapter
# ---------------------------------------------------------------------------

def adapt_sql(sql: str) -> str:
    """
    Convert SQLite-style ? placeholders to PostgreSQL-style %s.
    Called automatically on every query when using PostgreSQL.
    """
    if USING_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def execute(conn, sql: str, params=None):
    """
    Execute a SQL statement with automatic placeholder adaptation.
    Returns the cursor so callers can use .fetchone(), .fetchall(), .lastrowid.
    """
    adapted = adapt_sql(sql)
    if USING_POSTGRES:
        cur = conn.cursor()
        cur.execute(adapted, params or ())
        return cur
    else:
        return conn.execute(adapted, params or ())


def commit(conn):
    conn.commit()


def fetchone(cursor):
    """Return one row as a plain dict regardless of database backend."""
    row = cursor.fetchone()
    if row is None:
        return None
    if USING_POSTGRES:
        return dict(row)
    return dict(row)


def fetchall(cursor):
    """Return all rows as plain dicts regardless of database backend."""
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def lastrowid(cursor) -> int:
    """
    Return the ID of the last inserted row.
    PostgreSQL does not support cursor.lastrowid — use RETURNING id instead.
    SQLite supports lastrowid directly.
    """
    if USING_POSTGRES:
        row = cursor.fetchone()
        if row:
            return row.get("id") or row.get(list(row.keys())[0])
        return None
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

# PostgreSQL-compatible CREATE TABLE statements
# Key differences from SQLite version:
#   - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
#   - DEFAULT (datetime('now'))          → DEFAULT NOW()
#   - No PRAGMA statements

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_logs (
    id          SERIAL PRIMARY KEY,
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
    created_at  TEXT    NOT NULL DEFAULT NOW()::TEXT
);

CREATE TABLE IF NOT EXISTS incidents (
    id                 SERIAL PRIMARY KEY,
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
    ai_confidence      REAL,
    ai_fix_commands    TEXT,
    created_at         TEXT    NOT NULL DEFAULT NOW()::TEXT,
    updated_at         TEXT    NOT NULL DEFAULT NOW()::TEXT
);

CREATE TABLE IF NOT EXISTS deployments (
    id          SERIAL PRIMARY KEY,
    version     TEXT    NOT NULL,
    service     TEXT    NOT NULL,
    deployed_at TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'success',
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT NOW()::TEXT
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id          SERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL,
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    detail      TEXT,
    created_at  TEXT    NOT NULL DEFAULT NOW()::TEXT
);

CREATE TABLE IF NOT EXISTS incident_correlations (
    id            SERIAL PRIMARY KEY,
    from_incident INTEGER NOT NULL,
    to_incident   INTEGER NOT NULL,
    relation_type TEXT    NOT NULL DEFAULT 'caused_by',
    confidence    REAL    NOT NULL DEFAULT 0.8,
    created_at    TEXT    NOT NULL DEFAULT NOW()::TEXT
);
"""

_SQLITE_SCHEMA = """
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
);

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
    ai_confidence      REAL,
    ai_fix_commands    TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deployments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version     TEXT    NOT NULL,
    service     TEXT    NOT NULL,
    deployed_at TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'success',
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    detail      TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS incident_correlations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_incident INTEGER NOT NULL,
    to_incident   INTEGER NOT NULL,
    relation_type TEXT    NOT NULL DEFAULT 'caused_by',
    confidence    REAL    NOT NULL DEFAULT 0.8,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# Migration additions for existing SQLite databases
_SQLITE_MIGRATIONS = [
    "ALTER TABLE api_logs ADD COLUMN source TEXT NOT NULL DEFAULT 'demo'",
    "ALTER TABLE incidents ADD COLUMN source TEXT NOT NULL DEFAULT 'demo'",
    "ALTER TABLE incidents ADD COLUMN ai_confidence REAL",
    "ALTER TABLE incidents ADD COLUMN ai_fix_commands TEXT",
]


def init_db() -> None:
    """Create all tables. Safe to call multiple times — uses IF NOT EXISTS."""
    conn = get_connection()
    try:
        if USING_POSTGRES:
            cur = conn.cursor()
            cur.execute(_PG_SCHEMA)
            conn.commit()
            print("[DB] PostgreSQL schema initialised")
        else:
            # SQLite — run full schema
            conn.executescript(_SQLITE_SCHEMA)
            # Run migrations for columns added after initial release
            for migration in _SQLITE_MIGRATIONS:
                try:
                    conn.execute(migration)
                    conn.commit()
                except Exception:
                    pass  # Column already exists
            print("[DB] SQLite schema initialised")
    finally:
        conn.close()