import asyncio
import datetime
import logging
import os

import pytz
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

from commands import (
    cmd_start, cmd_help, cmd_scan, cmd_wishlist, cmd_applied,
    cmd_stats, cmd_digest, cmd_search,
    cmd_filters, cmd_addfilter, cmd_removefilter,
    cmd_blacklist, cmd_unblacklist, cmd_blacklisted,
    cmd_location, cmd_pause, cmd_resume,
    cmd_setstatus, cmd_setschedule,
    cmd_users, cmd_pending, cmd_ban,
    _keyboard, _fmt, _job_keyboard,
)
from callbacks import handle_callback

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
IST = pytz.timezone("Asia/Kolkata")

BUTTON_MAP = {
    "Scan Now":     cmd_scan,
    "Wishlist":     cmd_wishlist,
    "Applied Jobs": cmd_applied,
    "Stats":        cmd_stats,
    "Digest":       cmd_digest,
    "My Filters":   cmd_filters,
    "Blacklist":    cmd_blacklisted,
    "Pause Alerts": cmd_pause,
    "Resume":       cmd_resume,
    "Help":         cmd_help,
    "Schedule":     cmd_setschedule,
    "Users":        cmd_users,
    "Pending":      cmd_pending,
}

PROMPT_MAP = {
    "Search":   "Type your search:\n/search devops\n/search network engineer bangalore",
    "Location": "Change location:\n/location Bangalore\n/location Chennai\n/location Mumbai",
}


# ── Scheduled job: auto-scan every 30 minutes ─────────────────────────────────

async def auto_scan_job(context: ContextTypes.DEFAULT_TYPE):
    import storage as db
    import user_auth as auth
    from scraper import get_all_jobs
    from matcher import matches

    all_users = auth.get_all_users()
    if not all_users:
        return

    now_ist   = datetime.datetime.now(IST)
    now_total = now_ist.hour * 60 + now_ist.minute

    all_extra: set[str] = set()
    for uid in all_users:
        all_extra.update(db.get_filters(uid))

    all_jobs = get_all_jobs(extra_keywords=list(all_extra))
    log.info(f"[auto_scan] {len(all_jobs)} jobs scraped")

    for uid in all_users:
        if db.is_paused(uid):
            continue

        in_window = False
        for t in db.get_scan_times(uid):
            try:
                hh, mm = map(int, t.split(":"))
                if abs(now_total - hh * 60 - mm) <= 35:
                    in_window = True
                    break
            except ValueError:
                continue

        if not in_window:
            continue

        new_jobs = [
            j for j in all_jobs
            if not db.is_seen(uid, j["id"])
            and matches(j)
            and not db.is_blacklisted(uid, j["company"])
        ]

        if not new_jobs:
            continue

        log.info(f"[auto_scan] {uid}: sending {len(new_jobs)} jobs")
        await context.bot.send_message(
            chat_id=uid,
            text=f"Found {len(new_jobs)} new matching job(s)!"
        )

        for job in new_jobs[:10]:
            db.mark_seen(uid, job["id"])
            db.log_job(uid, job["id"], job["title"], job["company"], job["url"])
            await context.bot.send_message(
                chat_id=uid,
                text=_fmt(job),
                reply_markup=_job_keyboard(job["id"]),
            )
            await asyncio.sleep(0.4)


# ── Scheduled job: daily digest at 9 AM IST ───────────────────────────────────

async def daily_digest_job(context: ContextTypes.DEFAULT_TYPE):
    import storage as db
    import user_auth as auth

    for uid in auth.get_all_users():
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

        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            log.warning(f"[digest] {uid}: {e}")


# ── Message handlers ──────────────────────────────────────────────────────────

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in BUTTON_MAP:
        await BUTTON_MAP[text](update, context)
    elif text in PROMPT_MAP:
        uid = str(update.effective_user.id)
        await update.message.reply_text(PROMPT_MAP[text], reply_markup=_keyboard(uid))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Unhandled error: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            uid = str(update.effective_user.id) if update.effective_user else "0"
            await update.effective_message.reply_text(
                "Something went wrong. Please try again.",
                reply_markup=_keyboard(uid),
            )
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("scan",         cmd_scan))
    app.add_handler(CommandHandler("wishlist",     cmd_wishlist))
    app.add_handler(CommandHandler("applied",      cmd_applied))
    app.add_handler(CommandHandler("stats",        cmd_stats))
    app.add_handler(CommandHandler("digest",       cmd_digest))
    app.add_handler(CommandHandler("search",       cmd_search))
    app.add_handler(CommandHandler("filters",      cmd_filters))
    app.add_handler(CommandHandler("addfilter",    cmd_addfilter))
    app.add_handler(CommandHandler("removefilter", cmd_removefilter))
    app.add_handler(CommandHandler("blacklist",    cmd_blacklist))
    app.add_handler(CommandHandler("unblacklist",  cmd_unblacklist))
    app.add_handler(CommandHandler("blacklisted",  cmd_blacklisted))
    app.add_handler(CommandHandler("location",     cmd_location))
    app.add_handler(CommandHandler("pause",        cmd_pause))
    app.add_handler(CommandHandler("resume",       cmd_resume))
    app.add_handler(CommandHandler("setstatus",    cmd_setstatus))
    app.add_handler(CommandHandler("setschedule",  cmd_setschedule))
    app.add_handler(CommandHandler("users",        cmd_users))
    app.add_handler(CommandHandler("pending",      cmd_pending))
    app.add_handler(CommandHandler("ban",          cmd_ban))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button))
    app.add_error_handler(error_handler)

    # Scheduled jobs
    app.job_queue.run_repeating(
        auto_scan_job,
        interval=1800,   # every 30 minutes
        first=60,        # first run after 60s on startup
    )
    app.job_queue.run_daily(
        daily_digest_job,
        time=datetime.time(hour=9, minute=0, tzinfo=IST),
    )

    log.info("JobHunt India Bot started — auto-scan every 30 min, digest at 9 AM IST")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
