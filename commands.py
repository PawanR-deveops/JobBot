import asyncio
import logging
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import storage as db
import user_auth as auth
from scraper import get_all_jobs, scrape_linkedin
from matcher import matches

log = logging.getLogger(__name__)

BOT_NAME = "JobHunt India"

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

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Scan Now",     "Wishlist",    "Applied Jobs"],
        ["Stats",        "Digest",      "Search"],
        ["My Filters",   "Blacklist",   "Schedule"],
        ["Location",     "Pause Alerts","Resume"],
        ["Users",        "Pending",     "Help"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


def _keyboard(user_id: str):
    return ADMIN_KEYBOARD if auth.is_admin(user_id) else MAIN_KEYBOARD


# ── Decorators ────────────────────────────────────────────────────────────────

def safe(func):
    """Catches all exceptions so bot never crashes."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await func(update, context)
        except Exception as e:
            log.error(f"[{func.__name__}] {e}", exc_info=True)
            try:
                uid = str(update.effective_user.id)
                await update.effective_message.reply_text(
                    "Something went wrong. Please try again.",
                    reply_markup=_keyboard(uid),
                )
            except Exception:
                pass
    return wrapper


def requires_auth(func):
    """Blocks unapproved users and sends admin a request."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        uid     = str(user.id)
        name    = user.full_name or "Unknown"
        uname   = user.username or ""

        if auth.is_banned(uid):
            await update.effective_message.reply_text("You are not allowed to use this bot.")
            return

        if not auth.is_approved(uid):
            if not auth.is_pending(uid):
                auth.request_access(uid, name, uname)
                # Notify admin
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Approve", callback_data=f"approve|{uid}"),
                    InlineKeyboardButton("Deny",    callback_data=f"deny|{uid}"),
                ]])
                admin_text = (
                    f"New access request!\n\n"
                    f"Name: {name}\n"
                    f"Username: @{uname}\n"
                    f"User ID: {uid}"
                )
                try:
                    await context.bot.send_message(
                        chat_id=auth.ADMIN_ID,
                        text=admin_text,
                        reply_markup=kb,
                    )
                except Exception:
                    pass

            await update.effective_message.reply_text(
                f"Welcome to {BOT_NAME}!\n\n"
                "Your access request has been sent to the admin.\n"
                "You will be notified once approved."
            )
            return

        await func(update, context)
    return wrapper


def admin_only(func):
    """Restricts command to admin only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        if not auth.is_admin(uid):
            await update.effective_message.reply_text("Admin only command.")
            return
        await func(update, context)
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


async def _send_jobs(update: Update, uid: str, jobs: list):
    for job in jobs[:10]:
        db.mark_seen(uid, job["id"])
        db.log_job(uid, job["id"], job["title"], job["company"], job["url"])
        await update.message.reply_text(_fmt(job), reply_markup=_job_keyboard(job["id"]))
        await asyncio.sleep(0.4)


# ── User commands ─────────────────────────────────────────────────────────────

@safe
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = str(user.id)

    if auth.is_banned(uid):
        await update.effective_message.reply_text("You are not allowed to use this bot.")
        return

    if auth.is_approved(uid):
        kb = _keyboard(uid)
        await update.message.reply_text(
            f"Welcome back to {BOT_NAME}!\n\n"
            "I scan LinkedIn every 30 minutes and alert you about new job openings "
            "matching your profile in India.\n\n"
            "Tap any button below to get started.",
            reply_markup=kb,
        )
        return

    if not auth.is_pending(uid):
        # New user — try auto-approval first
        approved, reason = await auth.check_and_auto_approve(context.bot, user)
        if approved:
            kb = _keyboard(uid)
            await update.message.reply_text(
                f"Welcome to {BOT_NAME}!\n\n"
                "I scan LinkedIn every 30 minutes and alert you about new job openings "
                "matching your profile in India.\n\n"
                "Tap any button below to get started.",
                reply_markup=kb,
            )
            log.info(f"[start] {uid} auto-approved: {reason}")
            return

        # Profile didn't pass — put in pending and notify admin
        auth.request_access(uid, user.full_name or "", user.username or "")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Approve", callback_data=f"approve|{uid}"),
            InlineKeyboardButton("Deny",    callback_data=f"deny|{uid}"),
        ]])
        admin_text = (
            f"Access request (manual review needed)\n\n"
            f"Name: {user.full_name}\n"
            f"Username: @{user.username}\n"
            f"ID: {uid}\n"
            f"Issues: {reason}"
        )
        try:
            await context.bot.send_message(
                chat_id=auth.ADMIN_ID,
                text=admin_text,
                reply_markup=kb,
            )
        except Exception:
            pass

    await update.message.reply_text(
        f"Welcome to {BOT_NAME}!\n\n"
        "Your access request has been sent to the admin.\n"
        "You will be notified once approved."
    )


@safe
@requires_auth
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await update.message.reply_text(
        f"{BOT_NAME} — Button Guide\n\n"
        "Scan Now     - Find new jobs on LinkedIn right now\n"
        "Wishlist     - Jobs you saved (tap Remove to delete)\n"
        "Applied Jobs - Track application status\n"
        "Stats        - Your job hunt numbers\n"
        "Digest       - All jobs found today\n"
        "Search       - Search any keyword\n"
        "My Filters   - Your custom keywords (tap to remove)\n"
        "Blacklist    - Companies to skip (tap to remove)\n"
        "Schedule     - Set your preferred scan times\n"
        "Location     - Change search city\n"
        "Pause/Resume - Toggle job alerts\n\n"
        "Commands:\n"
        "/addfilter <keyword>    - Add keyword filter\n"
        "/blacklist <company>    - Block a company\n"
        "/location <city>        - Set location\n"
        "/setschedule <times>    - Set scan times\n"
        "/setstatus <id> <status>- Update job status",
        reply_markup=_keyboard(uid),
    )


@safe
@requires_auth
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if db.is_paused(uid):
        await update.message.reply_text("Alerts are paused. Tap Resume first.", reply_markup=_keyboard(uid))
        return

    await update.message.reply_text("Scanning LinkedIn... takes 1-2 minutes.")

    extra    = db.get_filters(uid)
    all_jobs = get_all_jobs(extra_keywords=extra)
    new_jobs = [
        j for j in all_jobs
        if not db.is_seen(uid, j["id"]) and matches(j) and not db.is_blacklisted(uid, j["company"])
    ]

    if not new_jobs:
        await update.message.reply_text(
            "No new matching jobs found right now.\nTry again in a few hours.",
            reply_markup=_keyboard(uid),
        )
        return

    await update.message.reply_text(f"Found {len(new_jobs)} new job(s)!")
    await _send_jobs(update, uid, new_jobs)


@safe
@requires_auth
async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    jobs = db.get_wishlist(uid)
    if not jobs:
        await update.message.reply_text(
            "Your wishlist is empty.\nTap Save to Wishlist on any job alert.",
            reply_markup=_keyboard(uid),
        )
        return
    await update.message.reply_text(f"Saved jobs ({len(jobs)}):", reply_markup=_keyboard(uid))
    for job_id, title, company, url in jobs[:10]:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Open", url=url),
            InlineKeyboardButton("Remove", callback_data=f"rm_wish|{job_id}"),
        ]])
        await update.message.reply_text(f"{title}\n{company}", reply_markup=kb)
        await asyncio.sleep(0.3)


@safe
@requires_auth
async def cmd_applied(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    jobs = db.get_applied(uid)
    if not jobs:
        await update.message.reply_text(
            "No applied jobs tracked yet.\nTap Mark as Applied on any job alert.",
            reply_markup=_keyboard(uid),
        )
        return
    await update.message.reply_text(f"Applied jobs ({len(jobs)}):", reply_markup=_keyboard(uid))
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
@requires_auth
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    s   = db.get_stats(uid)
    await update.message.reply_text(
        f"Your Job Stats\n\n"
        f"Today found  : {s['today_found']}\n"
        f"This week    : {s['this_week']}\n"
        f"Total found  : {s['total_found']}\n"
        f"Saved        : {s['wishlist']}\n"
        f"Applied      : {s['applied']}\n",
        reply_markup=_keyboard(uid),
    )


@safe
@requires_auth
async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    jobs = db.get_today_jobs(uid)
    if not jobs:
        await update.message.reply_text(
            "No jobs found today yet. Tap Scan Now to check.",
            reply_markup=_keyboard(uid),
        )
        return
    lines = [f"Today's Jobs ({len(jobs)} found)\n"]
    for i, (jid, title, company, url) in enumerate(jobs[:15], 1):
        lines.append(f"{i}. {title} - {company}")
    await update.message.reply_text("\n".join(lines), reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text(
            "Type your search:\n/search devops\n/search network engineer bangalore",
            reply_markup=_keyboard(uid),
        )
        return
    keyword = " ".join(context.args)
    await update.message.reply_text(f"Searching: {keyword}...")
    jobs = scrape_linkedin(keyword)
    if not jobs:
        await update.message.reply_text("No results found.", reply_markup=_keyboard(uid))
        return
    await update.message.reply_text(f"Found {len(jobs)} results:")
    await _send_jobs(update, uid, jobs[:5])


@safe
@requires_auth
async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    f   = db.get_filters(uid)
    if not f:
        await update.message.reply_text(
            "No custom filters yet.\n/addfilter kubernetes\n/addfilter machine learning",
            reply_markup=_keyboard(uid),
        )
        return
    await update.message.reply_text(
        f"Your filters ({len(f)}) — tap to remove:", reply_markup=_keyboard(uid)
    )
    for keyword in f:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"Remove: {keyword}", callback_data=f"rm_filter|{keyword}"),
        ]])
        await update.message.reply_text(keyword, reply_markup=kb)
        await asyncio.sleep(0.3)


@safe
@requires_auth
async def cmd_addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /addfilter machine learning", reply_markup=_keyboard(uid))
        return
    kw = " ".join(context.args).lower()
    db.add_filter(uid, kw)
    await update.message.reply_text(f"Added filter: {kw}", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_removefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /removefilter machine learning", reply_markup=_keyboard(uid))
        return
    kw = " ".join(context.args).lower()
    db.remove_filter(uid, kw)
    await update.message.reply_text(f"Removed: {kw}", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /blacklist Wipro", reply_markup=_keyboard(uid))
        return
    co = " ".join(context.args)
    db.add_blacklist(uid, co)
    await update.message.reply_text(f"Blacklisted: {co}", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /unblacklist Wipro", reply_markup=_keyboard(uid))
        return
    co = " ".join(context.args)
    db.remove_blacklist(uid, co)
    await update.message.reply_text(f"Removed from blacklist: {co}", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_blacklisted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    bl  = db.get_blacklist(uid)
    if not bl:
        await update.message.reply_text(
            "No companies blacklisted.\n/blacklist Wipro",
            reply_markup=_keyboard(uid),
        )
        return
    await update.message.reply_text(
        f"Blacklisted ({len(bl)}) — tap to remove:", reply_markup=_keyboard(uid)
    )
    for company in bl:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"Remove: {company}", callback_data=f"rm_blacklist|{company}"),
        ]])
        await update.message.reply_text(company, reply_markup=kb)
        await asyncio.sleep(0.3)


@safe
@requires_auth
async def cmd_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        loc = db.get_setting(uid, "location", "India")
        await update.message.reply_text(
            f"Current location: {loc}\n\n/location Bangalore\n/location Chennai",
            reply_markup=_keyboard(uid),
        )
        return
    loc = " ".join(context.args)
    db.set_setting(uid, "location", loc)
    await update.message.reply_text(f"Location updated to: {loc}", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_setschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        times = db.get_scan_times(uid)
        await update.message.reply_text(
            f"Scan times (IST): {', '.join(times)}\n\n"
            "To change:\n/setschedule 09:00 13:00 18:00",
            reply_markup=_keyboard(uid),
        )
        return
    times = [t for t in context.args if ":" in t]
    if not times:
        await update.message.reply_text("Format: /setschedule 09:00 13:00 18:00", reply_markup=_keyboard(uid))
        return
    db.set_setting(uid, "scan_times", ",".join(times))
    await update.message.reply_text(
        f"Schedule set! Scanning at: {', '.join(times)} IST",
        reply_markup=_keyboard(uid),
    )


@safe
@requires_auth
async def cmd_setstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /setstatus <job_id> <status>\n"
            f"Statuses: {', '.join(db.VALID_STATUSES)}",
            reply_markup=_keyboard(uid),
        )
        return
    job_id = context.args[0]
    status = context.args[1].capitalize()
    if status not in db.VALID_STATUSES:
        await update.message.reply_text(
            f"Invalid status. Choose: {', '.join(db.VALID_STATUSES)}",
            reply_markup=_keyboard(uid),
        )
        return
    if db.update_status(uid, job_id, status):
        await update.message.reply_text(f"Status updated to: {status}", reply_markup=_keyboard(uid))
    else:
        await update.message.reply_text("Job not found.", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    db.set_setting(uid, "paused", True)
    await update.message.reply_text("Alerts paused. Tap Resume to turn back on.", reply_markup=_keyboard(uid))


@safe
@requires_auth
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    db.set_setting(uid, "paused", False)
    await update.message.reply_text("Alerts resumed!", reply_markup=_keyboard(uid))


# ── Admin commands ────────────────────────────────────────────────────────────

@safe
@admin_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = str(update.effective_user.id)
    users = auth.get_all_users()
    if not users:
        await update.message.reply_text("No approved users yet.", reply_markup=_keyboard(uid))
        return
    lines = [f"Approved users ({len(users)})\n"]
    for user_id, info in users.items():
        name  = info.get("name", "Unknown")
        uname = info.get("username", "")
        lines.append(f"- {name} (@{uname}) [{user_id}]")
    await update.message.reply_text("\n".join(lines), reply_markup=_keyboard(uid))


@safe
@admin_only
async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    pending = auth.get_pending()
    if not pending:
        await update.message.reply_text("No pending requests.", reply_markup=_keyboard(uid))
        return
    await update.message.reply_text(f"Pending requests ({len(pending)}):")
    for user_id, info in pending.items():
        name  = info.get("name", "Unknown")
        uname = info.get("username", "")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Approve", callback_data=f"approve|{user_id}"),
            InlineKeyboardButton("Deny",    callback_data=f"deny|{user_id}"),
        ]])
        await update.message.reply_text(
            f"Name: {name}\nUsername: @{uname}\nID: {user_id}",
            reply_markup=kb,
        )
        await asyncio.sleep(0.3)


@safe
@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>", reply_markup=_keyboard(uid))
        return
    target = context.args[0]
    auth.ban_user(target)
    await update.message.reply_text(f"Banned user: {target}", reply_markup=_keyboard(uid))
