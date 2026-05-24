import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
LINKEDIN_PHONE = os.getenv("LINKEDIN_PHONE", "")

TARGET_ROLES = [
    "big data engineer",
    "data engineer",
    "devops engineer",
    "network engineer",
    "networking engineer",
    "cloud engineer",
    "devops",
    "big data",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", "lead", "principal",
    "manager", "head", "director", "architect",
    "staff", "vp", "vice president",
]

LOCATION = "India"
SCRAPE_INTERVAL_HOURS = 3
