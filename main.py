import logging
import os
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
    _keyboard,
)
from callbacks import handle_callback

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

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


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .concurrent_updates(True)
        .build()
    )

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

    log.info("JobHunt India Bot started")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
