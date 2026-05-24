import sqlite3
from datetime import datetime

DB_PATH = "jobs.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id   TEXT PRIMARY KEY,
            title    TEXT,
            company  TEXT,
            location TEXT,
            url      TEXT,
            seen_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def is_seen(job_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
    result = c.fetchone()
    conn.close()
    return result is not None


def mark_seen(job_id: str, title: str, company: str, location: str, url: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO seen_jobs VALUES (?,?,?,?,?,?)",
        (job_id, title, company, location, url, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
