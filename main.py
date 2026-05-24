import logging
import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from commands import (
    cmd_start, cmd_help, cmd_scan, cmd_wishlist, cmd_applied,
    cmd_stats, cmd_digest, cmd_search,
    cmd_filters, cmd_addfilter, cmd_removefilter,
    cmd_blacklist, cmd_unblacklist, cmd_blacklisted,
    cmd_location, cmd_pause, cmd_resume,
)
from callbacks import handle_callback

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

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
    app.add_handler(CallbackQueryHandler(handle_callback))

    logging.info("JobBot polling started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
