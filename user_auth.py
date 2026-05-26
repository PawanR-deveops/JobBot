"""
User authentication and approval system.
Auto-approves users who pass profile checks (username + real name + profile photo).
Users who fail checks are sent to admin for manual approval.
"""

import json
import logging
import os
import subprocess
from datetime import datetime

log = logging.getLogger(__name__)

DATA_DIR = "data"
# Support both TELEGRAM_CHAT_ID (used in .env.example) and ADMIN_CHAT_ID
ADMIN_ID = (os.getenv("TELEGRAM_CHAT_ID") or os.getenv("ADMIN_CHAT_ID") or "").strip()


def _path(name):
    return os.path.join(DATA_DIR, f"{name}.json")


def _load(name, default):
    p = _path(name)
    return json.load(open(p)) if os.path.exists(p) else default


def _save(name, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_path(name), "w") as f:
        json.dump(data, f, indent=2)
    try:
        subprocess.run(["git", "add", _path(name)], capture_output=True)
        if subprocess.run(["git", "diff", "--staged", "--quiet"]).returncode != 0:
            subprocess.run(["git", "commit", "-m", f"auth: update {name}"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
    except Exception:
        pass


# ── Status checks ─────────────────────────────────────────────────────────────

def is_admin(user_id: str) -> bool:
    return str(user_id) == str(ADMIN_ID)


def is_approved(user_id: str) -> bool:
    if is_admin(user_id):
        return True
    return str(user_id) in _load("approved_users", {})


def is_pending(user_id: str) -> bool:
    if is_admin(user_id):
        return False
    return str(user_id) in _load("pending_users", {})


def is_banned(user_id: str) -> bool:
    return str(user_id) in _load("banned_users", [])


# ── Profile auto-approval ─────────────────────────────────────────────────────

async def check_and_auto_approve(bot, user) -> tuple[bool, str]:
    """
    Checks user's Telegram profile and auto-approves if it looks legitimate.

    Checks:
      1. Has a Telegram username (@handle)
      2. Has a real first name (at least 2 chars, not all digits)
      3. Has at least one profile photo

    Returns (approved: bool, reason: str)
    """
    uid    = str(user.id)
    issues = []
    score  = 0

    # Check 1: Has a username
    if user.username:
        score += 1
        log.info(f"[auth] {uid} has username @{user.username}")
    else:
        issues.append("no Telegram username set")

    # Check 2: Real name
    name = (user.first_name or "").strip()
    if name and len(name) >= 2 and not name.isdigit():
        score += 1
        log.info(f"[auth] {uid} has valid name: {name}")
    else:
        issues.append("name looks invalid")

    # Check 3: Profile photo
    try:
        photos = await bot.get_user_profile_photos(user_id=user.id, limit=1)
        if photos.total_count > 0:
            score += 1
            log.info(f"[auth] {uid} has profile photo")
        else:
            issues.append("no profile photo")
    except Exception as e:
        log.warning(f"[auth] Could not check photo for {uid}: {e}")
        issues.append("profile photo check failed")

    log.info(f"[auth] {uid} score={score}/3 issues={issues}")

    if score >= 2:
        # Profile looks real — auto approve
        approve_user(uid, user.first_name or "", user.username or "", auto=True)
        return True, f"auto-approved (score {score}/3)"

    return False, ", ".join(issues)


# ── User management ───────────────────────────────────────────────────────────

def approve_user(user_id: str, name: str = "", username: str = "", auto: bool = False):
    pending  = _load("pending_users", {})
    approved = _load("approved_users", {})
    info     = pending.pop(str(user_id), {})
    approved[str(user_id)] = {
        "name":        name or info.get("name", ""),
        "username":    username or info.get("username", ""),
        "approved_at": datetime.now().isoformat(),
        "method":      "auto" if auto else "manual",
    }
    _save("pending_users", pending)
    _save("approved_users", approved)


def deny_user(user_id: str):
    pending = _load("pending_users", {})
    pending.pop(str(user_id), None)
    _save("pending_users", pending)


def ban_user(user_id: str):
    approved = _load("approved_users", {})
    approved.pop(str(user_id), None)
    banned = _load("banned_users", [])
    if str(user_id) not in banned:
        banned.append(str(user_id))
    _save("approved_users", approved)
    _save("banned_users", banned)


def request_access(user_id: str, full_name: str, username: str):
    if is_admin(user_id):
        return
    pending = _load("pending_users", {})
    pending[str(user_id)] = {
        "name":         full_name,
        "username":     username or "",
        "requested_at": datetime.now().isoformat(),
    }
    _save("pending_users", pending)


def get_all_users() -> dict:
    return _load("approved_users", {})


def get_pending() -> dict:
    return _load("pending_users", {})