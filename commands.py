from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage as db
from scraper import get_all_jobs, scrape_linkedin
from matcher import matches


def _job_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Apply on LinkedIn", url=f"https://www.linkedin.com/jobs/view/{job_id}"),
            InlineKeyboardButton("Save to Wishlist",  callback_data=f"save|{job_id}"),
        ],
        [
            InlineKeyboardButton("Mark as Applied",   callback_data=f"applied|{job_id}"),
            InlineKeyboardButton("Skip",              callback_data=f"skip|{job_id}"),
        ],
    ])


def _fmt(job: dict) -> str:
    return (
        f"New Job Match!\n\n"
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "JobBot is active!\n\n"
        "/scan              - Scan LinkedIn now\n"
        "/wishlist          - Saved jobs\n"
        "/applied           - Jobs you applied to\n"
        "/stats             - Your stats\n"
        "/digest            - Today's job summary\n"
        "/search <keyword>  - Search any keyword\n"
        "/addfilter <kw>    - Add custom keyword\n"
        "/removefilter <kw> - Remove keyword\n"
        "/filters           - Show your filters\n"
        "/blacklist <co>    - Skip a company\n"
        "/unblacklist <co>  - Remove from blacklist\n"
        "/blacklisted       - Show blacklisted companies\n"
        "/location <city>   - Change location\n"
        "/pause             - Pause alerts\n"
        "/resume            - Resume alerts\n"
        "/help              - Show this menu"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.is_paused():
        await update.message.reply_text("Alerts are paused. Use /resume first.")
        return

    await update.message.reply_text("Scanning LinkedIn... takes 1-2 minutes.")

    bl      = db.get_blacklist()
    extra   = db.get_filters()
    all_jobs = get_all_jobs(extra_keywords=extra)
    new_jobs = [
        j for j in all_jobs
        if not db.is_seen(j["id"]) and matches(j) and not db.is_blacklisted(j["company"])
    ]

    if not new_jobs:
        await update.message.reply_text("No new matching jobs found right now.")
        return

    await update.message.reply_text(f"Found {len(new_jobs)} new job(s)!")
    for job in new_jobs[:10]:
        db.mark_seen(job["id"])
        db.log_job(job["id"], job["title"], job["company"], job["url"])
        await update.message.reply_text(_fmt(job), reply_markup=_job_keyboard(job["id"]))


async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_wishlist()
    if not jobs:
        await update.message.reply_text("Your wishlist is empty.")
        return
    await update.message.reply_text(f"Saved jobs ({len(jobs)}):")
    for job_id, title, company, url in jobs[:10]:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Open", url=url),
            InlineKeyboardButton("Remove", callback_data=f"rm_wish|{job_id}"),
        ]])
        await update.message.reply_text(f"{title}\n{company}", reply_markup=kb)


STATUS_EMOJI = {
    "Applied":      "Sent",
    "Interviewing": "Interview",
    "Offer":        "Offer",
    "Rejected":     "Rejected",
    "Withdrawn":    "Withdrawn",
}


async def cmd_applied(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_applied()
    if not jobs:
        await update.message.reply_text("No applied jobs tracked yet.")
        return
    await update.message.reply_text(f"Applied jobs ({len(jobs)}):")
    for job_id, title, company, url, applied_at, status in jobs[:10]:
        label = STATUS_EMOJI.get(status, status)
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Open", url=url),
                InlineKeyboardButton(f"Status: {label}", callback_data=f"status_menu|{job_id}"),
            ],
            [InlineKeyboardButton("Remove", callback_data=f"rm_applied|{job_id}")],
        ])
        await update.message.reply_text(
            f"Title: {title}\nCompany: {company}\nApplied: {applied_at[:10]}\nStatus: {status}",
            reply_markup=kb,
        )


async def cmd_setstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /setstatus <job_id> <status>\n\n"
            "Statuses: Applied, Interviewing, Offer, Rejected, Withdrawn\n\n"
            "Tip: Use /applied to see job IDs."
        )
        return
    job_id = context.args[0]
    status = context.args[1].capitalize()
    if status not in db.VALID_STATUSES:
        await update.message.reply_text(f"Invalid status. Choose: {', '.join(db.VALID_STATUSES)}")
        return
    if db.update_status(job_id, status):
        await update.message.reply_text(f"Status updated to: {status}")
    else:
        await update.message.reply_text("Job not found. Use /applied to see your job IDs.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.get_stats()
    await update.message.reply_text(
        f"Your Job Stats\n\n"
        f"Today found  : {s['today_found']}\n"
        f"This week    : {s['this_week']}\n"
        f"Total found  : {s['total_found']}\n"
        f"Saved        : {s['wishlist']}\n"
        f"Applied      : {s['applied']}\n"
    )


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_today_jobs()
    if not jobs:
        await update.message.reply_text("No jobs found today yet. Use /scan to check now.")
        return
    lines = [f"Today's Jobs ({len(jobs)} found)\n"]
    for i, (jid, title, company, url) in enumerate(jobs[:15], 1):
        lines.append(f"{i}. {title} - {company}")
    await update.message.reply_text("\n".join(lines))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /search devops bangalore")
        return
    keyword = " ".join(context.args)
    await update.message.reply_text(f"Searching: {keyword}...")
    jobs = scrape_linkedin(keyword)
    if not jobs:
        await update.message.reply_text("No results found.")
        return
    await update.message.reply_text(f"Found {len(jobs)} results:")
    for job in jobs[:5]:
        db.log_job(job["id"], job["title"], job["company"], job["url"])
        await update.message.reply_text(_fmt(job), reply_markup=_job_keyboard(job["id"]))


async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    f = db.get_filters()
    if not f:
        await update.message.reply_text("No custom filters yet.\nUse /addfilter <keyword>")
        return
    await update.message.reply_text("Custom filters:\n" + "\n".join(f"- {k}" for k in f))


async def cmd_addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /addfilter machine learning")
        return
    kw = " ".join(context.args).lower()
    db.add_filter(kw)
    await update.message.reply_text(f"Added filter: {kw}")


async def cmd_removefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removefilter machine learning")
        return
    kw = " ".join(context.args).lower()
    db.remove_filter(kw)
    await update.message.reply_text(f"Removed filter: {kw}")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /blacklist Wipro")
        return
    co = " ".join(context.args)
    db.add_blacklist(co)
    await update.message.reply_text(f"Blacklisted: {co}")


async def cmd_unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unblacklist Wipro")
        return
    co = " ".join(context.args)
    db.remove_blacklist(co)
    await update.message.reply_text(f"Removed from blacklist: {co}")


async def cmd_blacklisted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bl = db.get_blacklist()
    if not bl:
        await update.message.reply_text("No companies blacklisted.")
        return
    await update.message.reply_text("Blacklisted:\n" + "\n".join(f"- {c}" for c in bl))


async def cmd_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        loc = db.get_setting("location", "India")
        await update.message.reply_text(f"Current location: {loc}\nUsage: /location Bangalore")
        return
    loc = " ".join(context.args)
    db.set_setting("location", loc)
    await update.message.reply_text(f"Location updated to: {loc}")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.set_setting("paused", True)
    await update.message.reply_text("Alerts paused. Use /resume to turn back on.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.set_setting("paused", False)
    await update.message.reply_text("Alerts resumed!")
