import logging
import pytz
from datetime import time as dtime

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config_bot import TELEGRAM_TOKEN
from database import init_db
from commands import (
    cmd_start, cmd_help, cmd_scan, cmd_wishlist, cmd_applied,
    cmd_stats, cmd_digest, cmd_search,
    cmd_filters, cmd_addfilter, cmd_removefilter,
    cmd_blacklist, cmd_unblacklist, cmd_blacklisted,
    cmd_location, cmd_pause, cmd_resume,
)
from callbacks import handle_callback
from scheduler_jobs import daily_digest, weekly_stats

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

IST = pytz.timezone("Asia/Kolkata")


def main():
    init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(CommandHandler("scan",          cmd_scan))
    app.add_handler(CommandHandler("wishlist",      cmd_wishlist))
    app.add_handler(CommandHandler("applied",       cmd_applied))
    app.add_handler(CommandHandler("stats",         cmd_stats))
    app.add_handler(CommandHandler("digest",        cmd_digest))
    app.add_handler(CommandHandler("search",        cmd_search))
    app.add_handler(CommandHandler("filters",       cmd_filters))
    app.add_handler(CommandHandler("addfilter",     cmd_addfilter))
    app.add_handler(CommandHandler("removefilter",  cmd_removefilter))
    app.add_handler(CommandHandler("blacklist",     cmd_blacklist))
    app.add_handler(CommandHandler("unblacklist",   cmd_unblacklist))
    app.add_handler(CommandHandler("blacklisted",   cmd_blacklisted))
    app.add_handler(CommandHandler("location",      cmd_location))
    app.add_handler(CommandHandler("pause",         cmd_pause))
    app.add_handler(CommandHandler("resume",        cmd_resume))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Scheduled jobs
    app.job_queue.run_daily(
        daily_digest,
        time=dtime(9, 0, tzinfo=IST),       # 9:00 AM IST every day
    )
    app.job_queue.run_daily(
        weekly_stats,
        time=dtime(10, 0, tzinfo=IST),      # 10:00 AM IST
        days=(6,),                           # Sunday only
    )

    logging.info("JobBot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
