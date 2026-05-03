"""
Locate918 Scraper - Venue-Specific Extractors
==============================================
Scrapers for specific Tulsa-area music and comedy venues:
  - Bricktown Comedy Club (SeatEngine)
  - Loony Bin Comedy Club (custom CMS)
  - Mabee Center / Cain's Ballroom / Tulsa Theater (rhp-events WP plugin)
  - The Church Studio (Elementor/WordPress)
  - Maggie's Music Box (Squarespace)
  - Route 66 Historical Village (Wix)
  - Living Arts of Tulsa (WordPress/Elementor)
  - Carney Fest (static site)
  - Jenks Planetarium (Eleyo)
  - River Parks Authority (SociableKit)
  - Magic City Books (BookManager CMS)
  - Tulsa Spotlight Theater (Wix Events)
  - Tulsa Mayfest (static)
  - Tulsa Oktoberfest
  - Rocklahoma
"""
"""
Locate918 Scraper - CMS & Platform API Extractors
===================================================
Extractors for CMS platforms with JSON APIs:
  - Expo Square (Saffire CMS)
  - Eventbrite API
  - Simpleview CMS (VisitTulsa.com)
  - SiteWrench CMS (Discovery Lab)
  - RecDesk (Tulsa Parks)
  - TicketLeap (Belafonte)
"""

import re
import json
import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin, quote
import httpx
from bs4 import BeautifulSoup

from scraperUtils import (
    HEADERS,
    extract_date_from_text,
    extract_time_from_text,
    text_has_date,
)


# ============================================================================
# SEATENGINE PLATFORM — Generic extractor for any SeatEngine-hosted venue
# ============================================================================
# Platform URL pattern: {venue-slug}-com.seatengine.com (also serves as CNAME
#   target for venues using their own domain, e.g. bricktowntulsa.com).
#
# Pages are fully server-rendered HTML — httpx is sufficient, skip Playwright.
#
# Detection signals (any one suffices):
#   - Hostname contains 'seatengine.com' OR is a key in SEATENGINE_VENUES
#   - HTML references 'cdn.seatengine.com' / 'files.seatengine.com'
#   - HTML contains 'Powered by SeatEngine' footer text
#   - HTML has id="mini-events" + class="event-list-item" markers
#
# DOM structure per card (.event-list-item):
#   Title:        .el-header a (text)
#   Event URL:    .el-header a[href]
#   Date range:   .el-date-range        (e.g. "March 22" or "March 27 - March 28")
#   Label:        .event-label          ("Special Event" / "Free Show" / absent)
#   Image:        .el-image img[src]
#   Single-show:  h6 text               → "Sun Mar 22 2026, 6:00 PM"
#   Multi-show:   .event-times-group    → h6.event-date + a.event-btn-inline per time
#
# Multi-day headliners emit ONE event per calendar day using the earliest
# showtime for that day.
#
# Known venues are registered in SEATENGINE_VENUES with precise metadata
# (address, category rules, description template). Unknown venues get a
# best-effort name extracted from og:site_name / <title> / hostname slug
# and leave address blank for downstream normalization to fill in.
# ============================================================================

# --- SeatEngine datetime format helpers ---

_SE_DT_FORMATS = [
    '%a %b %d %Y, %I:%M %p',   # "Sun Mar 22 2026, 6:00 PM"
    '%a %b %d %Y,  %I:%M %p',  # double-space variant
    '%a, %b %d, %Y %I:%M %p',  # "Fri, Mar 27, 2026 7:00 PM"
    '%a, %b %d, %Y  %I:%M %p', # double-space variant
]
_SE_DAY_FORMATS = [
    '%a, %b %d, %Y',  # "Fri, Mar 27, 2026"
    '%a %b %d %Y',    # "Fri Mar 27 2026"
]
_SE_TIME_FORMATS = [
    '%I:%M %p',
    ' %I:%M %p',
]


def _se_parse_dt(text: str) -> datetime | None:
    text = re.sub(r'  +', ' ', text.strip())
    for fmt in _SE_DT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _se_parse_day(text: str) -> datetime | None:
    text = re.sub(r'  +', ' ', text.strip())
    for fmt in _SE_DAY_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _se_parse_time(text: str) -> tuple[int, int] | None:
    text = text.strip()
    for fmt in _SE_TIME_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.hour, dt.minute
        except ValueError:
            pass
    return None


# --- Known-venue registry ---
# Keys: canonical lowercased hostnames (strip leading www.)
# Values: either a metadata dict or a string alias pointing to another key.
# Only fields that differ from _SEATENGINE_DEFAULT_META need be specified.

_SEATENGINE_DEFAULT_META = {
    'name':                 'SeatEngine Venue',
    'address':              '',
    'base_categories':      ['Live Entertainment'],
    'category_keywords':    {},   # lowercased title substring -> category
    'label_keywords':       {},   # lowercased label substring -> category
    'description_template': '{title} at {venue}.',
    'family_friendly':      None,
}

SEATENGINE_VENUES: dict = {
    # Bricktown Comedy Club — 5982 S Yale Ave, Tulsa, OK
    'bricktowntulsa.com': {
        'name':                 'Bricktown Comedy Club',
        'address':              '5982 S Yale Ave, Tulsa, OK 74135',
        'base_categories':      ['Comedy', 'Live Entertainment'],
        'category_keywords': {
            'open mic':  'Open Mic',
            'drag':      'Drag Show',
            'bingo':     'Drag Show',
            'magic':     'Magic Show',
            'magician':  'Magic Show',
            'improv':    'Improv',
        },
        'label_keywords': {
            'free': 'Free Event',
        },
        'description_template': '{title} performing live at {venue}, Tulsa.',
        'family_friendly':      None,
    },
    # Alias — SeatEngine's own subdomain for the same venue
    'bricktowntulsa-com.seatengine.com': 'bricktowntulsa.com',
}


# --- Detection & metadata resolution ---

def _se_canonical_host(url: str) -> str:
    host = urlparse((url or '').lower()).netloc.split(':')[0]
    if host.startswith('www.'):
        host = host[4:]
    return host


def _is_seatengine(html: str, url: str) -> bool:
    host = _se_canonical_host(url)
    if 'seatengine.com' in host or host in SEATENGINE_VENUES:
        return True
    if html:
        sample = html[:80000].lower()  # cap for perf on large pages
        if 'cdn.seatengine.com' in sample or 'files.seatengine.com' in sample:
            return True
        if 'powered by seatengine' in sample:
            return True
        if 'id="mini-events"' in sample and 'event-list-item' in sample:
            return True
    return False


def _resolve_seatengine_meta(url: str, html: str) -> dict:
    """Registry lookup with alias resolution; falls back to page extraction."""
    host = _se_canonical_host(url)
    entry = SEATENGINE_VENUES.get(host)
    seen = set()
    while isinstance(entry, str) and entry not in seen:
        seen.add(entry)
        entry = SEATENGINE_VENUES.get(entry)

    if isinstance(entry, dict):
        return {**_SEATENGINE_DEFAULT_META, **entry}

    # Unknown venue — do best-effort name extraction.
    meta = dict(_SEATENGINE_DEFAULT_META)
    if html:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            og = soup.select_one('meta[property="og:site_name"]')
            if og and og.get('content'):
                meta['name'] = og['content'].strip()
                return meta
            t = soup.select_one('title')
            if t:
                title_text = t.get_text(strip=True)
                for suf in (' — Events', ' | Events', ' - Events', ' Events',
                            ' — Calendar', ' | Calendar', ' - Calendar'):
                    if title_text.lower().endswith(suf.lower()):
                        title_text = title_text[: -len(suf)].strip()
                        break
                if title_text:
                    meta['name'] = title_text
                    return meta
        except Exception:
            pass

    # Final fallback — derive from hostname slug.
    slug = host
    if slug.endswith('.seatengine.com'):
        slug = slug[: -len('.seatengine.com')]
        if slug.endswith('-com'):
            slug = slug[: -len('-com')]
    else:
        slug = slug.rsplit('.', 1)[0] if '.' in slug else slug
    slug = slug.replace('-', ' ').replace('.', ' ').strip()
    if slug:
        meta['name'] = slug.title()
    return meta


def _seatengine_categories(title: str, label: str, meta: dict) -> list[str]:
    cats = list(meta.get('base_categories', []))
    tl = title.lower()
    ll = label.lower()
    for kw, cat in meta.get('category_keywords', {}).items():
        if kw in tl and cat not in cats:
            cats.append(cat)
    for kw, cat in meta.get('label_keywords', {}).items():
        if kw in ll and cat not in cats:
            cats.append(cat)
    return cats


# --- Main extractor ---

async def extract_seatengine_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Generic SeatEngine-platform extractor.

    Detects any SeatEngine-hosted venue (via hostname, asset URLs, or page
    markers) and parses the .event-list-item card grid into event records.
    Known venues (SEATENGINE_VENUES) get rich metadata (address, categories);
    unknown venues get a best-effort name derived from the page/URL.
    """
    if not _is_seatengine(html, url):
        return [], False

    meta       = _resolve_seatengine_meta(url, html)
    venue_name = meta['name']
    print(f"[SeatEngine] Detected '{venue_name}' — scraping via httpx")

    # Page is fully server-rendered; refetch via httpx if caller passed thin
    # or JS-stripped HTML that doesn't contain the event grid.
    if not html or 'event-list-item' not in html:
        try:
            target = url or f"https://{_se_canonical_host(url)}/events"
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(target, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[SeatEngine] Fetch error: {exc}")
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.event-list-item')
    print(f"[SeatEngine] Found {len(cards)} event cards")

    parsed   = urlparse(url or '')
    base_url = f"{parsed.scheme or 'https'}://{parsed.netloc}" if parsed.netloc else ''

    today     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events    = []
    seen_keys = set()
    desc_tpl  = meta.get('description_template', _SEATENGINE_DEFAULT_META['description_template'])

    for card in cards:
        a_tag = card.select_one('.el-header a')
        if not a_tag:
            continue
        title     = a_tag.get_text(strip=True)
        href      = a_tag.get('href', '')
        event_url = urljoin(base_url, href) if href else ''
        label     = card.select_one('.event-label')
        label_txt = label.get_text(strip=True) if label else ''
        img_tag   = card.select_one('.el-image img')
        image_url = img_tag['src'] if img_tag and img_tag.get('src') else ''

        # Determine show datetimes
        show_datetimes: list[datetime] = []
        time_groups = card.select('.event-times-group')

        if time_groups:
            # Multi-show card: one group per calendar day
            for group in time_groups:
                day_h6 = group.select_one('h6.event-date') or group.select_one('h6')
                day_dt = _se_parse_day(day_h6.get_text()) if day_h6 else None

                time_links = group.select('a.event-btn-inline')
                first_hm: tuple[int, int] | None = None
                for link in time_links:
                    hm = _se_parse_time(link.get_text())
                    if hm is not None:
                        if first_hm is None or (hm[0]*60 + hm[1]) < (first_hm[0]*60 + first_hm[1]):
                            first_hm = hm

                if day_dt and first_hm:
                    show_datetimes.append(day_dt.replace(hour=first_hm[0], minute=first_hm[1], second=0))
                elif day_dt:
                    show_datetimes.append(day_dt)
        else:
            # Single-show card: parse from h6
            h6 = card.select_one('h6')
            if h6:
                dt = _se_parse_dt(h6.get_text())
                if dt:
                    show_datetimes.append(dt)

        if not show_datetimes:
            print(f"[SeatEngine] Skipping (no parseable datetime): {title}")
            continue

        multi_day = len(show_datetimes) > 1

        for start_dt in show_datetimes:
            if future_only and start_dt.date() < today.date():
                continue

            dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            display_title = title
            if multi_day:
                display_title = f"{title} – {start_dt.strftime('%a %b %-d')}"

            desc = desc_tpl.format(title=title, venue=venue_name)
            if label_txt:
                desc += f" ({label_txt})"

            events.append({
                'title':           display_title,
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        '',
                'venue':           venue_name,
                'venue_address':   meta.get('address', ''),
                'description':     desc,
                'source_url':      event_url,
                'image_url':       image_url,
                'source_name':     source_name or venue_name,
                'categories':      _seatengine_categories(title, label_txt, meta),
                'outdoor':         False,
                'family_friendly': meta.get('family_friendly'),
            })

    print(f"[SeatEngine] Total events: {len(events)}")
    return events, True


# Backwards-compat alias — existing imports of the BCC-specific function
# continue to work (now dispatches through the generic SeatEngine extractor).
extract_bricktown_comedy_events = extract_seatengine_events

# ============================================================================
# LOONY BIN COMEDY CLUB TULSA — Custom CMS (loonybincomedy.com)
# ============================================================================
# Site:    https://tulsa.loonybincomedy.com/
# Method:  httpx — fully server-rendered HTML, all events on homepage
# Structure:
#   All shows live in: section.upcoming-events div.col-sm-3
#   Each card innerText lines:
#     [0] Title       e.g. "Jaron Myers"
#     [1] Label       e.g. "SPECIAL ENGAGEMENT | 18 & over"
#     [2] Date text   e.g. "March 26" or "March 27 - March 28"
#   Image: img[data-src] (lazy-loaded)
#   Show URL: a[href] → /ShowDetails/{showGuid}/{clubGuid}/{Name}/Tulsa_Loony_Bin
#   No show times exposed on listing page.
#
# Year inference: cards are in chronological order. Walk them in sequence and
#   increment the working year whenever the month number resets (e.g. Dec→Jan).
#
# Venue:   Loony Bin Comedy Club Tulsa
#          6808 S Memorial Dr, Tulsa, OK 74133
# Note:    18 & over venue → family_friendly: False
# ============================================================================

_LB_SOURCE_URL = 'https://tulsa.loonybincomedy.com/'
_LB_VENUE      = 'Loony Bin Comedy Club'
_LB_ADDR       = '6808 S Memorial Dr, Tulsa, OK 74133'

_LB_MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _lb_parse_month_day(text: str) -> tuple[int, int] | None:
    """
    Parse "March 25" or "March 27" → (month_number, day).
    Returns None if unparseable.
    """
    text = text.strip().lower()
    for month_name, month_num in _LB_MONTH_MAP.items():
        if text.startswith(month_name):
            rest = text[len(month_name):].strip()
            try:
                return month_num, int(rest)
            except ValueError:
                pass
    return None


def _lb_parse_date_range(date_text: str, year: int) -> tuple[datetime | None, datetime | None]:
    """
    Parse a Loony Bin date string into (start_dt, end_dt).
      "March 25"              → single day, end_dt = None
      "March 27 - March 28"  → two-day range
    Returns (None, None) on failure.
    """
    date_text = date_text.strip()
    if ' - ' in date_text:
        parts = date_text.split(' - ', 1)
        start_md = _lb_parse_month_day(parts[0])
        end_md   = _lb_parse_month_day(parts[1])
        if start_md and end_md:
            start_dt = datetime(year, start_md[0], start_md[1])
            end_year = year if end_md[0] >= start_md[0] else year + 1
            end_dt   = datetime(end_year, end_md[0], end_md[1])
            return start_dt, end_dt
    else:
        md = _lb_parse_month_day(date_text)
        if md:
            return datetime(year, md[0], md[1]), None
    return None, None


def _lb_categories(title: str, label: str) -> list[str]:
    cats = ['Comedy', 'Live Entertainment']
    tl, ll = title.lower(), label.lower()
    if 'open mic' in tl:
        cats.append('Open Mic')
    if 'special engagement' in ll:
        cats.append('Special Event')
    if 'trivia' in tl:
        cats.append('Trivia')
    if 'family' in tl or 'all ages' in tl:
        cats.append('Family Friendly')
    return cats


async def extract_loonybin_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from Loony Bin Comedy Club Tulsa (tulsa.loonybincomedy.com).

    All event data is server-rendered on the homepage.  Cards appear in
    chronological order with no year — the year is inferred by tracking
    month rollovers as we walk the list.
    """
    if 'loonybincomedy.com' not in url.lower():
        return [], False

    print(f"[LoonybinTulsa] Detected Loony Bin Comedy Club, scraping homepage...")

    # ── Fetch if no HTML provided ─────────────────────────────────────────────
    if not html or 'upcoming-events' not in html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_LB_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[LoonybinTulsa] Fetch error: {exc}")
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    cards = soup.select('section.upcoming-events .col-sm-3')
    print(f"[LoonybinTulsa] Found {len(cards)} event cards")

    today      = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    work_year  = today.year
    prev_month = 0
    events     = []
    seen_keys  = set()

    for card in cards:
        # ── Parse card text lines ─────────────────────────────────────────────
        lines = [l.strip() for l in card.get_text('\n').split('\n') if l.strip() and l.strip() != 'TICKETS']
        if len(lines) < 3:
            continue

        title     = lines[0]
        label     = lines[1]  # e.g. "SPECIAL ENGAGEMENT | 18 & over" or "18 & over"
        date_text = lines[2]

        # Skip placeholder/pass entries
        if any(skip in title.lower() for skip in ['gold pass', 'closed for']):
            continue

        a_tag  = card.select_one('a')
        img    = card.select_one('img')
        show_url  = a_tag['href'] if a_tag and a_tag.get('href') else _LB_SOURCE_URL
        image_url = img.get('data-src') or img.get('src') or '' if img else ''

        # ── Year inference: bump year on month rollover ───────────────────────
        start_md = _lb_parse_month_day(date_text.split(' - ')[0])
        if start_md:
            curr_month = start_md[0]
            if prev_month > 0 and curr_month < prev_month:
                work_year += 1
            prev_month = curr_month

        # ── Parse dates ───────────────────────────────────────────────────────
        start_dt, end_dt = _lb_parse_date_range(date_text, work_year)
        if not start_dt:
            print(f"[LoonybinTulsa] Skipping (no date): {title!r} — {date_text!r}")
            continue

        # ── Future filter ─────────────────────────────────────────────────────
        check_dt = end_dt or start_dt
        if future_only and check_dt.date() < today.date():
            continue

        # ── Dedup ─────────────────────────────────────────────────────────────
        dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # ── Build description ─────────────────────────────────────────────────
        label_clean = label.replace('|', '·').strip()
        desc = f"{title} live at the Loony Bin Comedy Club, Tulsa. ({label_clean})"

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           _LB_VENUE,
            'venue_address':   _LB_ADDR,
            'description':     desc,
            'source_url':      show_url,
            'image_url':       image_url,
            'source_name':     source_name or _LB_VENUE,
            'categories':      _lb_categories(title, label),
            'outdoor':         False,
            'family_friendly': False,
        })
        print(f"[LoonybinTulsa] Added: {title} on {start_dt.strftime('%Y-%m-%d')}")

    print(f"[LoonybinTulsa] Total events: {len(events)}")
    return events, True

# ============================================================================
# RHP-EVENTS WORDPRESS PLUGIN — Generic Extractor
# ============================================================================
# Sites:   Mabee Center (mabeecenter.com/mcevents/)
#          Cain's Ballroom (cainsballroom.com)
#          Tulsa Theater (tulsatheater.com/events/)
# Plugin:  rhp-events / RockHouseEvents — very common WP events plugin
# Method:  httpx — server-rendered HTML
# Structure: .rhpSingleEvent.rhp-event__single-event--list per event
#   Title:   .rhp-event__title--list
#   Date:    .singleEventDate → "Wed, Apr 08" or "Tue, June 02" (NO YEAR)
#   Time:    .rhp-event__time-text--list → "Start Time: 7pm" / "Doors: 6:30 pm"
#   Tagline: .rhp-event__tagline--list (presenter/series)
#   Age:     .rhp-event__age-restriction--list
#   Link:    first <a href> in card
#   Image:   img[src]
# Year:    Cards are chronological — infer year by tracking month rollovers
# ============================================================================

_RHP_VENUES = {
    'mabeecenter.com':     ('Mabee Center',   '7777 S Lewis Ave, Tulsa, OK 74171'),
    'cainsballroom.com':   ("Cain's Ballroom", '423 N Main St, Tulsa, OK 74103'),
    'tulsatheater.com':    ('Tulsa Theater',   '105 W Reconciliation Way, Tulsa, OK 74103'),
}

_RHP_TIME_RE = re.compile(
    r'(?:Doors|Start\s+Time|Show)[:\s]+(\d{1,2}(?::\d{2})?\s*(?:am|pm))',
    re.IGNORECASE,
)

_RHP_DATE_FORMATS = [
    '%a, %b %d',     # "Wed, Apr 08"
    '%a, %B %d',     # "Tue, June 02"
    '%a %b %d',      # "Wed Apr 08"
    '%a %B %d',      # "Tue June 02"
]


def _rhp_parse_date(date_text: str, year: int) -> datetime | None:
    """Parse rhp-events date string (no year) → naive datetime."""
    text = re.sub(r'\s+', ' ', date_text.strip())
    for fmt in _RHP_DATE_FORMATS:
        try:
            dt = datetime.strptime(f"{text} {year}", f"{fmt} %Y")
            return dt
        except ValueError:
            pass
    return None


def _rhp_parse_time(time_text: str) -> tuple[int, int] | None:
    """Extract (hour24, minute) from time string like 'Start Time: 7pm'."""
    if not time_text:
        return None
    m = _RHP_TIME_RE.search(time_text)
    raw = m.group(1).strip() if m else time_text.strip()
    for fmt in ('%I:%M %p', '%I %p', '%I:%M%p', '%I%p'):
        try:
            dt = datetime.strptime(raw.upper(), fmt)
            return dt.hour, dt.minute
        except ValueError:
            pass
    return None


def _rhp_categories(title: str, tagline: str) -> list[str]:
    cats = ['Live Entertainment']
    tl = (title + ' ' + tagline).lower()
    if any(w in tl for w in ['concert', 'tour', 'live', 'music', 'band', 'ballroom']):
        cats.append('Live Music')
    if any(w in tl for w in ['comedy', 'standup', 'stand-up']):
        cats.append('Comedy')
    if any(w in tl for w in ['baseball', 'basketball', 'sports', 'oru']):
        cats.append('Sports')
    if any(w in tl for w in ['family', 'homecoming', 'graduation', 'commencement']):
        cats.append('Family Friendly')
    return cats


async def extract_rhp_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Generic extractor for the rhp-events (RockHouseEvents) WordPress plugin.
    Handles Mabee Center, Cain's Ballroom, and Tulsa Theater.
    """
    domain = urlparse(url).netloc.lower().lstrip('www.')
    venue_info = None
    for key, val in _RHP_VENUES.items():
        if key in domain:
            venue_info = val
            break
    if not venue_info:
        return [], False

    venue_name, venue_addr = venue_info
    print(f"[RHPEvents] Detected {venue_name}, scraping rhp-events HTML...")

    if not html or 'rhpSingleEvent' not in html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[RHPEvents] Fetch error: {exc}")
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    # Broad selector: catches .rhpSingleEvent on both the homepage widget
    # (modifier --widget) and the full /events/ page (modifier --list), plus
    # .rhpEventSeries multi-show cards. Cards without the required title/date
    # children are skipped silently inside the loop.
    cards = soup.select('.rhpSingleEvent, .rhpEventSeries')
    print(f"[RHPEvents/{venue_name}] Found {len(cards)} event cards")

    today      = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    work_year  = today.year
    prev_month = 0
    events     = []
    seen_keys  = set()

    for card in cards:
        title_el   = card.select_one('.rhp-event__title--list, .rhp-event__title, h2.rhp-event__title--list, .eventTitleDiv h2, h2')
        # The date element carries multiple co-equal classes in the live DOM:
        #   <div class="rhp-event-series-date eventDateList rhp-event__date--list">
        # Legacy .singleEventDate kept as a fallback in case older widgets use it.
        date_el    = card.select_one('.rhp-event-series-date, .eventDateList, .rhp-event__date--list, .singleEventDate')
        time_el    = card.select_one('.rhp-event__time-text--list, .eventDoorStartDate')
        tagline_el = card.select_one('.rhp-event__tagline--list, .eventTagLine')
        age_el     = card.select_one('.rhp-event__age-restriction--list, .eventAgeRestriction')
        a_tag      = card.select_one('a.url[href], a[href*="/event/"], a[href]')
        img        = card.select_one('img')

        if not title_el or not date_el:
            continue

        title     = title_el.get_text(strip=True)
        date_text = date_el.get_text(strip=True)
        time_text = time_el.get_text(strip=True) if time_el else ''
        tagline   = tagline_el.get_text(strip=True) if tagline_el else ''
        age_text  = age_el.get_text(strip=True) if age_el else ''
        event_url = a_tag['href'] if a_tag else url
        image_url = img['src'] if img and img.get('src') else ''

        # ── Year inference ────────────────────────────────────────────────────
        month_match = re.search(
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|'
            r'march|april|june|july|august|september|october|november|december)\b',
            date_text, re.IGNORECASE
        )
        if month_match:
            month_abbr = month_match.group(1).lower()[:3]
            month_num  = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
                          'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}[month_abbr]
            if prev_month > 0 and month_num < prev_month:
                work_year += 1
            prev_month = month_num

        start_dt = _rhp_parse_date(date_text, work_year)
        if not start_dt:
            print(f"[RHPEvents] Skipping (no date): {title!r} — {date_text!r}")
            continue

        # ── Apply time ────────────────────────────────────────────────────────
        hm = _rhp_parse_time(time_text)
        if hm:
            start_dt = start_dt.replace(hour=hm[0], minute=hm[1])

        if future_only and start_dt.date() < today.date():
            continue

        dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        desc_parts = [title]
        if tagline:
            desc_parts.append(tagline)
        if age_text:
            desc_parts.append(age_text)
        if time_text:
            desc_parts.append(time_text)
        desc = ' — '.join(desc_parts)

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        '',
            'venue':           venue_name,
            'venue_address':   venue_addr,
            'description':     desc,
            'source_url':      event_url,
            'image_url':       image_url,
            'source_name':     source_name or venue_name,
            'categories':      _rhp_categories(title, tagline),
            'outdoor':         False,
            'family_friendly': None,
        })
        print(f"[RHPEvents/{venue_name}] Added: {title} on {start_dt.strftime('%Y-%m-%d %H:%M')}")

    print(f"[RHPEvents/{venue_name}] Total events: {len(events)}")
    return events, True


# ============================================================================
# THE CHURCH STUDIO — WordPress / Elementor Static HTML
# ============================================================================
# Site:    https://www.thechurchstudio.com/events/
# Method:  httpx — static WP/Elementor page
# Structure (2026 recon):
#   The /events/ page is a manually-built Elementor layout with NO events
#   plugin, NO events schema, and NO stable event-card selector. Past events
#   (going back to 2021) are mixed in with upcoming ones on the same page with
#   zero programmatic separation. Title/date formats vary per-event because
#   each section was designed by hand.
#
#   Anchor-first strategy: every ticketed upcoming event has a universe.com
#   or etix.com anchor. Past events' ticket links have mostly been removed
#   or expired, so these anchors naturally scope to "currently selling." For
#   each anchor: walk up to the enclosing <section>, extract title from the
#   nearest heading, and scan the section's text for any parseable date.
#   Skip events with no date (recurring "Tunes @ Noon" falls in this bucket).
#
# Venue:   The Church Studio / 304 S Trenton Ave, Tulsa, OK 74120
# ============================================================================

_CS_SOURCE_URL = 'https://www.thechurchstudio.com/events/'
_CS_VENUE      = 'The Church Studio'
_CS_ADDR       = '304 S Trenton Ave, Tulsa, OK 74120'

_CS_MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}

# Generic "[DOW,] Month Day[, Year]" pattern — finds ANY date in a text blob.
# Handles missing year for formats like "FRIDAY JULY 17".
_CS_DATE_SCAN_RE = re.compile(
    r'(?:(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+)?'
    r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'[\s,.]+(\d{1,2})(?:\s*&\s*\d{1,2})?(?:,?\s*(\d{4}))?',
    re.IGNORECASE
)

# Standalone day-of-week (e.g. Elementor often splits "Tuesday" onto its own
# heading above the date). Must be skipped when selecting a title.
_CS_DOW_ONLY_RE = re.compile(
    r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[.,\s]*$',
    re.IGNORECASE
)

# Titles/labels we never want to emit as an event title — these appear as
# button text, nav labels, or section headers in Elementor blocks.
_CS_JUNK_TITLE_RE = re.compile(
    r'^(GET TICKETS|MORE INFO|LEARN MORE|BUY NOW|THE CHURCH STUDIO PRESENTS|'
    r'PAST EVENTS|UPCOMING EVENTS|EVENTS|DONATE|SHOP|MEDIA|SUPPORT|ABOUT|'
    r'VISIT|LOUNGE|CONTACT|TOURS|MEMBERSHIP|HOME|MENU)$',
    re.IGNORECASE
)


def _cs_scan_for_date(text: str, today: datetime) -> datetime | None:
    """Find the most reliable month-day-year match in a blob of text.

    Prefers matches with an explicit year over those without. For year-less
    matches, defaults to this year, rolling forward if already past (so
    "JULY 20" in late April becomes this July)."""
    flat = re.sub(r'\s+', ' ', text)

    with_year: list[datetime]    = []
    without_year: list[datetime] = []

    for m in _CS_DATE_SCAN_RE.finditer(flat):
        month_str = m.group(1).lower()[:3]
        month_num = _CS_MONTH_MAP.get(month_str)
        if not month_num:
            continue
        try:
            day = int(m.group(2))
        except (ValueError, TypeError):
            continue

        year_str = m.group(3)
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                continue
            try:
                with_year.append(datetime(year, month_num, day))
            except ValueError:
                continue
        else:
            # No year given — use this year, or next if already past
            year = today.year
            try:
                cand = datetime(year, month_num, day)
            except ValueError:
                continue
            if cand.date() < today.date():
                try:
                    cand = datetime(year + 1, month_num, day)
                except ValueError:
                    continue
            without_year.append(cand)

    # Year-explicit matches are more reliable — prefer them
    if with_year:
        return with_year[0]
    if without_year:
        return without_year[0]
    return None


def _cs_classify_text_widget(text: str, today: datetime) -> str:
    """Classify a text-editor widget's text content for Church Studio events.

    Returns one of:
      'empty'    — nothing usable
      'date'     — matches a date/DOW fragment (FRIDAY, JULY 17, Tuesday May 5 2026, etc.)
      'junk'     — button label or venue boilerplate
      'title'    — looks like an event title (short, not a date, not junk)
      'desc'     — long paragraph, likely a description
    """
    if not text:
        return 'empty'
    t = text.strip()
    if len(t) < 3:
        return 'empty'

    # Pure day-of-week fragment
    if _CS_DOW_ONLY_RE.match(t):
        return 'date'

    # Contains a parseable month-day (with or without DOW/year) and no other content
    stripped_no_date = _CS_DATE_SCAN_RE.sub('', t).strip(' ,.')
    # Also strip DOW prefix
    stripped_no_date = re.sub(
        r'^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[.,\s]+',
        '', stripped_no_date, flags=re.IGNORECASE,
    ).strip(' ,.')
    # Trailing time (5:30 PM, 10:00 AM)
    stripped_no_date = re.sub(
        r'\d{1,2}:\d{2}\s*(?:am|pm)\.?$',
        '', stripped_no_date, flags=re.IGNORECASE,
    ).strip(' ,.')
    if _cs_scan_for_date(t, today) and len(stripped_no_date) < 4:
        return 'date'

    # Junk button labels / venue boilerplate
    if _CS_JUNK_TITLE_RE.match(t):
        return 'junk'

    # Length-based title vs description split
    if len(t) <= 140:
        return 'title'
    return 'desc'


def _cs_extract_title_and_desc(scope, today: datetime) -> tuple:
    """Walk text-editor and heading widgets in DOM order within scope, returning
    (title, description). Handles Church Studio's layout where EVERYTHING
    (date, title, description) is rendered as separate text-editor widgets
    with no <h*> tags at all.

    Title = first widget that classifies as 'title' (short, non-date, non-junk).
    Description = first widget that classifies as 'desc' (long paragraph)
                  appearing after the title.
    """
    title = ''
    desc  = ''

    # Elementor's text-editor widget is the primary carrier. Some layouts
    # also have heading widgets; include both and walk in document order.
    widgets = scope.select(
        '[data-widget_type="text-editor.default"], '
        '[data-widget_type="heading.default"], '
        '.elementor-widget-text-editor, '
        '.elementor-widget-heading'
    )

    for w in widgets:
        text = w.get_text(' ', strip=True)
        klass = _cs_classify_text_widget(text, today)

        if klass == 'title' and not title:
            # Title-case all-caps titles for display
            title = text if text != text.upper() else text.title()
        elif klass == 'desc' and title and not desc:
            desc = text[:400]
            break

    return title, desc


async def extract_church_studio_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from The Church Studio (thechurchstudio.com/events/).

    The page has no events plugin, no schema, no stable card selector, and mixes
    past events (back to 2021) with upcoming. But every ticketed upcoming event
    has a universe.com or etix.com anchor, so we anchor off those: for each
    link, walk up to the enclosing <section>, extract title from the nearest
    heading, find a date anywhere in the section text, and filter past events.
    """
    if 'thechurchstudio.com' not in url.lower():
        return [], False

    print(f"[ChurchStudio] Detected The Church Studio events page...", flush=True)

    if not html or 'thechurchstudio' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_CS_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[ChurchStudio] Fetch error: {exc}", flush=True)
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Strip nav/header/footer so nav submenu links don't pollute our anchors
    for el in soup.select('nav, header, .header, .fl-page-nav, #fl-page-nav, '
                          'footer, .footer, .fl-page-footer'):
        el.decompose()

    # Find all ticketing anchors — the only reliable event markers on this page
    anchors = soup.select(
        'a[href*="universe.com"], a[href*="etix.com"], a[href*="eventbrite.com"]'
    )
    print(f"[ChurchStudio] Found {len(anchors)} ticketing anchor(s)", flush=True)

    events    = []
    seen_urls = set()
    skipped_no_date   = 0
    skipped_past      = 0
    skipped_no_title  = 0
    skipped_no_section = 0

    for a in anchors:
        href = (a.get('href') or '').strip()
        if not href or not href.startswith('http'):
            continue
        if href in seen_urls:
            continue

        # Walk up to the tightest event-wrapping scope.
        #
        # Elementor's layout hierarchy is: section > row > COLUMN > widget.
        # Column scope is CRITICAL for Church Studio: sections frequently host
        # multiple events side-by-side (recon confirmed HIT LIST + Speaker Wars
        # share section 7dca08b, with each event in its own column). Walking
        # up to <section> would return the combined widget set of both events,
        # making it impossible to tell which title/date goes with which link.
        #
        # Fall back to <section> only if no column is found (shouldn't happen
        # on Elementor pages, but safe default).
        column  = None
        section = None
        p = a
        for _ in range(15):
            p = p.parent
            if p is None:
                break
            classes = p.get('class', []) if hasattr(p, 'get') else []
            if column is None and any('elementor-column' in c for c in classes):
                column = p
            if section is None and p.name == 'section':
                section = p
            if column is not None and section is not None:
                break

        scope = column if column is not None else section
        if scope is None:
            skipped_no_section += 1
            continue

        # Title + description from text-editor widgets in column DOM order.
        # Church Studio's page has NO <h*> tags — everything is text-editor.
        title, desc = _cs_extract_title_and_desc(scope, today)
        if not title:
            skipped_no_title += 1
            continue

        # Date — scan the full scope's text. Split-widget dates ("FRIDAY" +
        # "JULY 17") become one string via get_text(' '). Year-explicit
        # matches are preferred over year-less (Speaker Wars has both
        # "MONDAY JULY 20" and "Mon, July 20, 2026" — the latter wins).
        scope_text = scope.get_text(' ', strip=True)
        start_dt = _cs_scan_for_date(scope_text, today)
        if not start_dt:
            # Recurring or undated (e.g. "Tunes @ Noon" standing ticket)
            skipped_no_date += 1
            print(f"[ChurchStudio] Skipping (no date): {title[:70]}", flush=True)
            continue

        # Past-event filter — stale ticket links on past-event sections
        # would otherwise produce pollution
        if future_only and start_dt.date() < today.date():
            skipped_past += 1
            continue

        seen_urls.add(href)

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        '',
            'venue':           _CS_VENUE,
            'venue_address':   _CS_ADDR,
            'description':     desc or title,
            'source_url':      href,
            'image_url':       '',
            'source_name':     source_name or _CS_VENUE,
            'categories':      ['Live Music', 'Live Entertainment', 'Arts & Culture'],
            'outdoor':         False,
            'family_friendly': None,
        })
        print(
            f"[ChurchStudio] Added: {title} on {start_dt.strftime('%Y-%m-%d')}",
            flush=True,
        )

    print(
        f"[ChurchStudio] Total: {len(events)} event(s)  "
        f"(skipped: {skipped_past} past, {skipped_no_date} no-date, "
        f"{skipped_no_title} no-title, {skipped_no_section} no-section)",
        flush=True,
    )
    return events, True


# ============================================================================
# MAGGIE'S OK -- Squarespace Event Page
# ============================================================================
# Site:    https://maggiesok.com/events
# Method:  httpx -- Squarespace static HTML
# Structure:
#   Each event is a div block identified by finding <p> tags matching
#   'DOW Month Day' and walking up 2 levels to the event container div.
#   Block lines: Title / Date / Time / Price
#   TBA entries with no specific date are ignored automatically.
#   Nav tabs never appear in these blocks.
# Venue:   Maggie's Music Box / 3910 E 31st St, Tulsa, OK 74135
# ============================================================================

_MAGGIES_SOURCE_URL = 'https://maggiesok.com/events'
_MAGGIES_VENUE      = "Maggie's Music Box"
_MAGGIES_ADDR       = '3910 E 31st St, Tulsa, OK 74135'

_MAGGIES_DOW_DATE_RE = re.compile(
    r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
    r'\s+(january|february|march|april|may|june|july|august|september|october|november|december)'
    r'\s+(\d{1,2})',
    re.IGNORECASE
)

_MAGGIES_TIME_RE = re.compile(r'(\d{1,2}(?::\d{2})?)\s*(am|pm)', re.IGNORECASE)
_MAGGIES_NOON_RE = re.compile(r'open\s+at\s+noon|noon', re.IGNORECASE)

_MAGGIES_MONTH_MAP = {
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}


def _maggies_parse_block(block_text: str, work_year: int) -> tuple:
    """Parse a Maggies event block into (title, start_dt, desc)."""
    lines = [l.strip() for l in block_text.split('\n') if l.strip()]
    if len(lines) < 2:
        return '', None, ''
    date_idx = next((i for i, l in enumerate(lines) if _MAGGIES_DOW_DATE_RE.match(l)), None)
    if date_idx is None:
        return '', None, ''
    title = lines[date_idx - 1] if date_idx > 0 else ''
    if not title or len(title) < 2:
        return '', None, ''
    m = _MAGGIES_DOW_DATE_RE.match(lines[date_idx])
    month_num = _MAGGIES_MONTH_MAP.get(m.group(2).lower())
    day = int(re.sub(r'\D', '', m.group(3)))
    try:
        start_dt = datetime(work_year, month_num, day)
    except ValueError:
        return '', None, ''
    hour, minute = 20, 30
    for line in lines[date_idx + 1:]:
        if _MAGGIES_NOON_RE.search(line):
            hour, minute = 12, 0
            break
        tm = _MAGGIES_TIME_RE.search(line)
        if tm:
            raw = tm.group(1)
            suffix = tm.group(2).lower()
            if ':' in raw:
                h, mn = map(int, raw.split(':'))
            else:
                h, mn = int(raw), 0
            if suffix == 'pm' and h != 12:
                h += 12
            elif suffix == 'am' and h == 12:
                h = 0
            hour, minute = h, mn
            break
    start_dt = start_dt.replace(hour=hour, minute=minute)
    price_lines = [l for l in lines if '$' in l or 'no cover' in l.lower()]
    desc = "Live music at Maggie's Music Box."
    if price_lines:
        desc += f' {price_lines[0]}'
    return title, start_dt, desc


async def extract_maggies_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple:
    """
    Extract events from Maggies Music Box (maggiesok.com/events).
    Uses DOM p-tag approach: finds date paragraphs, walks up 2 levels to
    the event block div. No nav tab contamination.
    """
    if 'maggiesok.com' not in url.lower():
        return [], False

    print(f'[MaggiesOK] Detected Maggies Music Box...')

    if not html or 'maggiesok' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_MAGGIES_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f'[MaggiesOK] Fetch error: {exc}')
            return [], False

    soup      = BeautifulSoup(html, 'html.parser')
    today     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    work_year = today.year
    prev_month = 0
    events    = []
    seen_keys = set()
    seen_blocks = set()

    date_paras = [
        p for p in soup.find_all('p')
        if _MAGGIES_DOW_DATE_RE.match(p.get_text(strip=True))
    ]
    print(f'[MaggiesOK] Found {len(date_paras)} date paragraphs')

    for p in date_paras:
        block_el = p.parent and p.parent.parent
        if not block_el:
            continue
        block_text = block_el.get_text(separator='\n')
        block_key  = block_text.strip()[:80]
        if block_key in seen_blocks:
            continue
        seen_blocks.add(block_key)

        m = _MAGGIES_DOW_DATE_RE.match(p.get_text(strip=True))
        if m:
            curr_month = _MAGGIES_MONTH_MAP.get(m.group(2).lower(), 0)
            if prev_month > 0 and curr_month < prev_month:
                work_year += 1
            prev_month = curr_month

        title, start_dt, desc = _maggies_parse_block(block_text, work_year)
        if not title or not start_dt:
            continue

        if future_only and start_dt.date() < today.date():
            continue

        dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        '',
            'venue':           _MAGGIES_VENUE,
            'venue_address':   _MAGGIES_ADDR,
            'description':     desc,
            'source_url':      _MAGGIES_SOURCE_URL,
            'image_url':       '',
            'source_name':     source_name or _MAGGIES_VENUE,
            'categories':      ['Live Music', 'Live Entertainment'],
            'outdoor':         False,
            'family_friendly': None,
        })
        print(f"[MaggiesOK] Added: {title} on {start_dt.strftime('%Y-%m-%d %H:%M')}")

    print(f'[MaggiesOK] Total events: {len(events)}')
    return events, True


# ============================================================================
# ROUTE 66 HISTORICAL VILLAGE — Wix Static HTML
# ============================================================================
# Site:    https://www.route66village.com/tulsaevents
# Method:  httpx — Wix static page, ~2 events per year
# Structure: h2 headings contain date + title (e.g. "February 14, 2026
#            Centennial Heart of 66 Community Wedding")
#            or "March 2026   Whistle Stop Chili Challenge Details Coming Soon"
# Venue:   Route 66 Historical Village / 3770 Southwest Blvd, Tulsa, OK 74107
# ============================================================================

_R66_SOURCE_URL = 'https://www.route66village.com/tulsaevents'
_R66_VENUE      = 'Route 66 Historical Village'
_R66_ADDR       = '3770 Southwest Blvd, Tulsa, OK 74107'

_R66_DATE_RE = re.compile(
    r'(january|february|march|april|may|june|july|august|september|october|november|december)'
    r'\s+(\d{1,2})?,?\s*(\d{4})',
    re.IGNORECASE
)

_R66_MONTH_MAP = {
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
}


async def extract_route66_village_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from Route 66 Historical Village (route66village.com/tulsaevents).
    Wix site with ~2 events per year described in h2 headings.
    """
    if 'route66village.com' not in url.lower():
        return [], False

    print(f"[Route66Village] Detected Route 66 Historical Village events page...")

    if not html or 'route66village' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_R66_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[Route66Village] Fetch error: {exc}")
            return [], False

    soup     = BeautifulSoup(html, 'html.parser')
    today    = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events   = []
    seen_keys = set()

    # Find all headings that contain a date
    for heading in soup.find_all(['h1','h2','h3','h4','p']):
        text = heading.get_text(separator=' ', strip=True)
        if len(text) < 5 or len(text) > 300:
            continue

        m = _R66_DATE_RE.search(text)
        if not m:
            continue

        month_num = _R66_MONTH_MAP.get(m.group(1).lower())
        year      = int(m.group(3))

        if m.group(2):
            # Specific day given
            day = int(m.group(2))
        else:
            # Month-only date (e.g. "March 2026") — use last day of month
            # so the event stays upcoming as long as the month isn't fully over
            import calendar
            day = calendar.monthrange(year, month_num)[1]

        try:
            start_dt = datetime(year, month_num, day)
        except ValueError:
            continue

        if future_only and start_dt.date() < today.date():
            continue

        # Title = text after the date portion, or from next sibling heading
        date_end   = m.end()
        title_part = re.sub(r'^[\s\-–:,]+', '', text[date_end:]).strip()

        # Clean up "Details Coming Soon" etc.
        title_part = re.sub(r'\s+details coming soon\.?', '', title_part, flags=re.IGNORECASE).strip()
        title_part = re.sub(r'\s+', ' ', title_part)

        if not title_part or len(title_part) < 4:
            # Try next sibling
            nxt = heading.find_next_sibling()
            if nxt:
                title_part = nxt.get_text(strip=True)[:100]
        if not title_part or len(title_part) < 4:
            continue

        # Find ticket/detail link
        event_url = _R66_SOURCE_URL
        link = heading.find('a') or heading.find_next('a')
        if link and link.get('href','').startswith('http') and 'route66village' in link.get('href',''):
            event_url = link['href']

        # Image
        img_el    = heading.find_next('img')
        image_url = img_el['src'] if img_el and img_el.get('src','').startswith('http') else ''

        dedup_key = f"{title_part.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        events.append({
            'title':           title_part,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        '',
            'venue':           _R66_VENUE,
            'venue_address':   _R66_ADDR,
            'description':     f"{title_part} at the Route 66 Historical Village, Tulsa.",
            'source_url':      event_url,
            'image_url':       image_url,
            'source_name':     source_name or _R66_VENUE,
            'categories':      ['Community', 'Festival', 'Arts & Culture'],
            'outdoor':         True,
            'family_friendly': True,
        })
        print(f"[Route66Village] Added: {title_part} on {start_dt.strftime('%Y-%m-%d')}")

    print(f"[Route66Village] Total events: {len(events)}")
    return events, True


# ============================================================================
# LIVING ARTS OF TULSA -- WordPress / Elementor Exhibitions Page
# ============================================================================
# Site:    https://livingarts.org/exhibitions/
# Method:  httpx — WP + Astra + Elementor, fully server-rendered HTML.
# Structure (2026 recon):
#   The /exhibitions/ page is a manually-built Elementor layout — NOT rendered
#   by the MEC events plugin (which powers /calendar/ and /events/ instead).
#   Each exhibition date-block lives in one <section class="elementor-top-section">
#   with a unique data-id. Within each top-section:
#     - An icon-list widget holds the date range ("January 2-17",
#       "February 6-March 14", etc.) — no year in the string; year lives only
#       in the "2026 EXHIBITION CALENDAR" h2 above.
#     - A heading widget (one per exhibition) holds the title. Some date-blocks
#       host TWO simultaneous exhibitions in different galleries (e.g. January
#       had "24 Hours of Wonder" + "Contours of Time"), so a single top-section
#       may contain multiple heading widgets — each is its own exhibition
#       sharing the same date range.
#     - Text-editor widget holds the description.
#     - Button widget (optional) holds the catalogue/ticket link.
#     - Images are CSS background-image on .elementor-widget-wrap, NOT <img>.
#   Date format uses ASCII hyphens only (no bullets, en-dashes, em-dashes).
#   No past/current/upcoming markers in the DOM — status is derived from date.
# Venue:   Living Arts of Tulsa / 307 E Reconciliation Way, Tulsa, OK 74120
# ============================================================================

_LA_SOURCE_URL = 'https://livingarts.org/exhibitions/'
_LA_VENUE      = 'Living Arts of Tulsa'
_LA_ADDR       = '307 E Reconciliation Way, Tulsa, OK 74120'

_LA_MONTH_MAP = {
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
    'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,
    'sep':9,'oct':10,'nov':11,'dec':12,
}

# Matches "January 2-17", "February 6-March 14", "August 7-22", or bare
# "December 4". Hyphen separator is required for ranges. Any end day without
# an explicit end month inherits the start month.
_LA_DATE_RANGE_RE = re.compile(
    r'^(january|february|march|april|may|june|july|august|september|october|november|december)'
    r'\s+(\d{1,2})'
    r'(?:\s*-\s*(?:(january|february|march|april|may|june|july|august|september|october|november|december)\s+)?(\d{1,2}))?'
    r'\s*$',
    re.IGNORECASE
)

# Page-level heading used to pull out the calendar year. Matches things like
# "2026 Exhibition Calendar" or "2026 EXHIBITION CALENDAR".
_LA_YEAR_HEADING_RE = re.compile(
    r'(20\d{2})\s+EXHIBITION\s+CALENDAR',
    re.IGNORECASE
)

# CSS background-image URL extraction (images are never <img> on this page)
_LA_BG_IMAGE_RE = re.compile(
    r'background-image\s*:\s*url\(\s*(["\']?)([^)"\']+?)\1\s*\)',
    re.IGNORECASE
)


def _la_parse_date_range(line: str, year: int) -> tuple:
    """Parse 'January 2-17', 'February 6-March 14', or 'December 4' into a
    (start_dt, end_dt) tuple. If only one day is given, start == end."""
    m = _LA_DATE_RANGE_RE.match(line.strip())
    if not m:
        return None, None

    start_month = _LA_MONTH_MAP.get(m.group(1).lower())
    if not start_month:
        return None, None
    try:
        start_day = int(m.group(2))
    except (ValueError, TypeError):
        return None, None

    if m.group(4):  # has an end-day
        end_month = _LA_MONTH_MAP.get(m.group(3).lower()) if m.group(3) else start_month
        if not end_month:
            return None, None
        try:
            end_day = int(m.group(4))
        except (ValueError, TypeError):
            return None, None
    else:
        end_month = start_month
        end_day   = start_day

    try:
        start_dt = datetime(year, start_month, start_day)
        end_dt   = datetime(year, end_month, end_day, 23, 59)
        # If end precedes start, range crosses year boundary (Dec 28-Jan 5)
        if end_dt < start_dt:
            end_dt = datetime(year + 1, end_month, end_day, 23, 59)
        return start_dt, end_dt
    except (ValueError, TypeError):
        return None, None


def _la_extract_year(soup) -> int:
    """Pull the calendar year from the '2026 Exhibition Calendar' heading.
    Falls back to current year if no match."""
    # Scan all heading-ish elements
    for el in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        m = _LA_YEAR_HEADING_RE.search(el.get_text(' ', strip=True))
        if m:
            return int(m.group(1))
    # Last resort: scan entire page text
    m = _LA_YEAR_HEADING_RE.search(soup.get_text(' ', strip=True))
    return int(m.group(1)) if m else datetime.now().year


def _la_find_bg_image(scope) -> str:
    """Find the first CSS background-image URL in any element's inline style
    within the given scope (section or column). Checks the scope element
    itself as well as its descendants, since column-level styles often
    live on the column tag directly."""
    # Check the scope's own style first
    if hasattr(scope, 'get'):
        own_style = scope.get('style') or ''
        if own_style:
            m = _LA_BG_IMAGE_RE.search(own_style)
            if m:
                return m.group(2).strip()
    # Then descendants
    for el in scope.find_all(style=True):
        m = _LA_BG_IMAGE_RE.search(el.get('style', ''))
        if m:
            return m.group(2).strip()
    return ''


async def extract_living_arts_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple:
    """
    Extract exhibitions from Living Arts of Tulsa (livingarts.org/exhibitions/).

    Uses DOM structure rather than flat-text walking: each exhibition occupies
    a top-level Elementor section with a date-range icon-list and one or more
    heading widgets. Some sections host multiple simultaneous exhibitions in
    different galleries — all heading widgets within a section share the
    section's date range.
    """
    if 'livingarts.org' not in url.lower() or '/exhibitions' not in url.lower():
        return [], False

    print(f'[LivingArts] Detected Living Arts exhibitions page...', flush=True)

    if not html or 'livingarts' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_LA_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f'[LivingArts] Fetch error: {exc}', flush=True)
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    year  = _la_extract_year(soup)
    print(f'[LivingArts] Using calendar year {year}', flush=True)

    events    = []
    seen_keys = set()
    skipped_no_date  = 0
    skipped_no_title = 0
    skipped_past     = 0

    # Every exhibition date-block is a top-level Elementor section with a
    # unique data-id. Filter to those that actually contain a date widget
    # (the /exhibitions/ page also has header/footer top-sections).
    top_sections = soup.select('section.elementor-top-section[data-id]')
    print(f'[LivingArts] Found {len(top_sections)} top-level section(s)', flush=True)

    for section in top_sections:
        date_widget = section.select_one(
            '.elementor-widget-icon-list .elementor-icon-list-text'
        )
        if not date_widget:
            continue  # not an exhibition section (header/footer/etc.)

        date_text = date_widget.get_text(' ', strip=True)
        start_dt, end_dt = _la_parse_date_range(date_text, year)
        if not start_dt:
            skipped_no_date += 1
            print(f'[LivingArts] Unparseable date: {date_text!r}', flush=True)
            continue

        # Past-event filter — exhibition is past once its end date has passed
        if future_only and end_dt.date() < today.date():
            skipped_past += 1
            continue

        # Find all heading widgets in this section. Some blocks host two
        # simultaneous exhibitions in different galleries (e.g. January had
        # "24 Hours of Wonder" + "Contours of Time"), so each heading becomes
        # its own event sharing the section's date range.
        heading_widgets = section.select('.elementor-widget-heading')

        # Filter out the page-title heading if it's somehow nested here
        # (guard against sections that wrap the "2026 EXHIBITION CALENDAR" h2).
        valid_headings = []
        for h in heading_widgets:
            title_text = h.get_text(' ', strip=True)
            if not title_text or len(title_text) > 120 or len(title_text) < 3:
                continue
            if _LA_YEAR_HEADING_RE.search(title_text):
                continue
            # Skip date-only headings (just in case)
            if _la_parse_date_range(title_text, year)[0]:
                continue
            valid_headings.append((h, title_text))

        if not valid_headings:
            skipped_no_title += 1
            print(f'[LivingArts] No valid title headings for date {date_text!r}',
                  flush=True)
            continue

        # Default fallback link (site URL) — replaced by a button's href if
        # one exists in the same column as the heading
        fallback_url = url or _LA_SOURCE_URL

        for heading_widget, title in valid_headings:
            # Scope description / button / image to the heading's column if
            # possible — otherwise fall back to the whole section. BS4's
            # find_parent(class_=lambda) doesn't invoke the lambda for
            # class-matching, so we walk ancestors manually.
            col = None
            p = heading_widget
            for _ in range(15):
                p = p.parent
                if p is None:
                    break
                p_classes = p.get('class', []) if hasattr(p, 'get') else []
                if any('elementor-col' in c for c in p_classes):
                    col = p
                    break
            scope = col if col is not None else section

            # Description: first text-editor widget in the column
            desc = ''
            desc_widget = scope.select_one('.elementor-widget-text-editor')
            if desc_widget:
                desc = desc_widget.get_text(' ', strip=True)[:500]

            # Link: button widget in the column (falls back to page URL)
            link_el = scope.select_one('.elementor-widget-button a[href], a.elementor-button[href]')
            link = link_el.get('href', '').strip() if link_el else fallback_url
            if not link or not link.startswith('http'):
                link = fallback_url

            # Image: CSS background-image. Check column first (for multi-
            # exhibition blocks where each col has its own image), fall
            # back to any image in the top-section if the column has none.
            image_url = _la_find_bg_image(scope) or _la_find_bg_image(section)

            dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            events.append({
                'title':           title,
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                if end_dt and end_dt != start_dt else '',
                'venue':           _LA_VENUE,
                'venue_address':   _LA_ADDR,
                'description':     desc or title,
                'source_url':      link,
                'image_url':       image_url,
                'source_name':     source_name or _LA_VENUE,
                'categories':      ['Arts & Culture', 'Exhibition', 'Visual Art'],
                'outdoor':         False,
                'family_friendly': True,
            })
            print(
                f"[LivingArts] Added: {title} "
                f"({start_dt.strftime('%Y-%m-%d')} – {end_dt.strftime('%Y-%m-%d')})",
                flush=True,
            )

    print(
        f'[LivingArts] Total: {len(events)} exhibition(s)  '
        f'(skipped: {skipped_past} past, {skipped_no_date} no-date, '
        f'{skipped_no_title} no-title)',
        flush=True,
    )
    return events, True


# ============================================================================
# RHP-EVENTS WORDPRESS PLUGIN — Generic Extractor
# ============================================================================
# Sites:   Mabee Center (mabeecenter.com/mcevents/)
#          Cain's Ballroom (cainsballroom.com)
#          Tulsa Theater (tulsatheater.com/events/)
# Plugin:  rhp-events / RockHouseEvents — very common WP events plugin
# Method:  httpx — server-rendered HTML
# Structure: .rhpSingleEvent.rhp-event__single-event--list per event
#   Title:   .rhp-event__title--list
#   Date:    .singleEventDate → "Wed, Apr 08" or "Tue, June 02" (NO YEAR)
#   Time:    .rhp-event__time-text--list → "Start Time: 7pm" / "Doors: 6:30 pm"
#   Tagline: .rhp-event__tagline--list (presenter/series)
#   Age:     .rhp-event__age-restriction--list
#   Link:    first <a href> in card
#   Image:   img[src]
# Year:    Cards are chronological — infer year by tracking month rollovers
# CARNEY FEST — carneyfest.com
# ============================================================================
# Site:    https://carneyfest.com
# Method:  httpx — static HTML, one page with both days listed
# Structure:
#   Day 1: Cain's Ballroom  — "FRIDAY • MAY 1, 2026 • 5:30 PM"
#   Day 2: The Church Studio — "SATURDAY • MAY 2, 2026 • 10:00 AM"
#   Emits ONE multi-day event spanning both days (start=Day1, end=Day2)
#   Ticket links: etix for Cain's, universe.com for Church Studio
# Venue:   Multiple — description notes both venues
# ============================================================================

_CF_SOURCE_URL = 'https://carneyfest.com'
_CF_VENUE      = "Cain's Ballroom / The Church Studio"
_CF_ADDR       = 'Tulsa, OK'

_CF_DATE_RE = re.compile(
    r'(friday|saturday|sunday|monday|tuesday|wednesday|thursday)'
    r'\s*[•·]\s*'
    r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+(\d{1,2}),?\s*(\d{4})?'
    r'(?:\s*[•·]\s*(\d{1,2}:\d{2}\s*(?:am|pm)))?',
    re.IGNORECASE
)

_CF_MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}


async def extract_carneyfest_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract Carney Fest as a single multi-day event (carneyfest.com).
    Day 1 at Cain's Ballroom, Day 2 at The Church Studio.
    Emits one event: start = Day 1, end = Day 2.
    """
    if 'carneyfest.com' not in url.lower():
        return [], False

    print(f"[CarneyFest] Detected carneyfest.com...")

    if not html or 'carneyfest' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_CF_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[CarneyFest] Fetch error: {exc}")
            return [], False

    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Parse all dated day lines
    day_dts: list[datetime] = []
    for m in _CF_DATE_RE.finditer(text):
        mn = _CF_MONTH_MAP.get(m.group(2).lower()[:3])
        if not mn:
            continue
        yr = int(m.group(4)) if m.group(4) else today.year
        # Default times: Day 1 (Fri) = 5:30pm, Day 2 (Sat) = 10:00am
        dow = m.group(1).lower()
        default_h, default_m = (17, 30) if dow == 'friday' else (10, 0)
        try:
            dt = datetime(yr, mn, int(m.group(3)), default_h, default_m)
        except ValueError:
            continue
        # Override with explicit time if present
        if m.group(5):
            try:
                t = datetime.strptime(m.group(5).strip().upper(), '%I:%M %p')
                dt = dt.replace(hour=t.hour, minute=t.minute)
            except ValueError:
                pass
        day_dts.append(dt)

    if not day_dts:
        print(f"[CarneyFest] No dates found")
        return [], False

    day_dts = sorted(set(day_dts))
    start_dt = day_dts[0]
    end_dt   = day_dts[-1]

    if future_only and end_dt.date() < today.date():
        print(f"[CarneyFest] Event is in the past, skipping")
        return [], True

    # Grab the main ticket link (prefer universe.com for Church Studio day)
    ticket_url = _CF_SOURCE_URL
    for a in soup.select('a[href*="universe.com"], a[href*="etix.com"]'):
        href = a.get('href', '')
        if href.startswith('http'):
            ticket_url = href
            break

    event = {
        'title':           'Carney Fest',
        'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'venue':           _CF_VENUE,
        'venue_address':   _CF_ADDR,
        'description':     (
            f"Carney Fest {start_dt.year}: two-day music festival. "
            f"Day 1 at Cain's Ballroom, Day 2 at The Church Studio, Tulsa."
        ),
        'source_url':      ticket_url,
        'image_url':       '',
        'source_name':     source_name or 'Carney Fest',
        'categories':      ['Live Music', 'Festival', 'Live Entertainment'],
        'outdoor':         False,
        'family_friendly': True,
    }

    print(f"[CarneyFest] Added: Carney Fest {start_dt.strftime('%Y-%m-%d')} – {end_dt.strftime('%Y-%m-%d')}")
    return [event], True

# ============================================================================
# JENKS PLANETARIUM — Eleyo Community Education Platform
# ============================================================================
# Site:    https://jenksps.ce.eleyo.com/planetarium
# Method:  Playwright — the URL redirects to a JS-rendered search page:
#          https://jenksps.ce.eleyo.com/search?redirected_yet=true&sf[category]=121
#          All 11 show cards are rendered client-side via React/JS.
# Structure (innerText after JS renders):
#   Each show card separated by "View more info":
#     Title   — short line at start of block (< 80 chars)
#     Desc    — long paragraph
#     Date    — "Sat, Mar 28" (no year)
#     Time    — "11:00 AM - 12:00 PM" or "6:30 - 7:30 PM"
#     Venue   — "Jenks Planetarium"
#   Year inferred by month rollover (cards roughly chronological)
# Venue:   Jenks Planetarium / 205 E B St, Jenks, OK 74037
# ============================================================================

_JP_SOURCE_URL  = 'https://jenksps.ce.eleyo.com/search?redirected_yet=true&sf%5Bcategory%5D=121'
_JP_VENUE       = 'Jenks Planetarium'
_JP_ADDR        = '205 E B St, Jenks, OK 74037'

_JP_DATE_RE = re.compile(
    r'^(mon|tue|wed|thu|fri|sat|sun),\s+'
    r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+(\d{1,2})$',
    re.IGNORECASE
)

_JP_TIME_RE = re.compile(r'(\d{1,2}:\d{2})\s*(AM|PM)', re.IGNORECASE)

_JP_MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}

_JP_SKIP_LINES = {
    'sign in','skip to content','explore all programs','11 results','view',
    'name','newest','relevance','start date','sort by','m-f','days','time',
    'category','age/grade','location','catalogue','jenks planetarium',
    'view more info', 'starting soon',
}


def _jp_parse_time(time_str: str) -> tuple[int, int]:
    """Parse '11:00 AM' or '6:30' (assume PM for evening) → (hour24, min)."""
    m = _JP_TIME_RE.search(time_str)
    if m:
        parts = m.group(1).split(':')
        h, mn = int(parts[0]), int(parts[1])
        if m.group(2).upper() == 'PM' and h != 12:
            h += 12
        elif m.group(2).upper() == 'AM' and h == 12:
            h = 0
        return h, mn
    # No AM/PM — check if it looks like evening (< 10 = PM)
    parts = time_str.split(':')
    if len(parts) == 2:
        h = int(parts[0])
        if h < 10:
            h += 12  # assume PM
        return h, int(parts[1])
    return 19, 0  # default 7pm


async def extract_jenks_planetarium_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract shows from Jenks Planetarium (jenksps.ce.eleyo.com/planetarium).

    The page redirects to a JS-rendered Eleyo search page. Requires Playwright
    to get the rendered HTML. Parses the innerText by splitting on 'View more info'
    separators, then extracts title / date / time from each block.
    """
    if 'jenksps.ce.eleyo.com' not in url.lower():
        return [], False

    print(f"[JenksPlanetarium] Detected Jenks Planetarium (Eleyo)...")

    # The html passed in may be the /planetarium redirect page (no data).
    # We need the search results page — fetch it via httpx (server-renders enough).
    fetch_url = _JP_SOURCE_URL
    if not html or 'View more info' not in html:
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                resp = await client.get(fetch_url, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[JenksPlanetarium] Fetch error: {exc}")
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    text  = soup.get_text(separator='\n')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Split on "View more info" — each block is one show card
    blocks = text.split('View more info')
    print(f"[JenksPlanetarium] Found {len(blocks)-1} show blocks")

    work_year  = today.year
    prev_month = 0
    events     = []
    seen_keys  = set()

    for block in blocks[:-1]:  # last block is footer
        lines = [l.strip() for l in block.split('\n') if l.strip()]

        # Find title: first non-skip line under 80 chars
        title = ''
        for line in lines:
            if line.lower() not in _JP_SKIP_LINES and len(line) < 80 and len(line) > 3:
                # Skip filter/nav fragments
                if not any(line.startswith(s) for s in ('M-F','Days ','Time ','Sort')):
                    title = line
                    break
        if not title:
            continue

        # Find date line: "Sat, Mar 28"
        date_line = next((l for l in lines if _JP_DATE_RE.match(l)), None)
        if not date_line:
            continue

        dm = _JP_DATE_RE.match(date_line)
        month_abbr = dm.group(2).lower()[:3]
        month_num  = _JP_MONTH_MAP.get(month_abbr)
        day        = int(dm.group(3))

        # Year inference
        if prev_month > 0 and month_num < prev_month:
            work_year += 1
        prev_month = month_num

        # Find time line
        time_line = next((l for l in lines if re.search(r'\d{1,2}:\d{2}', l) and ('AM' in l.upper() or 'PM' in l.upper() or ':' in l)), None)
        h, mn = _jp_parse_time(time_line) if time_line else (19, 0)

        try:
            start_dt = datetime(work_year, month_num, day, h, mn)
        except ValueError:
            continue

        # Parse end time if present (e.g. "11:00 AM - 12:00 PM")
        end_dt = None
        if time_line and ' - ' in time_line:
            end_part = time_line.split(' - ')[-1].strip()
            eh, emn  = _jp_parse_time(end_part)
            try:
                end_dt = datetime(work_year, month_num, day, eh, emn)
            except ValueError:
                pass

        if future_only and start_dt.date() < today.date():
            continue

        dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # Description: longest line in block
        desc = max((l for l in lines if len(l) > 50 and l.lower() not in _JP_SKIP_LINES), key=len, default=title)[:300]

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           _JP_VENUE,
            'venue_address':   _JP_ADDR,
            'description':     desc,
            'source_url':      f'https://jenksps.ce.eleyo.com/courses/category/121/jenks-planetarium/planetarium-shows',
            'image_url':       '',
            'source_name':     source_name or _JP_VENUE,
            'categories':      ['Education', 'Family Friendly', 'Science', 'Community'],
            'outdoor':         False,
            'family_friendly': True,
        })
        print(f"[JenksPlanetarium] Added: {title} on {start_dt.strftime('%Y-%m-%d %H:%M')}")

    print(f"[JenksPlanetarium] Total shows: {len(events)}")
    return events, True


# ============================================================================
# RIVER PARKS AUTHORITY — SociableKit Facebook Events Widget
# ============================================================================
# Site:    https://www.riverparks.org/events/events
# Method:  httpx — fetch SociableKit iframe directly
#          URL: https://widgets.sociablekit.com/facebook-page-events/iframe/32201
#          Embed ID 32201 is hardcoded (tied to River Parks Facebook page)
#          Free tier shows 5 events only (no Load More via httpx)
# Structure: JSON-LD script[type="application/ld+json"] per event +
#            visible text for real location (JSON-LD has masked address)
#            Text pattern per event:
#              "Month D, YYYY @ H:MM am/pm [- end]"
#              "Title"
#              "Location string"
#              "Hosted By ..."
# Note:    GCal iframe (calendar ID ending in ...212e) already handled by
#          Playwright fetcher + extract_gcal_events. This extractor adds the
#          SociableKit Facebook events on top.
# Venue:   River Parks / Tulsa, OK (varies per event)
# ============================================================================

_RP_SOURCE_URL      = 'https://www.riverparks.org/events/events'
_RP_SK_IFRAME_URL   = 'https://widgets.sociablekit.com/facebook-page-events/iframe/32201'
_RP_DEFAULT_VENUE   = 'River Parks'
_RP_DEFAULT_ADDR    = 'Tulsa, OK'

_RP_DATE_RE = re.compile(
    r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+(\d{1,2}),\s+(\d{4})\s+@\s+(\d{1,2}:\d{2}\s*(?:am|pm))',
    re.IGNORECASE
)

_RP_MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}


async def extract_riverparks_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from River Parks Authority (riverparks.org/events/events).

    The page embeds a SociableKit Facebook Events widget (embed ID 32201).
    This extractor fetches the iframe URL directly to get events not captured
    by the GCal Playwright interceptor. Uses JSON-LD for start/end times and
    visible text for real venue addresses.
    """
    if 'riverparks.org' not in url.lower():
        return [], False

    print(f"[RiverParks] Detected River Parks, fetching SociableKit iframe...")

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(_RP_SK_IFRAME_URL, headers=HEADERS)
            resp.raise_for_status()
            sk_html = resp.text
    except Exception as exc:
        print(f"[RiverParks] SociableKit fetch error: {exc}")
        return [], False

    soup  = BeautifulSoup(sk_html, 'html.parser')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Parse JSON-LD for structured start/end times ──────────────────────────
    jsonld_events: dict[str, dict] = {}
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.get_text())
            if data.get('@type') == 'Event':
                name = data.get('name', '').strip()
                if name:
                    jsonld_events[name] = {
                        'start': data.get('startDate', ''),
                        'end':   data.get('endDate', ''),
                        'desc':  re.sub(r'<[^>]+>', '', data.get('description', ''))[:200],
                        'url':   data.get('url', _RP_SOURCE_URL),
                    }
        except Exception:
            pass

    print(f"[RiverParks] Found {len(jsonld_events)} JSON-LD events")

    # ── Parse visible text for real location info ─────────────────────────────
    # Pattern per card: "Month D, YYYY @ time" / "Title" / "Location" / "Hosted By..."
    text = soup.get_text(separator='\n')
    blocks = text.split('Read More')

    # Build location map: title → location string
    location_map: dict[str, str] = {}
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        # Find date line
        date_idx = next((i for i, l in enumerate(lines) if _RP_DATE_RE.search(l)), None)
        if date_idx is None:
            continue
        # Title: line after date
        if date_idx + 1 < len(lines):
            title = lines[date_idx + 1]
            # Location: line after title (not "Hosted By")
            if date_idx + 2 < len(lines):
                loc = lines[date_idx + 2]
                if not loc.lower().startswith('hosted by') and len(loc) > 5:
                    location_map[title] = loc

    # ── Build events from JSON-LD ─────────────────────────────────────────────
    events    = []
    seen_keys = set()

    for title, ev in jsonld_events.items():
        start_str = ev['start']
        if not start_str:
            continue

        try:
            # ISO datetime with Z suffix → UTC → local (assume UTC-5/CDT)
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            # Convert to naive local (CDT = UTC-5)
            from datetime import timezone, timedelta as _td
            start_dt = start_dt.astimezone(timezone(timedelta(hours=-5))).replace(tzinfo=None)
        except Exception:
            continue

        end_dt = None
        if ev['end']:
            try:
                end_dt = datetime.fromisoformat(ev['end'].replace('Z', '+00:00'))
                end_dt = end_dt.astimezone(timezone(timedelta(hours=-5))).replace(tzinfo=None)
            except Exception:
                pass

        if future_only and start_dt.date() < today.date():
            continue

        dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        venue_addr = location_map.get(title, _RP_DEFAULT_ADDR)
        # Extract venue name (first part before comma)
        venue_name = venue_addr.split(',')[0].strip() if ',' in venue_addr else _RP_DEFAULT_VENUE

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           venue_name or _RP_DEFAULT_VENUE,
            'venue_address':   venue_addr,
            'description':     ev['desc'] or title,
            'source_url':      ev['url'] or _RP_SOURCE_URL,
            'image_url':       '',
            'source_name':     source_name or _RP_DEFAULT_VENUE,
            'categories':      ['Outdoors', 'Community', 'Recreation'],
            'outdoor':         True,
            'family_friendly': True,
        })
        print(f"[RiverParks] Added: {title} on {start_dt.strftime('%Y-%m-%d %H:%M')}")

    print(f"[RiverParks] Total events: {len(events)}")
    return events, True


# ============================================================================
# MAGIC CITY BOOKS — BookManager CMS
# ============================================================================
# Site:    https://magiccitybooks.com/programs-services/events
# Method:  httpx — BookManager JS-rendered page (Playwright needed for full
#          render, but the page is also accessible via the BookManager API:
#          POST https://api.bookmanager.com/customer/event/v2/list?_cb=9907424
#          Store ID: 9907424 (stable, tied to Magic City Books account)
# API response: {list: [{event_id, title, date_start, time_start, time_end,
#                        event_type, location, description, ...}]}
# Fallback: parse rendered HTML h3/h4 → date → time → type → venue blocks
# Venue:   Magic City Books / 221 E Archer St, Tulsa, OK 74103
# ============================================================================

_MCB_SOURCE_URL = 'https://magiccitybooks.com/programs-services/events'
_MCB_API_URL    = 'https://api.bookmanager.com/customer/event/v2/list?_cb=9907424'
_MCB_VENUE      = 'Magic City Books'
_MCB_ADDR       = '221 E Archer St, Tulsa, OK 74103'
_MCB_STORE_ID   = '9907424'

_MCB_DATE_RE = re.compile(
    r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+'
    r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+(\d{1,2})(?:st|nd|rd|th)?,\s+(\d{4})',
    re.IGNORECASE
)

_MCB_TIME_RE = re.compile(r'(\d{1,2}:\d{2})\s*(AM|PM)', re.IGNORECASE)

_MCB_MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}

_MCB_SKIP_TITLES = {
    'events', 'stay in the know', 'find us at', 'programs & services',
    'about', 'shop', 'support', 'visit & contact',
}


def _mcb_parse_time(time_str: str) -> tuple[int, int]:
    m = _MCB_TIME_RE.search(time_str)
    if not m:
        return 19, 0
    h, mn = map(int, m.group(1).split(':'))
    if m.group(2).upper() == 'PM' and h != 12:
        h += 12
    elif m.group(2).upper() == 'AM' and h == 12:
        h = 0
    return h, mn


def _mcb_parse_block(lines: list[str]) -> tuple:
    """Parse a BookManager event block into (title, start_dt, end_dt, venue, type, desc)."""
    if len(lines) < 3:
        return None, None, None, '', '', ''

    title = lines[0]
    if title.lower() in _MCB_SKIP_TITLES or len(title) < 3:
        return None, None, None, '', '', ''

    # Find date line
    date_idx = next((i for i, l in enumerate(lines) if _MCB_DATE_RE.match(l)), None)
    if date_idx is None:
        return None, None, None, '', '', ''

    dm = _MCB_DATE_RE.match(lines[date_idx])
    month_num = _MCB_MONTH_MAP.get(dm.group(2).lower()[:3])
    day       = int(dm.group(3))
    year      = int(dm.group(4))

    # Start time: line after date
    start_h, start_m = 19, 0
    end_h,   end_m   = 0, 0
    end_dt_obj = None

    if date_idx + 1 < len(lines):
        start_h, start_m = _mcb_parse_time(lines[date_idx + 1])
    if date_idx + 2 < len(lines):
        end_h, end_m = _mcb_parse_time(lines[date_idx + 2])

    try:
        start_dt = datetime(year, month_num, day, start_h, start_m)
        if end_h or end_m:
            end_dt_obj = datetime(year, month_num, day, end_h, end_m)
    except ValueError:
        return None, None, None, '', '', ''

    # Type and venue
    event_type = ''
    venue      = _MCB_ADDR
    for line in lines[date_idx + 3:]:
        if 'Events' in line and len(line) < 40:
            event_type = line.strip()
        elif ('Magic City Books' in line or 'Tulsa' in line or 'Church' in line or 'Ave' in line or 'St.' in line) and not event_type:
            venue = line.strip().lstrip()
        elif ('Magic City Books' in line or 'Tulsa' in line or 'Ave' in line or 'St.' in line):
            venue = line.strip().lstrip()
            break

    # Description: long lines after venue
    desc_lines = [l for l in lines[date_idx + 4:] if len(l) > 30 and 'Read More' not in l and 'Buy Books' not in l and 'RSVP' not in l]
    desc = desc_lines[0][:250] if desc_lines else ''

    return title, start_dt, end_dt_obj, venue, event_type, desc


async def extract_magic_city_books_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from Magic City Books (magiccitybooks.com).

    Tries the BookManager JSON API first (POST to /customer/event/v2/list).
    Falls back to parsing the rendered HTML h3/h4 event blocks.
    """
    if 'magiccitybooks.com' not in url.lower():
        return [], False

    print(f"[MagicCityBooks] Detected Magic City Books events page...")

    today     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events    = []
    seen_keys = set()

    # ── Strategy 1: BookManager API ──────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            api_resp = await client.post(
                _MCB_API_URL,
                json={},
                headers={**HEADERS, 'Content-Type': 'application/json', 'Origin': 'https://magiccitybooks.com', 'Referer': _MCB_SOURCE_URL},
            )
            api_resp.raise_for_status()
            api_data = api_resp.json()

        items = api_data.get('list', api_data.get('items', api_data.get('events', [])))
        print(f"[MagicCityBooks] API returned {len(items)} events")

        for item in items:
            title = (item.get('title') or item.get('name') or item.get('event_name') or '').strip()
            if not title:
                continue

            # Try various date field names
            date_str  = item.get('date_start') or item.get('date') or item.get('start_date') or ''
            time_str  = item.get('time_start') or item.get('start_time') or ''
            time_end  = item.get('time_end') or item.get('end_time') or ''
            loc       = item.get('location') or item.get('venue') or _MCB_ADDR
            desc_raw  = item.get('description') or item.get('desc') or ''
            desc      = re.sub(r'<[^>]+>', ' ', desc_raw)[:200].strip()
            ev_type   = item.get('event_type') or item.get('type') or ''
            ev_url    = item.get('url') or item.get('link') or _MCB_SOURCE_URL

            if not date_str:
                continue

            try:
                start_dt = datetime.fromisoformat(date_str.replace('Z', ''))
                if time_str:
                    h, mn = _mcb_parse_time(time_str)
                    start_dt = start_dt.replace(hour=h, minute=mn)
            except Exception:
                continue

            end_dt = None
            if time_end:
                try:
                    h, mn = _mcb_parse_time(time_end)
                    end_dt = start_dt.replace(hour=h, minute=mn)
                except Exception:
                    pass

            if future_only and start_dt.date() < today.date():
                continue

            dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            is_free = 'free' in ev_type.lower() if ev_type else True
            events.append({
                'title':           title,
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
                'venue':           _MCB_VENUE if 'Magic City' in loc else loc.split(',')[0].strip(),
                'venue_address':   loc if loc != _MCB_ADDR else _MCB_ADDR,
                'description':     desc or title,
                'source_url':      ev_url,
                'image_url':       '',
                'source_name':     source_name or _MCB_VENUE,
                'categories':      ['Arts & Culture', 'Literary', 'Community'] + (['Free Event'] if is_free else ['Ticketed']),
                'outdoor':         False,
                'family_friendly': None,
            })
            print(f"[MagicCityBooks] API: {title} on {start_dt.strftime('%Y-%m-%d')}")

        if events:
            print(f"[MagicCityBooks] Total via API: {len(events)}")
            return events, True

    except Exception as exc:
        print(f"[MagicCityBooks] API error: {exc}, falling back to HTML parse")

    # ── Strategy 2: Parse rendered HTML ──────────────────────────────────────
    if not html or 'magiccitybooks' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_MCB_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[MagicCityBooks] HTML fetch error: {exc}")
            return [], False

    soup = BeautifulSoup(html, 'html.parser')

    # Find all h3/h4 that look like event titles
    for heading in soup.find_all(['h3', 'h4']):
        title_text = heading.get_text(strip=True)
        if title_text.lower() in _MCB_SKIP_TITLES or len(title_text) < 3:
            continue

        # Walk up to find a container with a date
        container = heading.parent
        for _ in range(5):
            text = container.get_text(separator='\n') if container else ''
            if _MCB_DATE_RE.search(text):
                break
            container = container.parent if container else None

        if not container:
            continue

        lines = [l.strip() for l in container.get_text(separator='\n').split('\n')
                 if l.strip() and l.strip() != '-']

        title, start_dt, end_dt, venue, ev_type, desc = _mcb_parse_block(lines)
        if not title or not start_dt:
            continue

        if future_only and start_dt.date() < today.date():
            continue

        dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        venue_name = _MCB_VENUE if 'Magic City' in venue else venue.split(',')[0].strip()
        is_free    = 'free' in ev_type.lower() if ev_type else True

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           venue_name,
            'venue_address':   venue if venue else _MCB_ADDR,
            'description':     desc or title,
            'source_url':      _MCB_SOURCE_URL,
            'image_url':       '',
            'source_name':     source_name or _MCB_VENUE,
            'categories':      ['Arts & Culture', 'Literary', 'Community'] + (['Free Event'] if is_free else ['Ticketed']),
            'outdoor':         False,
            'family_friendly': None,
        })
        print(f"[MagicCityBooks] HTML: {title} on {start_dt.strftime('%Y-%m-%d')}")

    print(f"[MagicCityBooks] Total via HTML: {len(events)}")
    return events, True

# ============================================================================
# TULSA SPOTLIGHT THEATER — Wix Events (warmup-data JSON)
# ============================================================================
# Site: https://www.tulsaspotlighttheater.com/box-office
# Method: httpx — the page is a Wix site that server-side renders all event
#         data into a <script id="wix-warmup-data" type="application/json">
#         tag. No separate API call needed — parse that tag directly.
# Path:   warmupData.appsWarmupData[appKey][widgetKey].events.events[]
# Fields: id, title, slug, scheduling.config.{startDate,endDate,timeZoneId},
#         location.address, description, mainImage.url
# URLs:   https://www.tulsaspotlighttheater.com/event-info/{slug}
# ============================================================================

_SPOTLIGHT_SOURCE_URL = 'https://www.tulsaspotlighttheater.com/box-office'
_SPOTLIGHT_EVENT_BASE = 'https://www.tulsaspotlighttheater.com/event-info/'
_SPOTLIGHT_VENUE      = 'Tulsa Spotlight Theater'
_SPOTLIGHT_ADDR       = '1381 Riverside Dr, Tulsa, OK 74127'


def _spotlight_categories(title: str, description: str = '') -> list[str]:
    text = (title + ' ' + description).lower()
    cats = ['Arts & Culture', 'Theater']
    if any(w in text for w in ['children', 'kids', 'camp', 'youth', 'family']):
        cats.append('Family Friendly')
    if 'magic' in text or 'magician' in text:
        cats.append('Magic')
    if 'drunkard' in text or 'melodrama' in text:
        cats.append('Comedy')
    if 'showcase' in text or 'camp' in text:
        cats.append('Education')
    return cats


async def extract_spotlight_theater_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from Tulsa Spotlight Theater's Wix-powered box office page.
    Wix SSR embeds all event data in a JSON blob inside <script id="wix-warmup-data">.
    """
    if 'tulsaspotlighttheater.com' not in url.lower():
        return [], False

    print(f"[SpotlightTheater] Detected Tulsa Spotlight Theater, parsing Wix warmup data...")

    from bs4 import BeautifulSoup
    from dateutil import parser as date_parser

    page_html = html
    if not page_html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_SPOTLIGHT_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                page_html = resp.text
        except Exception as e:
            print(f"[SpotlightTheater] Fetch error: {e}")
            return [], True

    soup = BeautifulSoup(page_html, 'html.parser')
    warmup_tag = soup.find('script', {'id': 'wix-warmup-data'})
    if not warmup_tag:
        print(f"[SpotlightTheater] wix-warmup-data tag not found")
        return [], True

    try:
        warmup = json.loads(warmup_tag.string)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"[SpotlightTheater] JSON parse error: {e}")
        return [], True

    apps = warmup.get('appsWarmupData', {})
    raw_events = []
    for app_val in apps.values():
        for widget_val in app_val.values():
            candidate = widget_val.get('events', {}).get('events', [])
            if candidate:
                raw_events = candidate
                break
        if raw_events:
            break

    if not raw_events:
        print(f"[SpotlightTheater] No events found in warmup data")
        return [], True

    print(f"[SpotlightTheater] Found {len(raw_events)} raw events")

    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    seen: set = set()

    for ev in raw_events:
        title = (ev.get('title') or '').strip()
        if not title:
            continue

        scheduling = ev.get('scheduling', {}).get('config', {})
        start_raw  = scheduling.get('startDate', '')
        end_raw    = scheduling.get('endDate', '')

        try:
            start_dt = date_parser.parse(start_raw).replace(tzinfo=None)
        except Exception:
            print(f"[SpotlightTheater] Could not parse start date: {start_raw}")
            continue

        if future_only and start_dt < cutoff:
            continue

        dedup_key = f"{title.lower()}|{start_dt.date()}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        end_dt = None
        if end_raw:
            try:
                end_dt = date_parser.parse(end_raw).replace(tzinfo=None)
            except Exception:
                pass

        location    = ev.get('location', {})
        address     = location.get('address') or _SPOTLIGHT_ADDR
        description = (ev.get('description') or ev.get('about') or '').strip()
        main_image  = ev.get('mainImage', {})
        image_url   = main_image.get('url', '') if isinstance(main_image, dict) else ''
        slug        = ev.get('slug', '')
        event_url   = (_SPOTLIGHT_EVENT_BASE + slug) if slug else _SPOTLIGHT_SOURCE_URL
        categories  = _spotlight_categories(title, description)
        is_family   = 'Family Friendly' in categories

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           _SPOTLIGHT_VENUE,
            'venue_address':   address,
            'description':     description[:500] if description else '',
            'source_url':      event_url,
            'image_url':       image_url,
            'source_name':     source_name or _SPOTLIGHT_VENUE,
            'categories':      categories,
            'outdoor':         False,
            'family_friendly': is_family,
        })
        print(f"[SpotlightTheater] Added: {title} on {start_dt.strftime('%Y-%m-%d')}")

    print(f"[SpotlightTheater] Total events extracted: {len(events)}")
    return events, True


# ============================================================================
# TULSA MAYFEST — Static/Hardcoded (Squarespace site under construction)
# ============================================================================
# Site: https://www.tulsamayfest.org/
# Method: Static — as of 2026 the site is in rebuild ("WEBSITE UPDATES IN
#         PROGRESS") with no events API or structured event pages.
#         Known 2026 events are hardcoded from homepage content.
#         Re-evaluate for live scraping once the site is rebuilt.
#
# 2026 Format: "Mayfest Road Trip" — multiple events on Route 66
#   - Local Art Show @ Mother Road Market:     May 15–17 (Fri–Sun)
#   - Student Art Display @ Renaissance Square: Every Saturday in May
#     (May 2, 9, 16, 23, 30) — elementary, middle & high school art
#   - Centennial Cruise (car cruise + music):   May 29–30 (Fri–Sat)
# ============================================================================

_MAYFEST_SOURCE_URL = 'https://www.tulsamayfest.org/'
_MAYFEST_YEAR       = 2026

_MAYFEST_EVENTS_STATIC = [
    {
        'title':         'Tulsa Mayfest — Local Art Show',
        'start_time':    f'{_MAYFEST_YEAR}-05-15T10:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-17T18:00:00',
        'venue':         'Mother Road Market',
        'venue_address': '1036 E 11th St, Tulsa, OK 74120',
        'description':   (
            'Tulsa International Mayfest 2026 Local Art Show on Route 66 at Mother Road Market. '
            'Featuring local artists as part of the Mayfest Road Trip. May 15–17.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Community', 'Free Event'],
        'outdoor':       True,
        'family_friendly': True,
    },
    {
        'title':         'Tulsa Mayfest — Student Art Display (May 2)',
        'start_time':    f'{_MAYFEST_YEAR}-05-02T10:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-02T17:00:00',
        'venue':         'Renaissance Square Event Center',
        'venue_address': '111 N Main St, Tulsa, OK 74103',
        'description':   (
            'Tulsa Mayfest 2026 Student Art Display — elementary, middle, and high school '
            'student artwork on Route 66 at Renaissance Square Event Center. Every Saturday in May.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Family Friendly', 'Education', 'Free Event'],
        'outdoor':       False,
        'family_friendly': True,
    },
    {
        'title':         'Tulsa Mayfest — Student Art Display (May 9)',
        'start_time':    f'{_MAYFEST_YEAR}-05-09T10:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-09T17:00:00',
        'venue':         'Renaissance Square Event Center',
        'venue_address': '111 N Main St, Tulsa, OK 74103',
        'description':   (
            'Tulsa Mayfest 2026 Student Art Display — elementary, middle, and high school '
            'student artwork on Route 66 at Renaissance Square Event Center. Every Saturday in May.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Family Friendly', 'Education', 'Free Event'],
        'outdoor':       False,
        'family_friendly': True,
    },
    {
        'title':         'Tulsa Mayfest — Local Art Show & Student Art Display (May 16)',
        'start_time':    f'{_MAYFEST_YEAR}-05-16T10:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-16T18:00:00',
        'venue':         'Mother Road Market & Renaissance Square',
        'venue_address': '1036 E 11th St, Tulsa, OK 74120',
        'description':   (
            'Tulsa Mayfest 2026 — Local Art Show at Mother Road Market (May 15–17) '
            'and Student Art Display at Renaissance Square Event Center. Both on Route 66.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Family Friendly', 'Education', 'Free Event'],
        'outdoor':       True,
        'family_friendly': True,
    },
    {
        'title':         'Tulsa Mayfest — Student Art Display (May 23)',
        'start_time':    f'{_MAYFEST_YEAR}-05-23T10:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-23T17:00:00',
        'venue':         'Renaissance Square Event Center',
        'venue_address': '111 N Main St, Tulsa, OK 74103',
        'description':   (
            'Tulsa Mayfest 2026 Student Art Display — elementary, middle, and high school '
            'student artwork on Route 66 at Renaissance Square Event Center. Every Saturday in May.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Family Friendly', 'Education', 'Free Event'],
        'outdoor':       False,
        'family_friendly': True,
    },
    {
        'title':         'Tulsa Mayfest — Centennial Cruise',
        'start_time':    f'{_MAYFEST_YEAR}-05-29T17:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-30T22:00:00',
        'venue':         'Route 66, Tulsa',
        'venue_address': 'Route 66, Tulsa, OK',
        'description':   (
            'Tulsa Mayfest 2026 Centennial Cruise — car cruise and local live music along '
            'Route 66 in Tulsa. May 29–30 as part of the Mayfest Road Trip.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Music', 'Live Music', 'Community', 'Free Event'],
        'outdoor':       True,
        'family_friendly': True,
    },
    {
        'title':         'Tulsa Mayfest — Student Art Display & Centennial Cruise (May 30)',
        'start_time':    f'{_MAYFEST_YEAR}-05-30T10:00:00',
        'end_time':      f'{_MAYFEST_YEAR}-05-30T22:00:00',
        'venue':         'Renaissance Square & Route 66',
        'venue_address': '111 N Main St, Tulsa, OK 74103',
        'description':   (
            'Tulsa Mayfest 2026 — Student Art Display at Renaissance Square Event Center '
            'plus the Centennial Cruise along Route 66. Live local music throughout.'
        ),
        'image_url':     '',
        'categories':    ['Arts & Culture', 'Festival', 'Music', 'Family Friendly', 'Free Event'],
        'outdoor':       True,
        'family_friendly': True,
    },
]


async def extract_tulsamayfest_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Return hardcoded Tulsa Mayfest 2026 events.

    The tulsamayfest.org site is under reconstruction as of early 2026 and
    has no structured events API or event pages.  Known events are derived
    from homepage text.  Re-evaluate for live scraping once the site is rebuilt.
    """
    if 'tulsamayfest.org' not in url.lower():
        return [], False

    print(f"[TulsaMayfest] Detected tulsamayfest.org — returning static 2026 events...")

    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []

    for ev in _MAYFEST_EVENTS_STATIC:
        if future_only:
            try:
                start_dt = datetime.strptime(ev['start_time'], '%Y-%m-%dT%H:%M:%S')
                if start_dt < cutoff:
                    continue
            except Exception:
                pass

        events.append({
            **ev,
            'source_url':  _MAYFEST_SOURCE_URL,
            'source_name': source_name or 'Tulsa International Mayfest',
            'location':    'Tulsa',
        })

    print(f"[TulsaMayfest] Returning {len(events)} static events")
    return events, True

# ============================================================================
# TULSA OKTOBERFEST — Annual German Festival, Tulsa OK
# ============================================================================
# Site: https://tulsaoktoberfest.org/
# CMS:  WordPress static
# Method: httpx — scrapes the festival-guide page for dates.
#         Falls back to known/projected dates.
#
# 2026: October 22–25, 2100 S. Jackson Ave (River West Festival Park), Tulsa OK
# Historical pattern: Thursday–Sunday in mid-to-late October.
# ============================================================================

_OKTOBERFEST_HOME        = 'https://tulsaoktoberfest.org/'
_OKTOBERFEST_GUIDE_URL   = 'https://tulsaoktoberfest.org/festival-guide/'
_OKTOBERFEST_SOURCE_URL  = 'https://tulsaoktoberfest.org/festival-guide/'
_OKTOBERFEST_VENUE       = 'River West Festival Park'
_OKTOBERFEST_ADDR        = '2100 S. Jackson Ave., Tulsa, OK 74107'
_OKTOBERFEST_IMAGE       = ''

# Confirmed future dates — update each year when announced.
# Format: { year: (month, start_day, end_day) }
_OKTOBERFEST_KNOWN_DATES = {
    2026: (10, 22, 25),   # Oct 22–25 2026 (confirmed from festival-guide page)
}


def _oktoberfest_dates_from_text(text: str, year: int):
    """Try to parse Oktoberfest dates from page text. Returns (start_dt, end_dt) or (None, None)."""
    import re
    # Look for patterns like "OCT 22-25, 2026" or "October 22-25, 2026"
    pattern = re.compile(
        r'(?:oct(?:ober)?)[^\d]*(\d{1,2})[-–](\d{1,2})[,\s]*(\d{4})',
        re.IGNORECASE
    )
    m = pattern.search(text)
    if m:
        try:
            start_day = int(m.group(1))
            end_day   = int(m.group(2))
            yr        = int(m.group(3))
            start_dt  = datetime(yr, 10, start_day, 17, 0)
            end_dt    = datetime(yr, 10, end_day, 23, 0)
            return start_dt, end_dt
        except Exception:
            pass
    return None, None


async def extract_tulsa_oktoberfest_events(html: str, source_name: str,
                                           url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract the Tulsa Oktoberfest festival event.
    Returns a single multi-day event entry for the full festival.
    Scrapes festival-guide page for dates; falls back to known/projected dates.
    """
    if 'tulsaoktoberfest.org' not in url.lower():
        return [], False

    print(f"[TulsaOktoberfest] Detected Tulsa Oktoberfest URL, building festival event...")

    from bs4 import BeautifulSoup as _BS
    soup = _BS(html, 'html.parser')
    page_text = soup.get_text(separator=' ')

    now = datetime.now()
    target_year = now.year if now.month <= 10 else now.year + 1

    # 1. Try scraping dates from page text
    start_dt, end_dt = _oktoberfest_dates_from_text(page_text, target_year)

    # 2. Fall back to known dates
    if not start_dt or start_dt.year < target_year:
        if target_year in _OKTOBERFEST_KNOWN_DATES:
            month, start_day, end_day = _OKTOBERFEST_KNOWN_DATES[target_year]
            start_dt = datetime(target_year, month, start_day, 17, 0)
            end_dt   = datetime(target_year, month, end_day, 23, 0)
            print(f"[TulsaOktoberfest] Using known {target_year} dates: {start_dt.date()}")
        else:
            # Project: third Thursday of October
            from datetime import date, timedelta
            oct_1 = date(target_year, 10, 1)
            days_to_thursday = (3 - oct_1.weekday()) % 7
            first_thursday = oct_1 + timedelta(days=days_to_thursday)
            third_thursday = first_thursday + timedelta(weeks=2)
            start_dt = datetime(third_thursday.year, third_thursday.month, third_thursday.day, 17, 0)
            end_dt   = datetime(third_thursday.year, third_thursday.month, third_thursday.day + 3, 23, 0)
            print(f"[TulsaOktoberfest] Projecting {target_year} dates: {start_dt.date()}")

    # 3. Future filter
    if future_only and end_dt and end_dt < now:
        print(f"[TulsaOktoberfest] Festival is in the past, skipping")
        return [], True

    year = start_dt.year
    event = {
        'title':           f'Zeeco Tulsa Oktoberfest {year}',
        'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
        'venue':           _OKTOBERFEST_VENUE,
        'venue_address':   _OKTOBERFEST_ADDR,
        'description': (
            f'Zeeco Tulsa Oktoberfest is a four-day outdoor German festival held annually '
            f'at River West Festival Park in Tulsa. Voted the #1 Oktoberfest in the USA, '
            f'this 45+ year tradition features authentic German music, 200+ taps of beer, '
            f'Bavarian food, massive Zelte tents, and views of the Tulsa skyline. '
            f'All ages welcome.'
        ),
        'source_url':      _OKTOBERFEST_SOURCE_URL,
        'image_url':       _OKTOBERFEST_IMAGE,
        'source_name':     source_name or 'Tulsa Oktoberfest',
        'categories':      ['Festival', 'Food', 'Drinks', 'Outdoor', 'Community', 'Music'],
        'outdoor':         True,
        'family_friendly': True,
    }

    print(f"[TulsaOktoberfest] Added: {event['title']} ({start_dt.date()} → {end_dt.date() if end_dt else 'N/A'})")
    return [event], True

# ============================================================================
# ROCKLAHOMA — Annual Rock Music Festival, Pryor OK
# ============================================================================
_ROCKLAHOMA_SOURCE_URL = 'https://www.rocklahoma.com/'
_ROCKLAHOMA_VENUE      = "Rockin' Red Dirt Ranch"
_ROCKLAHOMA_ADDR       = '1421 West 450 Road, Pryor, OK 74361'
_ROCKLAHOMA_IMAGE      = 'https://lirp.cdn-website.com/7db810c9/dms3rep/multi/opt/words+only-1920w.png'

_ROCKLAHOMA_KNOWN_DATES = {
    2026: (9, 4),   # Sept 4-6 2026 (confirmed from lineup poster)
}

_ROCKLAHOMA_HEADLINERS = {
    2026: 'Godsmack, Papa Roach, and Slayer',
}


def _rocklahoma_project_dates(year: int):
    from datetime import date, timedelta
    sept_1 = date(year, 9, 1)
    days_to_friday = (4 - sept_1.weekday()) % 7
    first_friday = sept_1 + timedelta(days=days_to_friday)
    return (
        datetime(first_friday.year, first_friday.month, first_friday.day, 16, 0),
        datetime(first_friday.year, first_friday.month, first_friday.day + 2, 23, 0),
    )


def _rocklahoma_dates_from_jsonld(soup):
    import json as _j
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = _j.loads(script.string or '')
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') == 'MusicEvent' and item.get('startDate'):
                    start = datetime.fromisoformat(item['startDate'])
                    end_raw = item.get('endDate')
                    end = datetime.fromisoformat(end_raw).replace(hour=23, minute=0) if end_raw else None
                    return start, end
        except Exception:
            continue
    return None, None


async def extract_rocklahoma_events(html: str, source_name: str,
                                    url: str = '', future_only: bool = True) -> tuple[list, bool]:
    if 'rocklahoma.com' not in url.lower():
        return [], False

    print(f"[Rocklahoma] Detected Rocklahoma URL, building festival event...")

    from bs4 import BeautifulSoup as _BS
    soup = _BS(html, 'html.parser')

    start_dt, end_dt = _rocklahoma_dates_from_jsonld(soup)

    now = datetime.now()
    if now.month < 9 or (now.month == 9 and now.day <= 6):
        target_year = now.year
    else:
        target_year = now.year + 1

    if not start_dt or start_dt.year < target_year:
        if target_year in _ROCKLAHOMA_KNOWN_DATES:
            month, day = _ROCKLAHOMA_KNOWN_DATES[target_year]
            start_dt = datetime(target_year, month, day, 16, 0)
            end_dt   = datetime(target_year, month, day + 2, 23, 0)
            print(f"[Rocklahoma] Using known {target_year} dates: {start_dt.date()}")
        else:
            start_dt, end_dt = _rocklahoma_project_dates(target_year)
            print(f"[Rocklahoma] Projecting {target_year} dates: {start_dt.date()}")

    if future_only and end_dt and end_dt < now:
        print(f"[Rocklahoma] Festival is in the past, skipping")
        return [], True

    year = start_dt.year
    headliners = _ROCKLAHOMA_HEADLINERS.get(year, '')
    headliner_note = f' Headliners include {headliners}.' if headliners else ''

    event = {
        'title':           f'Rocklahoma {year}',
        'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
        'venue':           _ROCKLAHOMA_VENUE,
        'venue_address':   _ROCKLAHOMA_ADDR,
        'description': (
            f'Rocklahoma is a three-day outdoor rock and metal music festival held annually in Pryor, '
            f'Oklahoma - about 45 minutes from Tulsa.{headliner_note} '
            f'Featuring 50+ bands across multiple stages, plus camping, VIP packages, '
            f'and a Thursday Night Throwdown pre-party.'
        ),
        'source_url':      _ROCKLAHOMA_SOURCE_URL,
        'image_url':       _ROCKLAHOMA_IMAGE,
        'source_name':     source_name or 'Rocklahoma',
        'categories':      ['Music', 'Rock', 'Metal', 'Festival', 'Outdoor', 'Concert'],
        'outdoor':         True,
        'family_friendly': False,
    }

    print(f"[Rocklahoma] Added: {event['title']} ({start_dt.date()} -> {end_dt.date() if end_dt else 'N/A'})")
    return [event], True