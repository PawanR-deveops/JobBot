import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from apply import easy_apply

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)


def build_app() -> Application:
    return Application.builder().token(TELEGRAM_TOKEN).build()


async def send_job_alert(app: Application, job: dict):
    text = (
        f"*New Job Match Found!*\n\n"
        f"*{job['title']}*\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("Auto Fill & Apply", callback_data=f"apply|{job['id']}|{job['url']}"),
            InlineKeyboardButton("Open on LinkedIn", url=job["url"]),
        ],
        [InlineKeyboardButton("Skip", callback_data=f"skip|{job['id']}")],
    ]

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|")
    action = parts[0]

    if action == "apply":
        _, job_id, url = parts
        await query.edit_message_text(
            f"Opening Easy Apply for job `{job_id}`...\n"
            f"Browser will open. Review the form and click *Submit* yourself.",
            parse_mode="Markdown",
        )

        result = await easy_apply(url)

        msg = {
            "ready": "Form filled! Please review in the browser and click Submit.",
            "not_available": "Easy Apply not available for this job.",
            "error": "Something went wrong. Try opening the job link manually.",
        }.get(result, "Unknown result.")

        await context.bot.send_message(chat_id=query.message.chat_id, text=msg)

    elif action == "skip":
        await query.edit_message_text("Job skipped.")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Job Bot is running!\n\n"
        "/scan — scan LinkedIn now\n"
        "/status — bot status\n\n"
        "Auto-scan runs every 3 hours in the background."
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Scanning LinkedIn... this may take 1-2 minutes.")
    from scraper import get_new_jobs
    from matcher import matches

    jobs = get_new_jobs()
    matched = [j for j in jobs if matches(j)]

    if not matched:
        await update.message.reply_text("No new matching jobs found right now.")
        return

    await update.message.reply_text(f"Found {len(matched)} new job(s). Sending alerts...")
    for job in matched[:10]:
        await send_job_alert(context.application, job)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import sqlite3
    from db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
    conn.close()
    await update.message.reply_text(f"Bot active. Total jobs tracked in DB: {count}")
