import asyncio
import logging
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import storage as db
from scraper import get_all_jobs, scrape_linkedin
from matcher import matches

log = logging.getLogger(__name__)

# ── Persistent bottom keyboard ────────────────────────────────────────────────

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Scan Now",     "Wishlist",    "Applied Jobs"],
        ["Stats",        "Digest",      "Search"],
        ["My Filters",   "Blacklist",   "Schedule"],
        ["Location",     "Pause Alerts","Resume"],
        ["Help"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

# ── Safety decorator — wraps every handler so crashes don't kill the bot ──────

def safe(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await func(update, context)
        except Exception as e:
            log.error(f"[{func.__name__}] {e}", exc_info=True)
            try:
                msg = update.effective_message
                if msg:
                    await msg.reply_text(
                        "Something went wrong. Please try again.",
                        reply_markup=MAIN_KEYBOARD,
                    )
            except Exception:
                pass
    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Apply on LinkedIn", url=f"https://www.linkedin.com/jobs/view/{job_id}"),
            InlineKeyboardButton("Save to Wishlist",  callback_data=f"save|{job_id}"),
        ],
        [
            InlineKeyboardButton("Mark as Applied", callback_data=f"applied|{job_id}"),
            InlineKeyboardButton("Skip",            callback_data=f"skip|{job_id}"),
        ],
    ])


def _fmt(job: dict) -> str:
    return (
        f"New Job Match!\n\n"
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )


async def _send_jobs(update: Update, jobs: list):
    """Send job list with rate-limit safe delay between messages."""
    for job in jobs[:10]:
        db.mark_seen(job["id"])
        db.log_job(job["id"], job["title"], job["company"], job["url"])
        await update.message.reply_text(_fmt(job), reply_markup=_job_keyboard(job["id"]))
        await asyncio.sleep(0.4)   # prevents Telegram flood limit


# ── Commands ──────────────────────────────────────────────────────────────────

@safe
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "JobBot is active! Tap any button below.\n\n"
        "Scan Now     - Find new jobs on LinkedIn\n"
        "Wishlist     - Jobs you saved\n"
        "Applied Jobs - Jobs applied + status tracking\n"
        "Stats        - Your job hunt numbers\n"
        "Digest       - Today's job summary\n"
        "Search       - Search any keyword\n"
        "My Filters   - Custom search keywords\n"
        "Blacklist    - Skip certain companies\n"
        "Location     - Change search city\n"
        "Pause/Resume - Toggle job alerts",
        reply_markup=MAIN_KEYBOARD,
    )


@safe
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Button guide:\n\n"
        "Scan Now     - Scan LinkedIn for new jobs\n"
        "Wishlist     - Saved jobs (tap Remove to delete)\n"
        "Applied Jobs - See status: Applied / Interviewing / Offer / Rejected\n"
        "Stats        - Today / this week / total found\n"
        "Digest       - All jobs found today in one message\n"
        "Search       - Then type: /search devops bangalore\n"
        "My Filters   - Keywords added via /addfilter\n"
        "Blacklist    - Companies blocked via /blacklist\n"
        "Location     - Then type: /location Chennai\n"
        "Pause Alerts - Stop auto job notifications\n"
        "Resume       - Turn notifications back on\n\n"
        "Other commands:\n"
        "/addfilter <keyword>     - Add custom keyword\n"
        "/removefilter <keyword>  - Remove keyword\n"
        "/blacklist <company>     - Block a company\n"
        "/unblacklist <company>   - Unblock company\n"
        "/location <city>         - Change location\n"
        "/setstatus <id> <status> - Update job status",
        reply_markup=MAIN_KEYBOARD,
    )


@safe
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.is_paused():
        await update.message.reply_text(
            "Alerts are paused. Tap Resume first.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await update.message.reply_text("Scanning LinkedIn... takes 1-2 minutes.")

    extra    = db.get_filters()
    all_jobs = get_all_jobs(extra_keywords=extra)
    new_jobs = [
        j for j in all_jobs
        if not db.is_seen(j["id"])
        and matches(j)
        and not db.is_blacklisted(j["company"])
    ]

    if not new_jobs:
        await update.message.reply_text(
            "No new matching jobs found right now.\nTry again in a few hours.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await update.message.reply_text(f"Found {len(new_jobs)} new job(s)! Sending...")
    await _send_jobs(update, new_jobs)


@safe
async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_wishlist()
    if not jobs:
        await update.message.reply_text(
            "Your wishlist is empty.\nTap Save to Wishlist on any job alert.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    await update.message.reply_text(f"Saved jobs ({len(jobs)}):", reply_markup=MAIN_KEYBOARD)
    for job_id, title, company, url in jobs[:10]:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Open", url=url),
            InlineKeyboardButton("Remove", callback_data=f"rm_wish|{job_id}"),
        ]])
        await update.message.reply_text(f"{title}\n{company}", reply_markup=kb)
        await asyncio.sleep(0.3)


@safe
async def cmd_applied(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_applied()
    if not jobs:
        await update.message.reply_text(
            "No applied jobs tracked yet.\nTap Mark as Applied on any job alert.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    await update.message.reply_text(f"Applied jobs ({len(jobs)}):", reply_markup=MAIN_KEYBOARD)
    for job_id, title, company, url, applied_at, status in jobs[:10]:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Open", url=url),
                InlineKeyboardButton(f"Status: {status}", callback_data=f"status_menu|{job_id}"),
            ],
            [InlineKeyboardButton("Remove", callback_data=f"rm_applied|{job_id}")],
        ])
        await update.message.reply_text(
            f"Title: {title}\nCompany: {company}\nApplied: {applied_at[:10]}\nStatus: {status}",
            reply_markup=kb,
        )
        await asyncio.sleep(0.3)


@safe
async def cmd_setstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /setstatus <job_id> <status>\n"
            "Statuses: Applied, Interviewing, Offer, Rejected, Withdrawn\n\n"
            "Get job_id from /applied list.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    job_id = context.args[0]
    status = context.args[1].capitalize()
    if status not in db.VALID_STATUSES:
        await update.message.reply_text(
            f"Invalid status. Choose:\n{', '.join(db.VALID_STATUSES)}",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    if db.update_status(job_id, status):
        await update.message.reply_text(f"Status updated to: {status}", reply_markup=MAIN_KEYBOARD)
    else:
        await update.message.reply_text(
            "Job not found in applied list.", reply_markup=MAIN_KEYBOARD
        )


@safe
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.get_stats()
    await update.message.reply_text(
        f"Your Job Stats\n\n"
        f"Today found  : {s['today_found']}\n"
        f"This week    : {s['this_week']}\n"
        f"Total found  : {s['total_found']}\n"
        f"Saved        : {s['wishlist']}\n"
        f"Applied      : {s['applied']}\n",
        reply_markup=MAIN_KEYBOARD,
    )


@safe
async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_today_jobs()
    if not jobs:
        await update.message.reply_text(
            "No jobs found today yet.\nTap Scan Now to check.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    lines = [f"Today's Jobs ({len(jobs)} found)\n"]
    for i, (jid, title, company, url) in enumerate(jobs[:15], 1):
        lines.append(f"{i}. {title} - {company}")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_KEYBOARD)


@safe
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Type your search keyword:\n"
            "/search devops\n"
            "/search network engineer bangalore\n"
            "/search big data",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    keyword = " ".join(context.args)
    await update.message.reply_text(f"Searching: {keyword}...")
    jobs = scrape_linkedin(keyword)
    if not jobs:
        await update.message.reply_text("No results found.", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.reply_text(f"Found {len(jobs)} results:")
    await _send_jobs(update, jobs[:5])


@safe
async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    f = db.get_filters()
    if not f:
        await update.message.reply_text(
            "No custom filters yet.\nUse /addfilter <keyword> to add one.\n\n"
            "Example:\n/addfilter kubernetes\n/addfilter machine learning",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    await update.message.reply_text(
        f"Custom filters ({len(f)}) — tap Remove to delete:",
        reply_markup=MAIN_KEYBOARD,
    )
    for keyword in f:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"Remove: {keyword}", callback_data=f"rm_filter|{keyword}"),
        ]])
        await update.message.reply_text(keyword, reply_markup=kb)
        await asyncio.sleep(0.3)


@safe
async def cmd_addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /addfilter machine learning", reply_markup=MAIN_KEYBOARD)
        return
    kw = " ".join(context.args).lower()
    db.add_filter(kw)
    await update.message.reply_text(f"Added filter: {kw}", reply_markup=MAIN_KEYBOARD)


@safe
async def cmd_removefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removefilter machine learning", reply_markup=MAIN_KEYBOARD)
        return
    kw = " ".join(context.args).lower()
    db.remove_filter(kw)
    await update.message.reply_text(f"Removed: {kw}", reply_markup=MAIN_KEYBOARD)


@safe
async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /blacklist Wipro", reply_markup=MAIN_KEYBOARD)
        return
    co = " ".join(context.args)
    db.add_blacklist(co)
    await update.message.reply_text(f"Blacklisted: {co}", reply_markup=MAIN_KEYBOARD)


@safe
async def cmd_unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unblacklist Wipro", reply_markup=MAIN_KEYBOARD)
        return
    co = " ".join(context.args)
    db.remove_blacklist(co)
    await update.message.reply_text(f"Removed from blacklist: {co}", reply_markup=MAIN_KEYBOARD)


@safe
async def cmd_blacklisted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bl = db.get_blacklist()
    if not bl:
        await update.message.reply_text(
            "No companies blacklisted.\nUse /blacklist <company> to skip them.\n\n"
            "Example:\n/blacklist Wipro\n/blacklist Infosys",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    await update.message.reply_text(
        f"Blacklisted companies ({len(bl)}) — tap Remove to unblock:",
        reply_markup=MAIN_KEYBOARD,
    )
    for company in bl:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"Remove: {company}", callback_data=f"rm_blacklist|{company}"),
        ]])
        await update.message.reply_text(company, reply_markup=kb)
        await asyncio.sleep(0.3)


@safe
async def cmd_setschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        times = db.get_scan_times()
        await update.message.reply_text(
            f"Current scan times (IST): {', '.join(times)}\n\n"
            "To change, type times in HH:MM format:\n"
            "/setschedule 09:00 13:00 18:00\n\n"
            "Bot will scan LinkedIn at these times every day automatically.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    times = [t for t in context.args if ":" in t]
    if not times:
        await update.message.reply_text(
            "Invalid format. Use HH:MM\nExample: /setschedule 09:00 13:00 18:00",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    db.set_setting("scan_times", ",".join(times))
    await update.message.reply_text(
        f"Scan schedule updated!\nWill scan at: {', '.join(times)} IST every day.",
        reply_markup=MAIN_KEYBOARD,
    )


@safe
async def cmd_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        loc = db.get_setting("location", "India")
        await update.message.reply_text(
            f"Current location: {loc}\n\nTo change:\n/location Bangalore\n/location Chennai\n/location Mumbai",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    loc = " ".join(context.args)
    db.set_setting("location", loc)
    await update.message.reply_text(f"Location updated to: {loc}", reply_markup=MAIN_KEYBOARD)


@safe
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.set_setting("paused", True)
    await update.message.reply_text(
        "Job alerts paused.\nTap Resume to turn back on.",
        reply_markup=MAIN_KEYBOARD,
    )


@safe
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.set_setting("paused", False)
    await update.message.reply_text("Job alerts resumed!", reply_markup=MAIN_KEYBOARD)
