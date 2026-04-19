"""
Locate918 Scraper - Universal Orchestrator
============================================
Master extraction function that chains all extractors in priority order
and applies universal post-processing (dedup, garbage filter).

FIX: Garbage title filter now applies to ALL extraction methods universally,
     not just date proximity. Catches "click here for tickets", UI labels, etc.
"""

import html
import re
from bs4 import BeautifulSoup

from .platformExtractors import (
    extract_schema_org,
    extract_tribe_events,
    extract_eventbrite_embed,
    extract_stubwire_events,
    extract_dice_events,
    extract_bandsintown_events,
    extract_songkick_events,
    extract_ticketmaster_events,
    extract_axs_events,
    extract_etix_events,
    extract_seetickets_events,
    extract_tnew_events,
    extract_gcal_events,
    extract_squarespace_events,
    extract_tickettailor_events,
)

from .apiExtractors import (
    extract_timely_from_html,
)

from .genericExtractors import (
    extract_repeating_structures,
    extract_by_date_proximity,
    _strip_past_events_section,
)


# ============================================================================
# GARBAGE TITLE FILTER
# ============================================================================

GARBAGE_TITLES = {
    # Navigation / UI labels
    'events', 'calendar', 'all events', 'upcoming events', 'event list',
    'calendar view', 'list view', 'grid view', 'filter by date',
    'filter by category', 'show filters', 'clear filters', 'reset',
    'previous', 'next', 'load more', 'view more', 'see all',
    'view all events', 'see all events', 'show all',
    # Subscription / export
    'google calendar', 'icalendar', 'ical', 'ical export',
    'outlook 365', 'outlook live', 'export events', 'subscribe',
    'add to calendar', 'add to my calendar',
    # Ticket CTAs
    'buy tickets', 'get tickets', 'buy now', 'book now', 'register',
    'click here for tickets', 'click here to get tickets',
    'click here to buy tickets', 'purchase tickets',
    'tickets on sale now', 'on sale now',
    # Social / share
    'share', 'share this', 'share event', 'tweet', 'facebook', 'instagram',
    # Date navigation
    'today', 'this week', 'this weekend', 'this month',
    'previous events', 'next events', 'past events',
    'event views navigation', 'view as',
    # Generic
    'read more', 'learn more', 'more info', 'details', 'info',
    'search', 'find events', 'no events found',
}

# Patterns that indicate garbage titles
GARBAGE_PATTERNS = [
    re.compile(r'^(mon|tue|wed|thu|fri|sat|sun)(day)?$', re.IGNORECASE),
    re.compile(r'^\d{1,2}[:/]\d{2}', re.IGNORECASE),  # time-only
    re.compile(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}$', re.IGNORECASE),  # date-only
    re.compile(r'^page\s+\d+', re.IGNORECASE),
    re.compile(r'^#\d+', re.IGNORECASE),
]


def _is_garbage_title(title: str) -> bool:
    """Check if a title is garbage (UI label, nav element, CTA, etc.)."""
    if not title:
        return True

    clean = title.lower().strip()

    # Exact matches
    if clean in GARBAGE_TITLES:
        return True

    # Very short non-word titles
    if len(clean) < 3:
        return True

    # Pattern matches
    for pattern in GARBAGE_PATTERNS:
        if pattern.match(clean):
            return True

    return False


# ============================================================================
# UNIVERSAL EXTRACTION
# ============================================================================

def extract_events_universal(html: str, base_url: str, source_name: str) -> list:
    """
    Universal event extraction - tries multiple strategies in priority order.
    Applies garbage filter and deduplication universally.
    """
    soup = BeautifulSoup(html, 'html.parser')
    all_events = []
    methods_used = []

    # ── 1. Schema.org FIRST (before stripping <script>) ──
    schema_events = extract_schema_org(soup, base_url, source_name)
    if schema_events:
        all_events.extend(schema_events)
        methods_used.append(f"Schema.org ({len(schema_events)})")

    # ── Strip junk tags (preserving <header> for Tribe) ──
    for tag in soup.select('style, nav, footer, noscript'):
        tag.decompose()
    for tag in soup.select('script:not([type="tnew-api-data"]):not([type="gcal-api-data"]):not([type="recdesk-api-data"]):not([type="etix-api-data"])'):
        tag.decompose()

    # ── FIX: Strip PAST EVENTS sections ──
    _strip_past_events_section(soup)

    # ── 2. Etix pages (special early exit) ──
    if 'etix.com' in base_url:
        etix_events = extract_etix_events(soup, base_url, source_name)
        if etix_events:
            all_events.extend(etix_events)
            methods_used.append(f"Etix ({len(etix_events)})")
            return _finalize(all_events, methods_used)

    # ── 2b. TicketTailor pages (special early exit) ──
    if 'tickettailor.com' in base_url:
        tt_events, tt_detected = extract_tickettailor_events(soup, base_url, source_name)
        if tt_detected and tt_events:
            all_events.extend(tt_events)
            methods_used.append(f"TicketTailor ({len(tt_events)})")
            return _finalize(all_events, methods_used)

    # ── 3. TNEW/Tessitura API data ──
    tnew_events = extract_tnew_events(soup, base_url, source_name)
    if tnew_events:
        all_events.extend(tnew_events)
        methods_used.append(f"TNEW ({len(tnew_events)})")

    # ── 4. Google Calendar API data ──
    gcal_events = extract_gcal_events(soup, base_url, source_name)
    if gcal_events:
        all_events.extend(gcal_events)
        methods_used.append(f"Google Calendar ({len(gcal_events)})")

    # ── 5. Known plugin extractors ──
    tribe_events = extract_tribe_events(soup, base_url, source_name)
    if tribe_events:
        all_events.extend(tribe_events)
        methods_used.append(f"WordPress Events Calendar ({len(tribe_events)})")

    eventbrite_events = extract_eventbrite_embed(soup, base_url, source_name)
    if eventbrite_events:
        all_events.extend(eventbrite_events)
        methods_used.append(f"Eventbrite ({len(eventbrite_events)})")

    stubwire_events = extract_stubwire_events(soup, base_url, source_name)
    if stubwire_events:
        all_events.extend(stubwire_events)
        methods_used.append(f"Stubwire ({len(stubwire_events)})")

    dice_events = extract_dice_events(soup, base_url, source_name)
    if dice_events:
        all_events.extend(dice_events)
        methods_used.append(f"Dice.fm ({len(dice_events)})")

    bit_events = extract_bandsintown_events(soup, base_url, source_name)
    if bit_events:
        all_events.extend(bit_events)
        methods_used.append(f"Bandsintown ({len(bit_events)})")

    sk_events = extract_songkick_events(soup, base_url, source_name)
    if sk_events:
        all_events.extend(sk_events)
        methods_used.append(f"Songkick ({len(sk_events)})")

    tm_events = extract_ticketmaster_events(soup, base_url, source_name)
    if tm_events:
        all_events.extend(tm_events)
        methods_used.append(f"Ticketmaster ({len(tm_events)})")

    axs_events = extract_axs_events(soup, base_url, source_name)
    if axs_events:
        all_events.extend(axs_events)
        methods_used.append(f"AXS ({len(axs_events)})")

    etix_events = extract_etix_events(soup, base_url, source_name)
    if etix_events:
        all_events.extend(etix_events)
        methods_used.append(f"Etix ({len(etix_events)})")

    st_events = extract_seetickets_events(soup, base_url, source_name)
    if st_events:
        all_events.extend(st_events)
        methods_used.append(f"See Tickets ({len(st_events)})")

    # ── 6. Squarespace ──
    sq_events = extract_squarespace_events(soup, html, base_url, source_name)
    if sq_events:
        all_events.extend(sq_events)
        methods_used.append(f"Squarespace ({len(sq_events)})")

    # ── 7. Fallbacks ──
    # Timely HTML fallback: safe again because fetchers.py now sets Playwright's
    # timezone_id to America/Chicago, so the widget renders in Central. The
    # Timely-specific DOM parser also produces cleaner titles than the generic
    # repeating-structures extractor (which glues tag spans onto the heading).
    if not all_events:
        timely_html = extract_timely_from_html(soup, base_url, source_name)
        if timely_html:
            all_events.extend(timely_html)
            methods_used.append(f"Timely HTML ({len(timely_html)})")

    if not all_events:
        repeat_events = extract_repeating_structures(soup, base_url, source_name)
        if repeat_events:
            all_events.extend(repeat_events)
            methods_used.append(f"Repeating structures ({len(repeat_events)})")

    if not all_events:
        proximity_events = extract_by_date_proximity(soup, base_url, source_name)
        if proximity_events:
            all_events.extend(proximity_events)
            methods_used.append(f"Date proximity ({len(proximity_events)})")

    return _finalize(all_events, methods_used)


def _clean_description(text: str) -> str:
    """
    Strip HTML tags and decode HTML entities from description text.
    Handles raw HTML like '&lt;p&gt;Some text&lt;/p&gt;' and tagged HTML like '<p>Some text</p>'.
    """
    if not text:
        return ''

    # 1. Decode HTML entities FIRST (&lt; → <, &amp; → &, etc.)
    #    Run twice to catch double-encoded entities like &amp;amp;
    text = html.unescape(html.unescape(text))

    # 2. Strip HTML tags (<p>, <br>, <a href="...">, etc.)
    text = re.sub(r'<[^>]+>', ' ', text)

    # 3. Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # 4. Truncate to 200 chars
    if len(text) > 200:
        text = text[:197] + '...'

    return text


def _finalize(all_events: list, methods_used: list) -> list:
    """Apply universal garbage filter, description cleaning, and deduplication."""

    # FIX: Universal garbage title filter (applies to ALL methods)
    filtered = []
    garbage_count = 0
    for event in all_events:
        title = event.get('title', '')
        if _is_garbage_title(title):
            garbage_count += 1
            continue
        # Clean HTML from descriptions
        event['description'] = _clean_description(event.get('description', ''))
        filtered.append(event)

    if garbage_count:
        print(f"[GarbageFilter] Removed {garbage_count} garbage titles")

    # Deduplicate by title
    seen_titles = set()
    unique_events = []
    for event in filtered:
        title = event.get('title', '').lower().strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_events.append(event)

    for event in unique_events:
        event['_extraction_methods'] = methods_used

    return unique_events