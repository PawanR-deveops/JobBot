"""
JSON-based persistent storage. Each write auto-commits back to the GitHub repo
so data survives across GitHub Actions runs without any external database.
"""

import json
import os
import subprocess
from datetime import datetime, date, timedelta

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def _path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.json")


def _load(name: str, default):
    p = _path(name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def _save(name: str, data):
    with open(_path(name), "w") as f:
        json.dump(data, f, indent=2)
    _commit(name)


def _commit(name: str):
    try:
        subprocess.run(["git", "add", _path(name)], capture_output=True)
        diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if diff.returncode != 0:
            subprocess.run(["git", "commit", "-m", f"bot: update {name}"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
    except Exception as e:
        print(f"[storage] git error: {e}")


# ── Wishlist ──────────────────────────────────────────────────────────────────

def add_wishlist(job_id, title, company, url):
    data = _load("wishlist", {})
    data[job_id] = {"title": title, "company": company, "url": url, "saved_at": datetime.now().isoformat()}
    _save("wishlist", data)


def remove_wishlist(job_id):
    data = _load("wishlist", {})
    data.pop(job_id, None)
    _save("wishlist", data)


def get_wishlist():
    data = _load("wishlist", {})
    return [(jid, v["title"], v["company"], v["url"]) for jid, v in data.items()]


# ── Applied ───────────────────────────────────────────────────────────────────

VALID_STATUSES = ["Applied", "Interviewing", "Offer", "Rejected", "Withdrawn"]


def mark_applied(job_id, title, company, url):
    data = _load("applied", {})
    data[job_id] = {
        "title": title, "company": company, "url": url,
        "applied_at": datetime.now().isoformat(),
        "status": "Applied",
    }
    _save("applied", data)


def update_status(job_id, status):
    data = _load("applied", {})
    if job_id in data:
        data[job_id]["status"] = status
        _save("applied", data)
        return True
    return False


def remove_applied(job_id):
    data = _load("applied", {})
    data.pop(job_id, None)
    _save("applied", data)


def get_applied():
    data = _load("applied", {})
    return [
        (jid, v["title"], v["company"], v["url"], v["applied_at"], v.get("status", "Applied"))
        for jid, v in data.items()
    ]


# ── Filters (permanent until manually removed) ────────────────────────────────

def add_filter(keyword):
    data = _load("filters", [])
    if keyword.lower() not in data:
        data.append(keyword.lower())
    _save("filters", data)


def remove_filter(keyword):
    data = _load("filters", [])
    _save("filters", [k for k in data if k != keyword.lower()])


def get_filters():
    return _load("filters", [])


# ── Blacklist (permanent until manually removed) ──────────────────────────────

def add_blacklist(company):
    data = _load("blacklist", [])
    if company.lower() not in data:
        data.append(company.lower())
    _save("blacklist", data)


def remove_blacklist(company):
    data = _load("blacklist", [])
    _save("blacklist", [c for c in data if c != company.lower()])


def get_blacklist():
    return _load("blacklist", [])


def is_blacklisted(company: str) -> bool:
    return any(b in company.lower() for b in get_blacklist())


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key, default=None):
    return _load("settings", {}).get(key, default)


def set_setting(key, value):
    data = _load("settings", {})
    data[key] = value
    _save("settings", data)


def is_paused() -> bool:
    return get_setting("paused", False)


def get_scan_times() -> list[str]:
    """Returns list of HH:MM strings for preferred scan times."""
    raw = get_setting("scan_times", "09:00,13:00,18:00")
    return [t.strip() for t in raw.split(",") if t.strip()]


# ── Daily job log (keeps only today — auto-cleanup) ───────────────────────────

def log_job(job_id, title, company, url):
    today = date.today().isoformat()
    data  = {today: _load("daily_jobs", {}).get(today, {})}   # keep ONLY today
    data[today][job_id] = {"title": title, "company": company, "url": url}
    _save("daily_jobs", data)


def get_today_jobs():
    data  = _load("daily_jobs", {})
    today = data.get(date.today().isoformat(), {})
    return [(jid, v["title"], v["company"], v["url"]) for jid, v in today.items()]


# ── Seen jobs — 7-day expiry (same job re-alerts after a week if still open) ──

def is_seen(job_id: str) -> bool:
    data = _load("seen_jobs_list", {})
    if job_id not in data:
        return False
    seen_at = datetime.fromisoformat(data[job_id])
    return (datetime.now() - seen_at) < timedelta(days=7)


def mark_seen(job_id: str):
    data   = _load("seen_jobs_list", {})
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    # Prune expired entries
    data   = {k: v for k, v in data.items() if v >= cutoff}
    data[job_id] = datetime.now().isoformat()
    _save("seen_jobs_list", data)


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    wishlist = _load("wishlist", {})
    applied  = _load("applied", {})
    daily    = _load("daily_jobs", {})
    today    = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    return {
        "total_found": sum(len(v) for v in daily.values()),
        "today_found": len(daily.get(today, {})),
        "this_week":   sum(len(v) for k, v in daily.items() if k >= week_ago),
        "wishlist":    len(wishlist),
        "applied":     len(applied),
    }
