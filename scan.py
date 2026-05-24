"""
GitHub Actions entry point — runs on schedule, checks user's preferred scan
times (IST), skips if not in a valid window, then scrapes and notifies.
"""

import os
from datetime import datetime
import pytz

import storage as db
from scraper import get_all_jobs
from matcher import matches
from notify import send_job_alert, send_text

IST = pytz.timezone("Asia/Kolkata")


def is_within_scan_window() -> bool:
    """Returns True if current IST hour:minute is within 30 min of a preferred scan time."""
    now_ist   = datetime.now(IST)
    now_total = now_ist.hour * 60 + now_ist.minute

    for t in db.get_scan_times():
        try:
            hh, mm = map(int, t.split(":"))
            target = hh * 60 + mm
            if abs(now_total - target) <= 35:   # ±35 min window
                return True
        except ValueError:
            continue
    return False


def main():
    if db.is_paused():
        print("[scan] Paused — skipping")
        return

    if not is_within_scan_window():
        from datetime import datetime
        now = datetime.now(IST).strftime("%H:%M")
        times = ", ".join(db.get_scan_times())
        print(f"[scan] Current time {now} IST not in scan window ({times}) — skipping")
        return

    extra    = db.get_filters()
    all_jobs = get_all_jobs(extra_keywords=extra)
    new_jobs = [
        j for j in all_jobs
        if not db.is_seen(j["id"])
        and matches(j)
        and not db.is_blacklisted(j["company"])
    ]

    print(f"[scan] {len(new_jobs)} new matching jobs found")

    if not new_jobs:
        print("[scan] Nothing new to send")
        return

    send_text(f"Found {len(new_jobs)} new matching job(s)!")

    for job in new_jobs[:10]:
        send_job_alert(job)
        db.mark_seen(job["id"])
        db.log_job(job["id"], job["title"], job["company"], job["url"])

    print("[scan] Done")


if __name__ == "__main__":
    main()
