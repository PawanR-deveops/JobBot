import logging
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage as db
from commands import MAIN_KEYBOARD

log = logging.getLogger(__name__)

STATUSES = ["Applied", "Interviewing", "Offer", "Rejected", "Withdrawn"]


def safe_callback(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await func(update, context)
        except Exception as e:
            log.error(f"[callback] {e}", exc_info=True)
            try:
                await update.callback_query.answer("Something went wrong. Please try again.")
            except Exception:
                pass
    return wrapper


def _parse_job(text: str) -> tuple[str, str]:
    title, company = "Unknown", "Unknown"
    for line in (text or "").splitlines():
        if line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
        elif line.startswith("Company:"):
            company = line.replace("Company:", "").strip()
    return title, company


@safe_callback
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()

    parts  = query.data.split("|")
    action = parts[0]
    job_id = parts[1] if len(parts) > 1 else ""
    url    = f"https://www.linkedin.com/jobs/view/{job_id}"
    text   = query.message.text or ""
    title, company = _parse_job(text)

    if action == "save":
        db.add_wishlist(job_id, title, company, url)
        await query.edit_message_text(
            f"{text}\nSaved to wishlist!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Apply on LinkedIn", url=url),
                InlineKeyboardButton("Mark as Applied", callback_data=f"applied|{job_id}"),
            ]]),
        )

    elif action == "applied":
        db.mark_applied(job_id, title, company, url)
        await query.edit_message_text(
            f"{text}\nMarked as applied!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Apply on LinkedIn", url=url),
                InlineKeyboardButton("Update Status", callback_data=f"status_menu|{job_id}"),
            ]]),
        )

    elif action == "skip":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("Skipped.")

    elif action == "rm_wish":
        db.remove_wishlist(job_id)
        await query.edit_message_text(f"{text}\nRemoved from wishlist.")

    elif action == "rm_applied":
        db.remove_applied(job_id)
        await query.edit_message_text(f"{text}\nRemoved from applied list.")

    elif action == "status_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(s, callback_data=f"set_status|{job_id}|{s}")]
            for s in STATUSES
        ])
        await query.edit_message_text(
            f"{text}\n\nSelect new status:",
            reply_markup=kb,
        )

    elif action == "set_status":
        new_status = parts[2] if len(parts) > 2 else "Applied"
        db.update_status(job_id, new_status)
        updated = "\n".join(
            f"Status: {new_status}" if line.startswith("Status:") else line
            for line in text.splitlines()
            if not line.startswith("Select new status")
        )
        await query.edit_message_text(
            updated,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Change Status", callback_data=f"status_menu|{job_id}"),
            ]]),
        )

    elif action == "rm_filter":
        keyword = parts[1] if len(parts) > 1 else ""
        db.remove_filter(keyword)
        await query.edit_message_text(f"Removed filter: {keyword}")

    elif action == "rm_blacklist":
        company = parts[1] if len(parts) > 1 else ""
        db.remove_blacklist(company)
        await query.edit_message_text(f"Removed from blacklist: {company}")
