import asyncio
import threading
import time
import logging
from telegram.ext import CommandHandler, CallbackQueryHandler
from bot import build_app, send_job_alert, handle_callback, cmd_start, cmd_scan, cmd_status
from scraper import get_new_jobs
from matcher import matches
from db import init_db
from config import SCRAPE_INTERVAL_HOURS, TELEGRAM_CHAT_ID

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)


def scheduler_loop(app):
    """Background thread: scan every SCRAPE_INTERVAL_HOURS hours."""
    while True:
        time.sleep(SCRAPE_INTERVAL_HOURS * 3600)
        logging.info("[scheduler] Running auto-scan...")

        try:
            jobs = get_new_jobs()
            matched = [j for j in jobs if matches(j)]
            logging.info(f"[scheduler] {len(matched)} new matching jobs found")

            for job in matched[:10]:
                asyncio.run(send_job_alert(app, job))

        except Exception as e:
            logging.error(f"[scheduler] Error: {e}")


def main():
    init_db()

    app = build_app()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(handle_callback))

    t = threading.Thread(target=scheduler_loop, args=(app,), daemon=True)
    t.start()

    logging.info("Bot started! Polling for messages...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
