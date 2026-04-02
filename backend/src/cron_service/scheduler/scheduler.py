"""
Locate918 Scraper Cron Runner
=============================
Executes a single scrape job and exits.
Railway's built-in cron schedule triggers this service.

Environment:
    SCRAPER_URL   Base URL for the scraper service.
    CRON_SECRET   Must match the CRON_SECRET on the scraper service.
    JOB_TYPE      "all" or "priority"
    PRIORITY      Priority tier when JOB_TYPE=priority (default: 1).
    TIMEOUT       Request timeout in seconds (default: 7200).
"""

import os
import sys
import httpx

SCRAPER_URL = os.environ.get("SCRAPER_URL", "http://localhost:5000").rstrip("/")
CRON_SECRET = os.environ.get("CRON_SECRET", "")
JOB_TYPE = os.environ.get("JOB_TYPE", "all").strip().lower()
TIMEOUT = float(os.environ.get("TIMEOUT", "7200"))


def main() -> int:
    print("=" * 50)
    print("  Locate918 Scraper Cron Runner")
    print(f"  Scraper URL: {SCRAPER_URL}")
    print(f"  Secret: {'set' if CRON_SECRET else 'NOT SET'}")
    print(f"  Job Type: {JOB_TYPE}")

    if not CRON_SECRET:
        print("[Cron] ⚠ WARNING: CRON_SECRET not set — request will fail auth!", file=sys.stderr)

    # Build query params
    params = {"secret": CRON_SECRET}

    if JOB_TYPE == "priority":
        priority = os.environ.get("PRIORITY", "1")
        params["priority"] = priority
        print(f"  Priority: {priority}")
    elif JOB_TYPE == "all":
        pass  # no priority filter — scrape everything
    else:
        print(f"[Cron] Unsupported JOB_TYPE '{JOB_TYPE}'", file=sys.stderr)
        return 2

    print("=" * 50)

    try:
        response = httpx.post(
            f"{SCRAPER_URL}/cron-scrape",
            params=params,
            timeout=TIMEOUT,
        )

        print(f"[Cron] Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"[Cron] ✓ Complete — "
                  f"{data.get('sources_scraped', 0)} sources, "
                  f"{data.get('total_events', 0)} events found, "
                  f"{data.get('total_saved', 0)} saved to DB, "
                  f"{data.get('norm_failures', 0)} norm failures, "
                  f"{data.get('elapsed_seconds', 0)}s elapsed")
            if data.get('errors'):
                for err in data['errors'][:5]:
                    print(f"  ✗ {err.get('name', '?')}: {err.get('error', '?')}")
            return 0

        elif response.status_code == 401:
            print("[Cron] ✗ Auth failed — check CRON_SECRET matches on both services", file=sys.stderr)
            return 1

        else:
            response.raise_for_status()
            return 0

    except httpx.TimeoutException:
        print(f"[Cron] ✗ Request timed out after {TIMEOUT}s (scrape may still be running)", file=sys.stderr)
        return 1
    except httpx.ConnectError:
        print(f"[Cron] ✗ Cannot reach scraper at {SCRAPER_URL}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[Cron] ✗ Job failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())