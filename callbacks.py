import logging
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage as db
import user_auth as auth
from commands import _keyboard, MAIN_KEYBOARD

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

    uid    = str(query.from_user.id)
    parts  = query.data.split("|")
    action = parts[0]
    arg1   = parts[1] if len(parts) > 1 else ""
    arg2   = parts[2] if len(parts) > 2 else ""
    url    = f"https://www.linkedin.com/jobs/view/{arg1}"
    text   = query.message.text or ""
    title, company = _parse_job(text)

    # ── Admin: approve / deny ──────────────────────────────────────────────
    if action == "approve":
        target_id = arg1
        info      = auth.get_pending().get(target_id, {})
        auth.approve_user(target_id)
        await query.edit_message_text(f"Approved: {info.get('name','User')} ({target_id})")
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="Your access has been approved! Send /start to begin.",
            )
        except Exception:
            pass

    elif action == "deny":
        target_id = arg1
        info      = auth.get_pending().get(target_id, {})
        auth.deny_user(target_id)
        await query.edit_message_text(f"Denied: {info.get('name','User')} ({target_id})")
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="Your access request was not approved at this time.",
            )
        except Exception:
            pass

    # ── Job actions ────────────────────────────────────────────────────────
    elif action == "save":
        db.add_wishlist(uid, arg1, title, company, url)
        await query.edit_message_text(
            f"{text}\nSaved to wishlist!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Apply on LinkedIn", url=url),
                InlineKeyboardButton("Mark as Applied", callback_data=f"applied|{arg1}"),
            ]]),
        )

    elif action == "applied":
        db.mark_applied(uid, arg1, title, company, url)
        await query.edit_message_text(
            f"{text}\nMarked as applied!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Apply on LinkedIn", url=url),
                InlineKeyboardButton("Update Status", callback_data=f"status_menu|{arg1}"),
            ]]),
        )

    elif action == "skip":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("Skipped.")

    elif action == "rm_wish":
        db.remove_wishlist(uid, arg1)
        await query.edit_message_text(f"{text}\nRemoved from wishlist.")

    elif action == "rm_applied":
        db.remove_applied(uid, arg1)
        await query.edit_message_text(f"{text}\nRemoved from applied list.")

    elif action == "status_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(s, callback_data=f"set_status|{arg1}|{s}")]
            for s in STATUSES
        ])
        await query.edit_message_text(f"{text}\n\nSelect new status:", reply_markup=kb)

    elif action == "set_status":
        db.update_status(uid, arg1, arg2)
        updated = "\n".join(
            f"Status: {arg2}" if line.startswith("Status:") else line
            for line in text.splitlines()
            if not line.startswith("Select new status")
        )
        await query.edit_message_text(
            updated,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Change Status", callback_data=f"status_menu|{arg1}"),
            ]]),
        )

    elif action == "rm_filter":
        db.remove_filter(uid, arg1)
        await query.edit_message_text(f"Removed filter: {arg1}")

    elif action == "rm_blacklist":
        db.remove_blacklist(uid, arg1)
        await query.edit_message_text(f"Removed from blacklist: {arg1}")
