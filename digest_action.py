"""
Runs as a one-shot GitHub Actions job for the daily digest.
Sends today's job summary to Telegram via HTTP (no running bot needed).
"""
import os
import requests
import storage as db

TOKEN   = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API     = f"https://api.telegram.org/bot{TOKEN}"


def send(text: str):
    requests.post(f"{API}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)


def main():
    jobs = db.get_today_jobs()
    s    = db.get_stats()

    if not jobs:
        send("Daily Digest: No new jobs found today. Use /scan to check manually.")
        return

    lines = [f"Daily Digest\n{len(jobs)} jobs found today\n"]
    for i, (jid, title, company, url) in enumerate(jobs[:15], 1):
        lines.append(f"{i}. {title} - {company}")

    lines.append(f"\nTotal applied so far: {s['applied']}")
    send("\n".join(lines))


if __name__ == "__main__":
    main()
