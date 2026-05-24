from datetime import datetime
from telegram.ext import ContextTypes

from database import get_today_jobs, get_stats, is_paused
from config_bot import TELEGRAM_CHAT_ID


async def daily_digest(context: ContextTypes.DEFAULT_TYPE):
    if is_paused():
        return

    jobs = get_today_jobs()
    if not jobs:
        msg = "Daily Digest: No new jobs found today."
    else:
        lines = [f"Daily Digest - {datetime.now().strftime('%d %b %Y')}\n{len(jobs)} jobs found today\n"]
        for i, (job_id, title, company, url) in enumerate(jobs[:15], 1):
            lines.append(f"{i}. {title} at {company}")
        msg = "\n".join(lines)

    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)


async def weekly_stats(context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    msg = (
        f"Weekly Report\n\n"
        f"This week found: {s['this_week']}\n"
        f"Total found:     {s['total_found']}\n"
        f"Saved:           {s['wishlist']}\n"
        f"Applied:         {s['applied']}\n\n"
        f"Keep going! Use /scan anytime to check new listings."
    )
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
