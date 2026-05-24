"""
Per-user JSON storage. All data is isolated under data/users/{user_id}/.
Global data (settings shared across bot) lives in data/global/.
Each write auto-commits to GitHub so data persists across Actions runs.
"""

import json
import os
import subprocess
from datetime import datetime, date, timedelta

DATA_DIR = "data"

VALID_STATUSES = ["Applied", "Interviewing", "Offer", "Rejected", "Withdrawn"]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _udir(user_id: str) -> str:
    path = os.path.join(DATA_DIR, "users", str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def _upath(user_id: str, name: str) -> str:
    return os.path.join(_udir(user_id), f"{name}.json")


def _gpath(name: str) -> str:
    gdir = os.path.join(DATA_DIR, "global")
    os.makedirs(gdir, exist_ok=True)
    return os.path.join(gdir, f"{name}.json")


def _load(path: str, default):
    return json.load(open(path)) if os.path.exists(path) else default


def _save(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    _commit(path)


def _commit(path: str):
    try:
        subprocess.run(["git", "add", path], capture_output=True)
        if subprocess.run(["git", "diff", "--staged", "--quiet"]).returncode != 0:
            subprocess.run(["git", "commit", "-m", f"bot: update {os.path.basename(path)}"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
    except Exception as e:
        print(f"[storage] git error: {e}")


# ── Wishlist ──────────────────────────────────────────────────────────────────

def add_wishlist(uid, job_id, title, company, url):
    p = _upath(uid, "wishlist")
    d = _load(p, {})
    d[job_id] = {"title": title, "company": company, "url": url, "saved_at": datetime.now().isoformat()}
    _save(p, d)


def remove_wishlist(uid, job_id):
    p = _upath(uid, "wishlist")
    d = _load(p, {})
    d.pop(job_id, None)
    _save(p, d)


def get_wishlist(uid):
    d = _load(_upath(uid, "wishlist"), {})
    return [(jid, v["title"], v["company"], v["url"]) for jid, v in d.items()]


# ── Applied ───────────────────────────────────────────────────────────────────

def mark_applied(uid, job_id, title, company, url):
    p = _upath(uid, "applied")
    d = _load(p, {})
    d[job_id] = {"title": title, "company": company, "url": url,
                 "applied_at": datetime.now().isoformat(), "status": "Applied"}
    _save(p, d)


def update_status(uid, job_id, status):
    p = _upath(uid, "applied")
    d = _load(p, {})
    if job_id in d:
        d[job_id]["status"] = status
        _save(p, d)
        return True
    return False


def remove_applied(uid, job_id):
    p = _upath(uid, "applied")
    d = _load(p, {})
    d.pop(job_id, None)
    _save(p, d)


def get_applied(uid):
    d = _load(_upath(uid, "applied"), {})
    return [(jid, v["title"], v["company"], v["url"], v["applied_at"], v.get("status", "Applied"))
            for jid, v in d.items()]


# ── Filters (permanent per user) ──────────────────────────────────────────────

def add_filter(uid, keyword):
    p = _upath(uid, "filters")
    d = _load(p, [])
    if keyword.lower() not in d:
        d.append(keyword.lower())
    _save(p, d)


def remove_filter(uid, keyword):
    p = _upath(uid, "filters")
    _save(p, [k for k in _load(p, []) if k != keyword.lower()])


def get_filters(uid):
    return _load(_upath(uid, "filters"), [])


# ── Blacklist (permanent per user) ────────────────────────────────────────────

def add_blacklist(uid, company):
    p = _upath(uid, "blacklist")
    d = _load(p, [])
    if company.lower() not in d:
        d.append(company.lower())
    _save(p, d)


def remove_blacklist(uid, company):
    p = _upath(uid, "blacklist")
    _save(p, [c for c in _load(p, []) if c != company.lower()])


def get_blacklist(uid):
    return _load(_upath(uid, "blacklist"), [])


def is_blacklisted(uid, company: str) -> bool:
    return any(b in company.lower() for b in get_blacklist(uid))


# ── Per-user settings ─────────────────────────────────────────────────────────

def get_setting(uid, key, default=None):
    return _load(_upath(uid, "settings"), {}).get(key, default)


def set_setting(uid, key, value):
    p = _upath(uid, "settings")
    d = _load(p, {})
    d[key] = value
    _save(p, d)


def is_paused(uid) -> bool:
    return get_setting(uid, "paused", False)


def get_scan_times(uid) -> list[str]:
    raw = get_setting(uid, "scan_times", "09:00,13:00,18:00")
    return [t.strip() for t in raw.split(",") if t.strip()]


# ── Seen jobs — 7-day expiry ──────────────────────────────────────────────────

def is_seen(uid, job_id: str) -> bool:
    p = _upath(uid, "seen_jobs")
    d = _load(p, {})
    if job_id not in d:
        return False
    return (datetime.now() - datetime.fromisoformat(d[job_id])) < timedelta(days=7)


def mark_seen(uid, job_id: str):
    p      = _upath(uid, "seen_jobs")
    d      = _load(p, {})
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    d      = {k: v for k, v in d.items() if v >= cutoff}
    d[job_id] = datetime.now().isoformat()
    _save(p, d)


# ── Daily job log (today only) ────────────────────────────────────────────────

def log_job(uid, job_id, title, company, url):
    p     = _upath(uid, "daily_jobs")
    today = date.today().isoformat()
    d     = {today: _load(p, {}).get(today, {})}
    d[today][job_id] = {"title": title, "company": company, "url": url}
    _save(p, d)


def get_today_jobs(uid):
    d     = _load(_upath(uid, "daily_jobs"), {})
    today = d.get(date.today().isoformat(), {})
    return [(jid, v["title"], v["company"], v["url"]) for jid, v in today.items()]


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats(uid) -> dict:
    wishlist = _load(_upath(uid, "wishlist"), {})
    applied  = _load(_upath(uid, "applied"), {})
    daily    = _load(_upath(uid, "daily_jobs"), {})
    today    = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    return {
        "today_found": len(daily.get(today, {})),
        "this_week":   sum(len(v) for k, v in daily.items() if k >= week_ago),
        "total_found": sum(len(v) for v in daily.values()),
        "wishlist":    len(wishlist),
        "applied":     len(applied),
    }
