"""
Locate918 Scraper - Extraction Strategies Package
==================================================
Split from the monolithic scraper_extractors.py into focused modules.

Modules:
  fetchers.py           - HTTP/Playwright page fetching
  apiExtractors.py      - Direct API extractors (EventCalendarApp, Timely, BOK Center)
  cmsExtractors.py      - CMS/platform API extractors (Expo, Eventbrite, Simpleview, SiteWrench, RecDesk, TicketLeap, Circle Cinema)
  platformExtractors.py - DOM-based platform extractors (Tribe, Stubwire, Etix, TNEW, GCal, Squarespace, etc.)
  genericExtractors.py  - Generic fallback extractors (repeating structures, date proximity)
  universal.py          - Master orchestrator that chains all extractors
"""

# Re-export everything that scraperRoutes.py imports
from .apiExtractors import (
    extract_eventcalendarapp,
    extract_timely,
    extract_bok_center,
)

from .cmsExtractors import (
    extract_expo_square_events,
    extract_eventbrite_api_events,
    extract_simpleview_events,
    extract_sitewrench_events,
    extract_recdesk_events,
    extract_ticketleap_events,
    extract_circle_cinema,
)

from .universal import extract_events_universal

from .fetchers import (
    fetch_with_httpx,
    fetch_with_playwright,
)

__all__ = [
    'extract_eventcalendarapp',
    'extract_timely',
    'extract_bok_center',
    'extract_expo_square_events',
    'extract_eventbrite_api_events',
    'extract_simpleview_events',
    'extract_sitewrench_events',
    'extract_recdesk_events',
    'extract_ticketleap_events',
    'extract_circle_cinema',
    'extract_events_universal',
    'fetch_with_httpx',
    'fetch_with_playwright',
]