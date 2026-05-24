from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import storage as db

STATUSES = ["Applied", "Interviewing", "Offer", "Rejected", "Withdrawn"]


def _parse_job(text: str) -> tuple[str, str]:
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

    parts  = query.data.split("|")
    action = parts[0]
    job_id = parts[1] if len(parts) > 1 else ""
    url    = f"https://www.linkedin.com/jobs/view/{job_id}"
    title, company = _parse_job(query.message.text or "")

    if action == "save":
        db.add_wishlist(job_id, title, company, url)
        await query.edit_message_text(
            f"{query.message.text}\nSaved to wishlist!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Apply on LinkedIn", url=url),
                InlineKeyboardButton("Mark as Applied", callback_data=f"applied|{job_id}"),
            ]]),
        )

    elif action == "applied":
        db.mark_applied(job_id, title, company, url)
        await query.edit_message_text(f"{query.message.text}\nMarked as applied!")

    elif action == "skip":
        await query.message.delete()

    elif action == "rm_wish":
        db.remove_wishlist(job_id)
        await query.edit_message_text(f"{query.message.text}\nRemoved from wishlist.")

    elif action == "rm_applied":
        db.remove_applied(job_id)
        await query.edit_message_text(f"{query.message.text}\nRemoved from applied list.")

    elif action == "status_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(s, callback_data=f"set_status|{job_id}|{s}")]
            for s in STATUSES
        ])
        await query.edit_message_text(
            f"{query.message.text}\n\nSelect new status:",
            reply_markup=kb,
        )

    elif action == "set_status":
        new_status = parts[2] if len(parts) > 2 else "Applied"
        db.update_status(job_id, new_status)
        await query.edit_message_text(
            "\n".join(
                line if not line.startswith("Status:") else f"Status: {new_status}"
                for line in (query.message.text or "").splitlines()
            )
        )
