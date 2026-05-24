# JobBot Setup Guide

## Step 1 — Get Telegram Bot Token

1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Give it a name (e.g. `MyJobBot`) and username (e.g. `myjob_alert_bot`)
4. Copy the **token** it gives you

## Step 2 — Get Your Telegram Chat ID

1. Search `@userinfobot` on Telegram
2. Send any message → it replies with your **Chat ID** (a number like `123456789`)

## Step 3 — Create .env file

Copy `.env.example` to `.env` and fill in:

```
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=123456789

LINKEDIN_EMAIL=your_email@gmail.com
LINKEDIN_PASSWORD=yourpassword
LINKEDIN_PHONE=9876543210
```

## Step 4 — Install dependencies

```bash
cd D:\Software\JobBot
pip install -r requirements.txt
playwright install chromium
```

## Step 5 — Run the bot

```bash
python main.py
```

## Usage

| Command | What it does |
|---------|-------------|
| `/start` | Show help |
| `/scan` | Manually scan LinkedIn now |
| `/status` | Show how many jobs tracked |

When a job alert appears in Telegram:
- **Auto Fill & Apply** → opens browser, fills the Easy Apply form, waits for YOU to click Submit
- **Open on LinkedIn** → opens the job page directly
- **Skip** → dismisses the alert

## Notes

- Auto-scan runs every 3 hours automatically
- The bot never submits applications without you seeing the form first
- LinkedIn may ask for 2FA on first login — handle it manually in the browser window
