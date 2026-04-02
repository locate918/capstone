"""
Locate918 Cron Scheduler
========================
Fires scrape jobs against the scraper service on a schedule.
Runs as a separate Railway service from the scraper GUI.

Schedule:
    - Thursday 3am CT:  Full scrape (all sources)
    - Daily 6am CT:     Priority 1 only (flagship venues)

Env vars required:
    SCRAPER_URL   — e.g. https://your-scraper.up.railway.app
    CRON_SECRET   — must match the CRON_SECRET on the scraper service
"""

import os
import httpx
from apscheduler.schedulers.blocking import BlockingScheduler

SCRAPER_URL = os.environ.get("SCRAPER_URL", "http://localhost:5000")
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Use America/Chicago so schedules align with Tulsa local time
scheduler = BlockingScheduler(timezone="America/Chicago")


def _call_cron_scrape(priority: str = None):
    """
    POST to /cron-scrape on the scraper service.
    Returns plain JSON (not SSE), so httpx can handle it normally.
    """
    params = {"secret": CRON_SECRET}
    if priority:
        params["priority"] = priority

    try:
        # Long timeout — sequential scraping of 30+ venues takes a few minutes
        resp = httpx.post(
            f"{SCRAPER_URL}/cron-scrape",
            params=params,
            timeout=7200,  # 2 hours max
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"[Scheduler] ✓ Complete — "
                  f"{data.get('sources_scraped', 0)} sources, "
                  f"{data.get('total_events', 0)} events found, "
                  f"{data.get('total_saved', 0)} saved to DB, "
                  f"{data.get('norm_failures', 0)} norm failures, "
                  f"{data.get('elapsed_seconds', 0)}s elapsed")
            if data.get('errors'):
                for err in data['errors'][:5]:
                    print(f"  ✗ {err.get('name', '?')}: {err.get('error', '?')}")
        elif resp.status_code == 401:
            print(f"[Scheduler] ✗ Auth failed (401) — check CRON_SECRET matches on both services")
        else:
            print(f"[Scheduler] ✗ HTTP {resp.status_code}: {resp.text[:300]}")

    except httpx.TimeoutException:
        print(f"[Scheduler] ✗ Request timed out (scrape may still be running)")
    except httpx.ConnectError:
        print(f"[Scheduler] ✗ Cannot reach scraper at {SCRAPER_URL} — is it running?")
    except Exception as e:
        print(f"[Scheduler] ✗ Error: {e}")


def scrape_all():
    """Full scrape — all priorities."""
    print("\n[Scheduler] ═══ Full scrape (all sources) ═══")
    _call_cron_scrape()


def scrape_priority1():
    """Daily scrape — flagship venues only."""
    print("\n[Scheduler] ═══ Priority 1 scrape (flagship venues) ═══")
    _call_cron_scrape(priority="1")


# Thursday 3am Central — full weekly scrape
scheduler.add_job(scrape_all, "cron", day_of_week="thu", hour=3, minute=0)

# Daily 6am Central — priority 1 venues only
scheduler.add_job(scrape_priority1, "cron", hour=6, minute=0)

if __name__ == "__main__":
    if not CRON_SECRET:
        print("⚠  WARNING: CRON_SECRET not set — requests will fail auth!")
    if SCRAPER_URL == "http://localhost:5000":
        print("⚠  WARNING: SCRAPER_URL is still localhost — set it to your Railway scraper URL")

    print("=" * 50)
    print("  Locate918 Cron Scheduler")
    print(f"  Scraper: {SCRAPER_URL}")
    print(f"  Secret:  {'set' if CRON_SECRET else 'NOT SET'}")
    print("  ─────────────────────────────")
    print("  Thu 3am CT  → Full scrape")
    print("  Daily 6am CT → Priority 1")
    print("=" * 50)
    scheduler.start()