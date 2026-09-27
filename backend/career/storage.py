"""Small SQLite repository for reload-safe Career Coach candidate sessions."""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path


log = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "priya_career.db"
_configured_path = os.getenv("PRIYA_CAREER_DB")
DB_PATH = Path(_configured_path).expanduser() if _configured_path else DEFAULT_DB_PATH
_announced_path: Path | None = None


class CareerStorageError(RuntimeError):
    """Raised when Career Coach cannot open either supported SQLite location."""


def _connect(path: Path) -> sqlite3.Connection:
    """Create the parent directory, open SQLite, and preserve the existing schema."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS candidate_sessions ("
            "id TEXT PRIMARY KEY, profile TEXT NOT NULL, analysis TEXT NOT NULL, "
            "job TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.commit()
        # Opening an existing read-only SQLite file can succeed. Verify this
        # location accepts writes before selecting it as the active database.
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()
        return conn
    except sqlite3.Error:
        conn.close()
        raise


def _announce_database(path: Path) -> None:
    global _announced_path
    if _announced_path != path:
        log.info("[CAREER] Using career database: %s", path)
        _announced_path = path


def _db() -> sqlite3.Connection:
    """Open the configured database, falling back safely to repository data/."""
    global DB_PATH
    try:
        conn = _connect(DB_PATH)
    except (OSError, sqlite3.Error) as configured_error:
        if DB_PATH == DEFAULT_DB_PATH:
            raise CareerStorageError("Career Coach storage is unavailable.") from configured_error

        log.warning(
            "[CAREER] Configured database path unavailable; falling back to local "
            "data/priya_career.db"
        )
        try:
            conn = _connect(DEFAULT_DB_PATH)
        except (OSError, sqlite3.Error) as fallback_error:
            raise CareerStorageError("Career Coach storage is unavailable.") from fallback_error
        DB_PATH = DEFAULT_DB_PATH

    _announce_database(DB_PATH)
    return conn


def save(candidate_id: str, profile: dict, analysis: dict, job: dict | None = None) -> None:
    """Persist structured profile and analysis only; never raw resume PDF/text."""
    now = datetime.utcnow().isoformat()
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO candidate_sessions VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET profile=excluded.profile, "
                "analysis=excluded.analysis, job=COALESCE(excluded.job, "
                "candidate_sessions.job), updated_at=excluded.updated_at",
                (
                    candidate_id,
                    json.dumps(profile),
                    json.dumps(analysis),
                    json.dumps(job) if job else None,
                    now,
                    now,
                ),
            )
    except sqlite3.Error as error:
        raise CareerStorageError("Career Coach storage is unavailable.") from error


def load(candidate_id: str) -> dict | None:
    try:
        with _db() as conn:
            row = conn.execute(
                "SELECT profile, analysis, job FROM candidate_sessions WHERE id=?",
                (candidate_id,),
            ).fetchone()
    except sqlite3.Error as error:
        raise CareerStorageError("Career Coach storage is unavailable.") from error
    if not row:
        return None
    return {
        "profile": json.loads(row[0]),
        "resume_analysis": json.loads(row[1]),
        "job": json.loads(row[2]) if row[2] else None,
    }
