"""
database.py — SQLite persistence layer.

Tables:
  emails      – one row per email (raw data + AI analysis)
  agent_runs  – audit log of every agent execution
"""

import sqlite3
import logging
from typing import Dict, List, Optional

from src.config import DATABASE_PATH

logger = logging.getLogger(__name__)


# ── Connection ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_database():
    """Create all tables and indexes (idempotent)."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS emails (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                uid          TEXT    UNIQUE NOT NULL,
                imap_id      TEXT,
                sender       TEXT    NOT NULL,
                subject      TEXT    NOT NULL,
                body         TEXT,
                date         TEXT,
                -- AI-generated fields
                category     TEXT    DEFAULT 'Uncategorized',
                urgency      TEXT    DEFAULT 'Low',
                summary      TEXT,
                action       TEXT    DEFAULT 'keep',
                folder       TEXT,
                key_info     TEXT,
                reasoning    TEXT,
                -- Status flags
                is_processed INTEGER DEFAULT 0,
                is_actioned  INTEGER DEFAULT 0,
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                updated_at   TEXT    DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at           TEXT    DEFAULT CURRENT_TIMESTAMP,
                emails_fetched   INTEGER DEFAULT 0,
                emails_analyzed  INTEGER DEFAULT 0,
                emails_actioned  INTEGER DEFAULT 0,
                status           TEXT    DEFAULT 'success',
                error_message    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_emails_uid       ON emails(uid);
            CREATE INDEX IF NOT EXISTS idx_emails_category  ON emails(category);
            CREATE INDEX IF NOT EXISTS idx_emails_urgency   ON emails(urgency);
            CREATE INDEX IF NOT EXISTS idx_emails_processed ON emails(is_processed);
            CREATE INDEX IF NOT EXISTS idx_emails_date      ON emails(date DESC);
        """)
    logger.info("Database ready: %s", DATABASE_PATH)


# ── Email CRUD ────────────────────────────────────────────────────────────────

def email_exists(uid: str) -> bool:
    """Return True if we already have this email UID in the database."""
    with _conn() as con:
        row = con.execute("SELECT 1 FROM emails WHERE uid = ?", (uid,)).fetchone()
        return row is not None


def upsert_email(data: Dict):
    """
    Insert a new email row, or silently skip if the UID already exists.

    Expected keys: uid, imap_id, sender, subject, body, date
    """
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO emails (uid, imap_id, sender, subject, body, date)
            VALUES (:uid, :imap_id, :sender, :subject, :body, :date)
            """,
            data,
        )


def update_analysis(uid: str, analysis: Dict):
    """Store AI analysis results for an existing email row."""
    with _conn() as con:
        con.execute(
            """
            UPDATE emails
               SET category     = :category,
                   urgency      = :urgency,
                   summary      = :summary,
                   action       = :action,
                   folder       = :folder,
                   key_info     = :key_info,
                   reasoning    = :reasoning,
                   is_processed = 1,
                   updated_at   = CURRENT_TIMESTAMP
             WHERE uid = :uid
            """,
            {**analysis, "uid": uid},
        )


def mark_actioned(uid: str):
    """Set is_actioned = 1 for an email (after archive / move action)."""
    with _conn() as con:
        con.execute(
            "UPDATE emails SET is_actioned = 1, updated_at = CURRENT_TIMESTAMP WHERE uid = ?",
            (uid,),
        )


# ── Queries ───────────────────────────────────────────────────────────────────

def get_emails(
    category: Optional[str] = None,
    urgency: Optional[str] = None,
    is_processed: Optional[bool] = None,
    limit: int = 200,
) -> List[Dict]:
    """Fetch emails with optional filters, newest first."""
    sql    = "SELECT * FROM emails WHERE 1=1"
    params: List = []

    if category and category != "All":
        sql += " AND category = ?"
        params.append(category)
    if urgency and urgency != "All":
        sql += " AND urgency = ?"
        params.append(urgency)
    if is_processed is not None:
        sql += " AND is_processed = ?"
        params.append(1 if is_processed else 0)

    sql += " ORDER BY date DESC LIMIT ?"
    params.append(limit)

    with _conn() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_email_by_uid(uid: str) -> Optional[Dict]:
    """Return a single email row by UID, or None."""
    with _conn() as con:
        row = con.execute("SELECT * FROM emails WHERE uid = ?", (uid,)).fetchone()
    return dict(row) if row else None


def get_stats() -> Dict:
    """Return aggregate counts for the dashboard header."""
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

        cat_rows = con.execute(
            "SELECT category, COUNT(*) FROM emails GROUP BY category"
        ).fetchall()

        urg_rows = con.execute(
            "SELECT urgency, COUNT(*) FROM emails GROUP BY urgency"
        ).fetchall()

        high_unactioned = con.execute(
            "SELECT COUNT(*) FROM emails WHERE urgency='High' AND is_actioned=0"
        ).fetchone()[0]

        unprocessed = con.execute(
            "SELECT COUNT(*) FROM emails WHERE is_processed=0"
        ).fetchone()[0]

        last_run = con.execute(
            "SELECT run_at, emails_fetched FROM agent_runs ORDER BY run_at DESC LIMIT 1"
        ).fetchone()

    return {
        "total":               total,
        "by_category":        {r[0]: r[1] for r in cat_rows},
        "by_urgency":         {r[0]: r[1] for r in urg_rows},
        "high_unactioned":    high_unactioned,
        "unprocessed":        unprocessed,
        "last_run":           dict(last_run) if last_run else None,
    }


# ── Agent run log ─────────────────────────────────────────────────────────────

def log_agent_run(
    fetched: int,
    analyzed: int,
    actioned: int,
    status: str = "success",
    error: Optional[str] = None,
):
    with _conn() as con:
        con.execute(
            """
            INSERT INTO agent_runs
                (emails_fetched, emails_analyzed, emails_actioned, status, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (fetched, analyzed, actioned, status, error),
        )
