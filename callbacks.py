from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    add_wishlist, remove_wishlist,
    mark_applied, remove_blacklist,
)


def _parse_job_from_text(text: str) -> tuple[str, str]:
    title, company = "Unknown", "Unknown"
    for line in (text or "").splitlines():
        if line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
        elif line.startswith("Company:"):
            company = line.replace("Company:", "").strip()
    return title, company


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|")
    action = parts[0]
    job_id = parts[1] if len(parts) > 1 else ""
    url = f"https://www.linkedin.com/jobs/view/{job_id}"

    msg_text = query.message.text or ""
    title, company = _parse_job_from_text(msg_text)

    if action == "save":
        add_wishlist(job_id, title, company, url)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Apply on LinkedIn", url=url),
            InlineKeyboardButton("Mark as Applied", callback_data=f"applied|{job_id}"),
        ]])
        await query.edit_message_text(
            f"{msg_text}\nSaved to wishlist!",
            reply_markup=keyboard,
        )

    elif action == "applied":
        mark_applied(job_id, title, company, url)
        await query.edit_message_text(
            f"{msg_text}\nMarked as applied!",
        )

    elif action == "skip":
        await query.message.delete()

    elif action == "rm_wish":
        remove_wishlist(job_id)
        await query.edit_message_text(f"{msg_text}\nRemoved from wishlist.")

    elif action == "rm_applied":
        from database import get_applied
        import sqlite3
        from database import DB_PATH, _conn
        with _conn() as conn:
            conn.execute("DELETE FROM applied_jobs WHERE job_id=?", (job_id,))
        await query.edit_message_text(f"{msg_text}\nRemoved from applied list.")
