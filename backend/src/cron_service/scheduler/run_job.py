"""
Locate918 Scraper Cron Runner
=============================
Executes a single scrape job and exits.

Environment:
    SCRAPER_URL  Base URL for the scraper service.
    JOB_TYPE     "all" or "priority"
    PRIORITY     Priority tier when JOB_TYPE=priority.
    TIMEOUT      Request timeout in seconds.
"""

import os
import sys

import httpx


SCRAPER_URL = os.environ.get("SCRAPER_URL", "http://localhost:5000").rstrip("/")
JOB_TYPE = os.environ.get("JOB_TYPE", "all").strip().lower()
TIMEOUT = float(os.environ.get("TIMEOUT", "3600"))


def main() -> int:
    print("=" * 50)
    print("  Locate918 Scraper Cron Runner")
    print(f"  Scraper URL: {SCRAPER_URL}")
    print(f"  Job Type: {JOB_TYPE}")

    try:
        if JOB_TYPE == "priority":
            priority = int(os.environ.get("PRIORITY", "1"))
            print(f"  Priority: {priority}")
            response = httpx.post(
                f"{SCRAPER_URL}/scrape-priority",
                json={"priority": priority},
                timeout=TIMEOUT,
            )
        elif JOB_TYPE == "all":
            response = httpx.post(
                f"{SCRAPER_URL}/scrape-all",
                timeout=TIMEOUT,
            )
        else:
            print(f"[Cron] Unsupported JOB_TYPE '{JOB_TYPE}'", file=sys.stderr)
            return 2

        print(f"[Cron] Response status: {response.status_code}")
        response.raise_for_status()
        if response.text:
            print(response.text[:1000])
        return 0
    except Exception as exc:
        print(f"[Cron] Job failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
