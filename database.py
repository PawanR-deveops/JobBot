import sqlite3
from datetime import datetime, date

DB_PATH = "jobbot.db"


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS wishlist (
                job_id   TEXT PRIMARY KEY,
                title    TEXT,
                company  TEXT,
                url      TEXT,
                saved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS applied_jobs (
                job_id     TEXT PRIMARY KEY,
                title      TEXT,
                company    TEXT,
                url        TEXT,
                applied_at TEXT
            );
            CREATE TABLE IF NOT EXISTS extra_filters (
                keyword TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS blacklist (
                company TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS daily_jobs (
                job_id     TEXT,
                title      TEXT,
                company    TEXT,
                url        TEXT,
                found_date TEXT,
                PRIMARY KEY (job_id, found_date)
            );
            INSERT OR IGNORE INTO settings VALUES ('paused',   '0');
            INSERT OR IGNORE INTO settings VALUES ('location', 'India');
        """)


# --- Settings ---

def get_setting(key, default=None):
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default


def set_setting(key, value):
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))


def is_paused():
    return get_setting("paused") == "1"


# --- Wishlist ---

def add_wishlist(job_id, title, company, url):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO wishlist VALUES (?,?,?,?,?)",
            (job_id, title, company, url, datetime.now().isoformat()),
        )


def remove_wishlist(job_id):
    with _conn() as conn:
        conn.execute("DELETE FROM wishlist WHERE job_id=?", (job_id,))


def get_wishlist():
    with _conn() as conn:
        return conn.execute(
            "SELECT job_id,title,company,url FROM wishlist ORDER BY saved_at DESC"
        ).fetchall()


# --- Applied ---

def mark_applied(job_id, title, company, url):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO applied_jobs VALUES (?,?,?,?,?)",
            (job_id, title, company, url, datetime.now().isoformat()),
        )


def get_applied():
    with _conn() as conn:
        return conn.execute(
            "SELECT job_id,title,company,url,applied_at FROM applied_jobs ORDER BY applied_at DESC"
        ).fetchall()


# --- Filters ---

def add_filter(keyword):
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO extra_filters VALUES (?)", (keyword.lower(),))


def remove_filter(keyword):
    with _conn() as conn:
        conn.execute("DELETE FROM extra_filters WHERE keyword=?", (keyword.lower(),))


def get_filters():
    with _conn() as conn:
        return [r[0] for r in conn.execute("SELECT keyword FROM extra_filters").fetchall()]


# --- Blacklist ---

def add_blacklist(company):
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO blacklist VALUES (?)", (company.lower(),))


def remove_blacklist(company):
    with _conn() as conn:
        conn.execute("DELETE FROM blacklist WHERE company=?", (company.lower(),))


def get_blacklist():
    with _conn() as conn:
        return [r[0] for r in conn.execute("SELECT company FROM blacklist").fetchall()]


def is_blacklisted(company):
    bl = get_blacklist()
    return any(b in company.lower() for b in bl)


# --- Daily jobs log ---

def log_job(job_id, title, company, url):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO daily_jobs VALUES (?,?,?,?,?)",
            (job_id, title, company, url, date.today().isoformat()),
        )


def get_today_jobs():
    with _conn() as conn:
        return conn.execute(
            "SELECT job_id,title,company,url FROM daily_jobs WHERE found_date=?",
            (date.today().isoformat(),),
        ).fetchall()


# --- Stats ---

def get_stats():
    with _conn() as conn:
        return {
            "total_found":  conn.execute("SELECT COUNT(DISTINCT job_id) FROM daily_jobs").fetchone()[0],
            "today_found":  conn.execute("SELECT COUNT(*) FROM daily_jobs WHERE found_date=?", (date.today().isoformat(),)).fetchone()[0],
            "wishlist":     conn.execute("SELECT COUNT(*) FROM wishlist").fetchone()[0],
            "applied":      conn.execute("SELECT COUNT(*) FROM applied_jobs").fetchone()[0],
            "this_week":    conn.execute("SELECT COUNT(DISTINCT job_id) FROM daily_jobs WHERE found_date >= date('now','-7 days')").fetchone()[0],
        }
