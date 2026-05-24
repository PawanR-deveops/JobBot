"""
GitHub Actions entry point — runs every 30 minutes.
Scrapes LinkedIn once, then sends personalized alerts to each approved user
based on their scan window, filters, and blacklist settings.
"""

import os
from datetime import datetime
import pytz
import requests

import storage as db
import user_auth as auth
from scraper import get_all_jobs
from matcher import matches

IST   = pytz.timezone("Asia/Kolkata")
TOKEN = os.environ["TELEGRAM_TOKEN"]
API   = f"https://api.telegram.org/bot{TOKEN}"


def _send(chat_id: str, text: str, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    try:
        requests.post(f"{API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"[scan] send error → {chat_id}: {e}")


def send_job_alert(chat_id: str, job: dict):
    job_id = job["id"]
    text = (
        f"New Job Match!\n\n"
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Apply on LinkedIn", "url": f"https://www.linkedin.com/jobs/view/{job_id}"},
                {"text": "Save to Wishlist",  "callback_data": f"save|{job_id}"},
            ],
            [
                {"text": "Mark as Applied",   "callback_data": f"applied|{job_id}"},
                {"text": "Skip",              "callback_data": f"skip|{job_id}"},
            ],
        ]
    }
    _send(chat_id, text, keyboard)


def in_scan_window(uid: str) -> bool:
    now_ist   = datetime.now(IST)
    now_total = now_ist.hour * 60 + now_ist.minute
    for t in db.get_scan_times(uid):
        try:
            hh, mm = map(int, t.split(":"))
            if abs(now_total - hh * 60 - mm) <= 35:
                return True
        except ValueError:
            continue
    return False


def main():
    all_users = auth.get_all_users()
    if not all_users:
        print("[scan] No approved users — nothing to do")
        return

    # Collect all users' extra keywords so we scrape once
    all_extra: set[str] = set()
    for uid in all_users:
        all_extra.update(db.get_filters(uid))

    print(f"[scan] Scraping ({len(all_extra)} extra keywords)...")
    all_jobs = get_all_jobs(extra_keywords=list(all_extra))
    print(f"[scan] Total jobs scraped: {len(all_jobs)}")

    for uid in all_users:
        if db.is_paused(uid):
            print(f"[scan] {uid} paused — skip")
            continue

        if not in_scan_window(uid):
            print(f"[scan] {uid} not in scan window — skip")
            continue

        new_jobs = [
            j for j in all_jobs
            if not db.is_seen(uid, j["id"])
            and matches(j)
            and not db.is_blacklisted(uid, j["company"])
        ]

        print(f"[scan] {uid}: {len(new_jobs)} new jobs")
        if not new_jobs:
            continue

        _send(uid, f"Found {len(new_jobs)} new matching job(s)!")
        for job in new_jobs[:10]:
            send_job_alert(uid, job)
            db.mark_seen(uid, job["id"])
            db.log_job(uid, job["id"], job["title"], job["company"], job["url"])

    print("[scan] Done")


if __name__ == "__main__":
    main()
