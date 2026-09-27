"""Small SQLite repository for reload-safe Career Coach candidate sessions."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "priya_career.db"

def _db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS candidate_sessions (id TEXT PRIMARY KEY, profile TEXT NOT NULL, analysis TEXT NOT NULL, job TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    return conn

def save(candidate_id: str, profile: dict, analysis: dict, job: dict | None = None) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        conn.execute("INSERT INTO candidate_sessions VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET profile=excluded.profile, analysis=excluded.analysis, job=COALESCE(excluded.job,candidate_sessions.job), updated_at=excluded.updated_at", (candidate_id, json.dumps(profile), json.dumps(analysis), json.dumps(job) if job else None, now, now))

def load(candidate_id: str) -> dict | None:
    with _db() as conn: row = conn.execute("SELECT profile, analysis, job FROM candidate_sessions WHERE id=?", (candidate_id,)).fetchone()
    if not row: return None
    return {"profile": json.loads(row[0]), "resume_analysis": json.loads(row[1]), "job": json.loads(row[2]) if row[2] else None}
