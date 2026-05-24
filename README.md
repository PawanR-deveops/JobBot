# JobBot

A Telegram bot that scans LinkedIn every 30 minutes and sends new job alerts matching your profile in India.

## Features

- Auto-scans LinkedIn for job openings in India
- Filters by role keywords and location
- Wishlist and applied jobs tracker
- Daily digest at 9 AM IST
- Admin approval system for new users
- Blacklist companies you want to skip

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your credentials
3. Set GitHub Secrets: `TELEGRAM_TOKEN`, `ADMIN_CHAT_ID`
4. Enable GitHub Actions — the bot runs automatically

## Commands

| Command | Description |
|---|---|
| `Scan Now` | Find new jobs instantly |
| `Wishlist` | View saved jobs |
| `Applied Jobs` | Track application status |
| `My Filters` | Custom keyword filters |
| `Blacklist` | Skip specific companies |
| `/location <city>` | Set search location |
| `/addfilter <keyword>` | Add keyword filter |

## Tech

Python, python-telegram-bot, GitHub Actions