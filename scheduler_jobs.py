"""
PTB JobQueue callbacks — daily digest and weekly stats.
Registered in main.py via app.job_queue.run_daily / run_repeating.
(Active scheduling is handled in main.py; this file is kept for reference.)
"""

import logging
from datetime import datetime
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)


async def daily_digest(context: ContextTypes.DEFAULT_TYPE):
    import storage as db
    import user_auth as auth

    for uid in auth.get_all_users():
        jobs = db.get_today_jobs(uid)
        s    = db.get_stats(uid)

        if not jobs:
            msg = "Daily Digest: No new jobs found today. Tap Scan Now to check."
        else:
            lines = [f"Daily Digest - {datetime.now().strftime('%d %b %Y')}\n{len(jobs)} jobs found today\n"]
            for i, (jid, title, company, url) in enumerate(jobs[:15], 1):
                lines.append(f"{i}. {title} at {company}")
            lines.append(f"\nTotal applied so far: {s['applied']}")
            msg = "\n".join(lines)

        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            log.warning(f"[digest] {uid}: {e}")


async def weekly_stats(context: ContextTypes.DEFAULT_TYPE):
    import storage as db
    import user_auth as auth

    for uid in auth.get_all_users():
        s = db.get_stats(uid)
        msg = (
            f"Weekly Report\n\n"
            f"This week found: {s['this_week']}\n"
            f"Total found:     {s['total_found']}\n"
            f"Saved:           {s['wishlist']}\n"
            f"Applied:         {s['applied']}\n\n"
            f"Keep going! Use /scan anytime to check new listings."
        )
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            log.warning(f"[weekly_stats] {uid}: {e}")
