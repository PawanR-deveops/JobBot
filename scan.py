import json
import os

from scraper import get_all_jobs
from matcher import matches
from notify import send_job_alert, send_text

SEEN_FILE = "seen_jobs.json"


def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE) as f:
        return set(json.load(f))


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def main():
    seen = load_seen()
    print(f"[scan] {len(seen)} jobs already seen")

    all_jobs = get_all_jobs()
    new_matched = [j for j in all_jobs if j["id"] not in seen and matches(j)]

    print(f"[scan] {len(new_matched)} new matching jobs found")

    if not new_matched:
        print("[scan] Nothing new to send")
        return

    send_text(f"Found {len(new_matched)} new job(s) matching your profile!")

    for job in new_matched[:10]:
        send_job_alert(job)
        seen.add(job["id"])

    save_seen(seen)
    print("[scan] Done")


if __name__ == "__main__":
    main()
