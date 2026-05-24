import os
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_job_alert(job: dict):
    text = (
        f"*New Job Match!*\n\n"
        f"*{job['title']}*\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "Open on LinkedIn", "url": job["url"]}
        ]]
    }

    requests.post(f"{API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
        "disable_web_page_preview": False,
    }, timeout=10)


def send_text(msg: str):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
    }, timeout=10)
