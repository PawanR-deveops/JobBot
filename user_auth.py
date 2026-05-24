"""
User authentication and approval system.
Admin (bot owner) approves/denies access requests.
"""

import json
import os
import subprocess
from datetime import datetime

DATA_DIR  = "data"
ADMIN_ID  = os.getenv("ADMIN_CHAT_ID", "5086463703")


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


# ── User status ───────────────────────────────────────────────────────────────

def is_admin(user_id: str) -> bool:
    return str(user_id) == str(ADMIN_ID)


def is_approved(user_id: str) -> bool:
    if is_admin(user_id):
        return True
    approved = _load("approved_users", {})
    return str(user_id) in approved


def is_pending(user_id: str) -> bool:
    pending = _load("pending_users", {})
    return str(user_id) in pending


def request_access(user_id: str, full_name: str, username: str):
    pending = _load("pending_users", {})
    pending[str(user_id)] = {
        "name":         full_name,
        "username":     username or "",
        "requested_at": datetime.now().isoformat(),
    }
    _save("pending_users", pending)


def approve_user(user_id: str):
    pending  = _load("pending_users", {})
    approved = _load("approved_users", {})
    info = pending.pop(str(user_id), {})
    approved[str(user_id)] = {**info, "approved_at": datetime.now().isoformat()}
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


def is_banned(user_id: str) -> bool:
    return str(user_id) in _load("banned_users", [])


def get_all_users() -> dict:
    return _load("approved_users", {})


def get_pending() -> dict:
    return _load("pending_users", {})
