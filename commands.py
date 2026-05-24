import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_wishlist, get_applied, get_stats, get_filters, get_blacklist,
    add_filter, remove_filter, add_blacklist, remove_blacklist,
    is_paused, set_setting, get_setting, get_today_jobs, log_job,
)
from scraper import get_all_jobs
from matcher import matches

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "PawanR-deveops/JobBot")


def _job_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Apply on LinkedIn", url=f"https://www.linkedin.com/jobs/view/{job_id}"),
            InlineKeyboardButton("Save to Wishlist", callback_data=f"save|{job_id}"),
        ],
        [
            InlineKeyboardButton("Mark as Applied", callback_data=f"applied|{job_id}"),
            InlineKeyboardButton("Skip", callback_data=f"skip|{job_id}"),
        ],
    ])


def _fmt_job(job: dict) -> str:
    return (
        f"New Job Match!\n\n"
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "JobBot is active!\n\n"
        "Commands:\n"
        "/scan         - Scan LinkedIn now\n"
        "/wishlist     - Saved jobs\n"
        "/applied      - Jobs you applied to\n"
        "/stats        - Your job stats\n"
        "/digest       - Today's job summary\n"
        "/search <kw>  - Search a keyword\n"
        "/filters      - Your custom filters\n"
        "/addfilter    - Add a keyword filter\n"
        "/removefilter - Remove a filter\n"
        "/blacklist    - Blacklist a company\n"
        "/blacklisted  - Show blacklisted companies\n"
        "/location     - Change search location\n"
        "/pause        - Pause job alerts\n"
        "/resume       - Resume job alerts\n"
        "/help         - Show this menu"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_paused():
        await update.message.reply_text("Alerts are paused. Use /resume first.")
        return

    await update.message.reply_text("Scanning LinkedIn... this takes 1-2 minutes.")

    from matcher import matches as _matches
    from database import get_blacklist

    bl = get_blacklist()
    extra = get_filters()

    jobs = get_all_jobs(extra_keywords=extra)
    new_jobs = [j for j in jobs if _matches(j) and not any(b in j["company"].lower() for b in bl)]

    if not new_jobs:
        await update.message.reply_text("No new matching jobs found right now.")
        return

    await update.message.reply_text(f"Found {len(new_jobs)} new job(s)!")

    for job in new_jobs[:10]:
        log_job(job["id"], job["title"], job["company"], job["url"])
        await update.message.reply_text(
            _fmt_job(job),
            reply_markup=_job_keyboard(job["id"]),
        )


async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_wishlist()
    if not jobs:
        await update.message.reply_text("Your wishlist is empty.")
        return

    await update.message.reply_text(f"Saved jobs ({len(jobs)}):")
    for job_id, title, company, url in jobs[:10]:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Open", url=url),
            InlineKeyboardButton("Remove", callback_data=f"rm_wish|{job_id}"),
        ]])
        await update.message.reply_text(
            f"{title}\n{company}",
            reply_markup=keyboard,
        )


async def cmd_applied(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_applied()
    if not jobs:
        await update.message.reply_text("No applied jobs tracked yet.")
        return

    await update.message.reply_text(f"Applied jobs ({len(jobs)}):")
    for job_id, title, company, url, applied_at in jobs[:10]:
        date = applied_at[:10]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Open", url=url),
            InlineKeyboardButton("Remove", callback_data=f"rm_applied|{job_id}"),
        ]])
        await update.message.reply_text(
            f"{title}\n{company}\nApplied: {date}",
            reply_markup=keyboard,
        )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    await update.message.reply_text(
        f"Your Job Stats\n\n"
        f"Today found:   {s['today_found']}\n"
        f"This week:     {s['this_week']}\n"
        f"Total found:   {s['total_found']}\n"
        f"Saved:         {s['wishlist']}\n"
        f"Applied:       {s['applied']}\n"
    )


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_today_jobs()
    if not jobs:
        await update.message.reply_text("No jobs found today yet. Use /scan to check now.")
        return

    lines = [f"Today's Jobs ({len(jobs)} found)\n"]
    for i, (job_id, title, company, url) in enumerate(jobs[:15], 1):
        lines.append(f"{i}. {title} - {company}")

    await update.message.reply_text("\n".join(lines))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /search devops bangalore")
        return

    keyword = " ".join(context.args)
    await update.message.reply_text(f"Searching for: {keyword}...")

    from scraper import scrape_linkedin
    jobs = scrape_linkedin(keyword)

    if not jobs:
        await update.message.reply_text("No results found.")
        return

    await update.message.reply_text(f"Found {len(jobs)} results:")
    for job in jobs[:5]:
        log_job(job["id"], job["title"], job["company"], job["url"])
        await update.message.reply_text(
            _fmt_job(job),
            reply_markup=_job_keyboard(job["id"]),
        )


async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filters = get_filters()
    if not filters:
        await update.message.reply_text("No custom filters added yet.\nUse /addfilter <keyword>")
        return
    await update.message.reply_text("Custom filters:\n" + "\n".join(f"- {f}" for f in filters))


async def cmd_addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /addfilter machine learning")
        return
    keyword = " ".join(context.args).lower()
    add_filter(keyword)
    await update.message.reply_text(f"Added filter: {keyword}")


async def cmd_removefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removefilter machine learning")
        return
    keyword = " ".join(context.args).lower()
    remove_filter(keyword)
    await update.message.reply_text(f"Removed filter: {keyword}")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /blacklist Wipro")
        return
    company = " ".join(context.args)
    add_blacklist(company)
    await update.message.reply_text(f"Blacklisted: {company}\nJobs from this company will be skipped.")


async def cmd_unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unblacklist Wipro")
        return
    company = " ".join(context.args)
    remove_blacklist(company)
    await update.message.reply_text(f"Removed from blacklist: {company}")


async def cmd_blacklisted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bl = get_blacklist()
    if not bl:
        await update.message.reply_text("No companies blacklisted.")
        return
    await update.message.reply_text("Blacklisted companies:\n" + "\n".join(f"- {c}" for c in bl))


async def cmd_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        loc = get_setting("location", "India")
        await update.message.reply_text(f"Current location: {loc}\nUsage: /location Bangalore")
        return
    location = " ".join(context.args)
    set_setting("location", location)
    await update.message.reply_text(f"Location updated to: {location}")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("paused", "1")
    await update.message.reply_text("Job alerts paused. Use /resume to turn back on.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("paused", "0")
    await update.message.reply_text("Job alerts resumed!")
