# JobHunt India — Telegram Bot

A Telegram bot that automatically scans LinkedIn for fresher job openings in India and sends personalized alerts. Built to run 24/7 on GitHub Actions with zero server cost.

---

## How It Works — Full Flow

### 1. User Onboarding (`user_auth.py`)

When a new user sends `/start`, the bot runs a 3-point profile check to auto-approve or flag for manual review:

| Check | Pass Condition |
|---|---|
| Telegram username | Has a `@handle` |
| Real name | First name ≥ 2 characters, not all digits |
| Profile photo | At least 1 photo set |

- **Score 2 or 3/3** → Auto-approved immediately, gets full access
- **Score 0 or 1/3** → Added to pending queue, admin gets an Approve/Deny notification
- **Admin** (`TELEGRAM_CHAT_ID`) → Always bypasses all checks, instant access

Admin can also manually approve/deny from the **Pending** button or via inline buttons in the notification message.

---

### 2. Job Scraping (`scraper.py`)

Scrapes LinkedIn's public job search page (no login needed) using `requests` + `BeautifulSoup`.

**Default target roles scraped:**
- Big Data Engineer
- Data Engineer
- DevOps Engineer
- Network Engineer
- Cloud Engineer

Each role is scraped separately with a 2–5 second random delay between requests to avoid rate limiting. Results are deduplicated by LinkedIn job ID.

**URL format used:**
```
linkedin.com/jobs/search/?keywords=<role>&location=India&f_E=2&f_TPR=r86400
```
- `f_E=2` → Entry level only
- `f_TPR=r86400` → Posted in last 24 hours

---

### 3. Job Filtering (`matcher.py`)

After scraping, every job title is checked against two lists:

**Target keywords (must match at least one):**
`big data`, `data engineer`, `devops`, `network engineer`, `networking`, `cloud engineer`

**Exclude keywords (if any match → job is skipped):**
`senior`, `sr.`, `lead`, `principal`, `manager`, `head`, `director`, `architect`, `staff`, `vp`

Users can add their own custom keywords via `/addfilter` — these are merged into the scrape query and filter automatically.

---

### 4. Auto Scan — Two Modes

**Mode A: Interactive Bot (`main.py` via `bot_poll.yml`)**

`main.py` runs as a long-polling Telegram bot. It uses PTB's `JobQueue` to run `auto_scan_job` every 30 minutes internally.

Per-user scan window check: each user sets preferred scan times (default: 09:00, 13:00, 18:00 IST). The bot only sends alerts if the current time is within ±35 minutes of one of those times.

**Mode B: GitHub Actions (`scan.py` via `scan.yml`)**

`scan.py` is a one-shot script triggered every 30 minutes by GitHub Actions cron. It calls the Telegram HTTP API directly (no bot library needed). Same scan window logic applies.

Both modes do the same thing — one runs inside the bot process, the other as a separate Actions job.

---

### 5. Per-User Data (`storage.py`)

All user data is stored as JSON files under `data/users/{user_id}/` and auto-committed to the repo after every write so data persists across GitHub Actions runs (which are stateless).

| File | What it stores |
|---|---|
| `wishlist.json` | Jobs saved by the user |
| `applied.json` | Jobs marked as applied + status |
| `filters.json` | Custom keyword filters |
| `blacklist.json` | Companies to skip |
| `settings.json` | Paused state, scan times, location |
| `seen_jobs.json` | Job IDs seen (auto-expires after 7 days) |
| `daily_jobs.json` | Jobs found today (for digest) |

**Seen jobs expiry:** `seen_jobs.json` stores the timestamp each job was seen. Jobs older than 7 days are automatically removed — so if a job is still open after a week, it will show up again.

---

### 6. Inline Buttons — Callback Flow (`callbacks.py`)

Every job alert message has 4 inline buttons. When tapped, `handle_callback` parses the `callback_data` string (`action|job_id`) and performs the action:

| Button | callback_data | Action |
|---|---|---|
| Apply on LinkedIn | (URL link) | Opens LinkedIn directly |
| Save to Wishlist | `save\|{job_id}` | Writes to `wishlist.json` |
| Mark as Applied | `applied\|{job_id}` | Writes to `applied.json` |
| Skip | `skip\|{job_id}` | Deletes the message |

After marking applied, user gets a **Status** button to track: `Applied → Interviewing → Offer / Rejected / Withdrawn`

Admin gets `approve|{uid}` and `deny|{uid}` buttons on pending requests.

---

### 7. Daily Digest

Runs every day at **9:00 AM IST** via two paths:
- `daily_digest_job` in `main.py` using PTB JobQueue (`run_daily`)
- `digest_action.py` triggered by `daily_digest.yml` GitHub Actions cron (`30 3 * * *` UTC = 9 AM IST)

Sends each user a summary of all jobs found that day + total applied count.

---

## GitHub Actions Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `bot_poll.yml` | Every 4 hours + manual | Runs `main.py` in a loop, restarts on crash, auto-pulls latest code |
| `scan.yml` | Every 30 minutes | Runs `scan.py` — scrapes LinkedIn, sends alerts |
| `daily_digest.yml` | 9 AM IST daily | Runs `digest_action.py` — sends daily job summary |
| `set_logo.yml` | Manual only | Sets the bot profile photo (one-time setup) |

---

## Data Files (Auth)

Stored in `data/` at repo root, auto-committed on every change:

| File | Contents |
|---|---|
| `approved_users.json` | `{user_id: {name, username, approved_at, method}}` |
| `pending_users.json` | `{user_id: {name, username, requested_at}}` |
| `banned_users.json` | `[user_id, ...]` |

---

## Setup

### GitHub Secrets required

| Secret | Value |
|---|---|
| `TELEGRAM_TOKEN` | Bot token from @BotFather |
| `ADMIN_CHAT_ID` | Your Telegram user ID (get from @userinfobot) |

### Environment variables (`.env` for local)

```
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Enable GitHub Actions

Go to repo → **Actions** tab → enable all workflows. The bot starts automatically on the next scheduled trigger, or run manually via "Run workflow".

---

## Commands Reference

| Command / Button | Who can use | Description |
|---|---|---|
| `/start` | Everyone | Onboarding + auth check |
| `Scan Now` | Approved users | Manual LinkedIn scan |
| `Wishlist` | Approved users | View saved jobs |
| `Applied Jobs` | Approved users | Track application status |
| `Stats` | Approved users | Job hunt numbers |
| `Digest` | Approved users | Today's jobs summary |
| `Search` | Approved users | Search any keyword |
| `My Filters` | Approved users | View + remove custom filters |
| `Blacklist` | Approved users | View + remove blacklisted companies |
| `Schedule` | Approved users | View + set scan times |
| `Location` | Approved users | Change search city |
| `Pause / Resume` | Approved users | Toggle job alerts |
| `Users` | Admin only | List all approved users |
| `Pending` | Admin only | Review + approve/deny requests |
| `/ban <id>` | Admin only | Ban a user |
| `/addfilter <kw>` | Approved users | Add keyword filter |
| `/blacklist <co>` | Approved users | Block a company |
| `/location <city>` | Approved users | Set search location |
| `/setschedule <times>` | Approved users | Set scan times (e.g. `09:00 13:00 18:00`) |
| `/setstatus <id> <status>` | Approved users | Update job application status |

---

## Tech Stack

- **Python 3.11**
- **python-telegram-bot** — bot framework + job queue
- **requests + BeautifulSoup4** — LinkedIn scraper
- **pytz** — IST timezone handling
- **JSON files** — per-user data storage (auto-committed to GitHub)
- **GitHub Actions** — hosting, scheduling, auto-restart