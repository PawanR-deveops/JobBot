import time
import random
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TARGET_ROLES = [
    "big data engineer",
    "data engineer",
    "devops engineer",
    "network engineer",
    "networking engineer",
    "cloud engineer",
]

LOCATION = "India"


def scrape_linkedin(keyword: str) -> list[dict]:
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={keyword.replace(' ', '%20')}"
        f"&location={LOCATION}"
        f"&f_E=2"
        f"&f_TPR=r86400"
        f"&position=1&pageNum=0"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []

        for card in soup.find_all("div", class_="base-card"):
            try:
                job_id = card.get("data-entity-urn", "").split(":")[-1]
                title_el = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")
                location_el = card.find("span", class_="job-search-card__location")
                link_el = card.find("a", class_="base-card__full-link")

                if not title_el or not job_id:
                    continue

                jobs.append({
                    "id": job_id,
                    "title": title_el.get_text(strip=True),
                    "company": company_el.get_text(strip=True) if company_el else "Unknown",
                    "location": location_el.get_text(strip=True) if location_el else LOCATION,
                    "url": link_el.get("href", "").split("?")[0] if link_el else "",
                })
            except Exception:
                continue

        return jobs

    except Exception as e:
        print(f"[scraper] Error for '{keyword}': {e}")
        return []


def get_all_jobs(extra_keywords: list[str] = None) -> list[dict]:
    all_roles = TARGET_ROLES + (extra_keywords or [])
    all_jobs = {}
    for role in all_roles:
        time.sleep(random.uniform(2, 5))
        jobs = scrape_linkedin(role)
        print(f"[scraper] '{role}' → {len(jobs)} found")
        for job in jobs:
            all_jobs[job["id"]] = job
    return list(all_jobs.values())
