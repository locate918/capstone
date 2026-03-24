"""
scraperExtractors package
=========================
Re-exports all extractor functions and fetch utilities so scraperRoutes.py
can import everything from a single namespace:

    from scraperExtractors import extract_eventcalendarapp, ...
"""

# ── API / JSON-driven extractors ──────────────────────────────────────────────
from .apiExtractors import (
    extract_eventcalendarapp,
    extract_timely,
    extract_bok_center,
)

# ── CMS / platform-specific extractors ───────────────────────────────────────
from .cmsExtractors import (
    extract_expo_square_events,
    extract_eventbrite_api_events,
    extract_simpleview_events,
    extract_sitewrench_events,
    extract_recdesk_events,
    extract_ticketleap_events,
    extract_circle_cinema_events,
    extract_libnet_events,
    extract_philbrook_events,
    extract_tulsapac_events,
    extract_roosterdays_events,
    extract_tulsabrunchfest_events,
    extract_okeq_events,
    extract_flywheel_events,
    extract_arvest_events,
    extract_tulsatough_events,
    extract_gradient_events,
    extract_tulsafarmersmarket_events,
    extract_okcastle_events,
    extract_broken_arrow_events,
    extract_tulsazoo_events,
    extract_hardrock_tulsa_events,
    extract_gypsy_events,
    extract_badass_renees_events,
    extract_rocklahoma_events,
    extract_tulsa_oktoberfest_events,
    extract_bricktown_comedy_events,
    extract_loonybin_events,
    extract_rhp_events,
    extract_church_studio_events,
    extract_carneyfest_events,
    extract_maggies_events,
    extract_route66_village_events,
    extract_living_arts_events,
    extract_jenks_planetarium_events,
    extract_riverparks_events,
    extract_magic_city_books_events,
    extract_spotlight_theater_events,
    extract_tulsamayfest_events,
)

# ── Universal fallback ────────────────────────────────────────────────────────
from .universal import extract_events_universal

# ── Fetch helpers ─────────────────────────────────────────────────────────────
from .fetchers import fetch_with_httpx, fetch_with_playwright

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
    'extract_circle_cinema_events',
    'extract_libnet_events',
    'extract_philbrook_events',
    'extract_tulsapac_events',
    'extract_roosterdays_events',
    'extract_tulsabrunchfest_events',
    'extract_okeq_events',
    'extract_flywheel_events',
    'extract_arvest_events',
    'extract_tulsatough_events',
    'extract_gradient_events',
    'extract_tulsafarmersmarket_events',
    'extract_okcastle_events',
    'extract_broken_arrow_events',
    'extract_tulsazoo_events',
    'extract_hardrock_tulsa_events',
    'extract_gypsy_events',
    'extract_badass_renees_events',
    'extract_rocklahoma_events',
    'extract_tulsa_oktoberfest_events',
    'extract_bricktown_comedy_events',
    'extract_loonybin_events',
    'extract_rhp_events',
    'extract_church_studio_events',
    'extract_carneyfest_events',
    'extract_maggies_events',
    'extract_route66_village_events',
    'extract_living_arts_events',
    'extract_jenks_planetarium_events',
    'extract_riverparks_events',
    'extract_magic_city_books_events',
    'extract_spotlight_theater_events',
    'extract_tulsamayfest_events',
    'extract_events_universal',
    'fetch_with_httpx',
    'fetch_with_playwright',
]