"""
Runs as a one-shot GitHub Actions job for the daily digest (9 AM IST).
Sends today's job summary to each approved user via Telegram HTTP API.
"""

import os
import requests

import storage as db
import user_auth as auth

TOKEN = os.environ["TELEGRAM_TOKEN"]
API   = f"https://api.telegram.org/bot{TOKEN}"


def send(chat_id: str, text: str):
    try:
        requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"[digest] send error → {chat_id}: {e}")


def main():
    all_users = auth.get_all_users()
    if not all_users:
        print("[digest] No approved users")
        return

    for uid in all_users:
        jobs = db.get_today_jobs(uid)
        s    = db.get_stats(uid)

        if not jobs:
            msg = "Daily Digest: No new jobs found today. Tap Scan Now to check."
        else:
            lines = [f"Daily Digest\n{len(jobs)} jobs found today\n"]
            for i, (jid, title, company, url) in enumerate(jobs[:15], 1):
                lines.append(f"{i}. {title} - {company}")
            lines.append(f"\nTotal applied so far: {s['applied']}")
            msg = "\n".join(lines)

        send(uid, msg)
        print(f"[digest] Sent to {uid}")


if __name__ == "__main__":
    main()
