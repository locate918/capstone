"""
Locate918 Cron Scheduler
========================
Fires scrape jobs against the scraper service on a schedule.
Runs independently of the scraper GUI.

Schedule:
    - Thursday 3am UTC: Full scrape (all sources)
    - Daily 6am UTC:    Priority 1 only (flagship venues)
"""

import os
import httpx
from apscheduler.schedulers.blocking import BlockingScheduler

SCRAPER_URL = os.environ.get("SCRAPER_URL", "http://localhost:5000")

scheduler = BlockingScheduler(timezone="UTC")


def scrape_all():
    print("[Scheduler] Triggering full scrape (all sources)...")
    try:
        resp = httpx.post(f"{SCRAPER_URL}/scrape-all", timeout=3600)
        print(f"[Scheduler] Full scrape complete — status {resp.status_code}")
    except Exception as e:
        print(f"[Scheduler] Full scrape failed: {e}")


def scrape_priority1():
    print("[Scheduler] Triggering Priority 1 scrape...")
    try:
        resp = httpx.post(f"{SCRAPER_URL}/scrape-priority", json={"priority": 1}, timeout=1800)
        print(f"[Scheduler] Priority 1 scrape complete — status {resp.status_code}")
    except Exception as e:
        print(f"[Scheduler] Priority 1 scrape failed: {e}")


# Thursday 3am UTC — full weekly scrape
scheduler.add_job(scrape_all, "cron", day_of_week="thu", hour=3, minute=0)

# Daily 6am UTC — priority 1 venues only
scheduler.add_job(scrape_priority1, "cron", hour=6, minute=0)

if __name__ == "__main__":
    print("=" * 50)
    print("  Locate918 Cron Scheduler")
    print(f"  Scraper URL: {SCRAPER_URL}")
    print("  Thu 3am UTC  → Full scrape")
    print("  Daily 6am UTC → Priority 1 scrape")
    print("=" * 50)
    scheduler.start()