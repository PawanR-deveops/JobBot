TARGET_ROLES = [
    "big data", "data engineer", "devops",
    "network engineer", "networking", "cloud engineer",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", "lead", "principal",
    "manager", "head", "director", "architect", "staff",
]


def matches(job: dict) -> bool:
    title = job.get("title", "").lower()
    if any(exc in title for exc in EXCLUDE_KEYWORDS):
        return False
    return any(role in title for role in TARGET_ROLES)
