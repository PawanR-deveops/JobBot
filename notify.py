import os
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_job_alert(job: dict):
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

    requests.post(f"{API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "reply_markup": keyboard,
    }, timeout=10)


def send_text(msg: str):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
    }, timeout=10)
