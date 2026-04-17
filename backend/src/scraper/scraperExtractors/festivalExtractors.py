"""
Locate918 Scraper - Festival & Recurring Event Extractors
==========================================================
Extractors for festivals, multi-day events, and computed recurring schedules:
  - Rooster Days Festival (Broken Arrow)
  - Tulsa Brunch Fest
  - OKEQ (Oklahomans for Equality)
  - Flywheel Tulsa
  - Arvest Convention Center
  - Tulsa Tough (cycling)
  - Gradient Tulsa (entrepreneurship events)
  - Tulsa Farmers' Market (computed schedule)
  - Oklahoma Renaissance Festival (okcastle.com)
  - Broken Arrow / CivicPlus community calendar
  - Tulsa Zoo
  - Hard Rock Casino Tulsa
  - Gypsy Coffee House (computed recurring)
  - Bad Ass Renee's (GoDaddy calendar API)
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
# ROOSTER DAYS FESTIVAL (Broken Arrow, OK — Wix static site)
# ============================================================================

async def extract_roosterdays_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extractor for Rooster Days festival (roosterdays.com).
    Wix static site — no API. The date range (e.g. "MAY 14-17, 2026") is
    parsed from the page text so this stays accurate year-to-year without
    code changes.

    Returns a single multi-day event. start_time = first day, end_time =
    last day so the FutureFilter keeps it alive for the whole run.
    source_url is always https://www.roosterdays.com/ per project requirement.
    """
    if 'roosterdays.com' not in url.lower():
        return [], False

    print(f"[RoosterDays] Detected Rooster Days — parsing date from page text...")

    # ── Parse date range from page text ──
    # Handles both "MAY 14-17, 2026" and "May 14-17, 2026"
    MONTHS = {
        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
        'MAY': 5, 'JUNE': 6, 'JULY': 7, 'AUGUST': 8,
        'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
    }

    soup = BeautifulSoup(html, 'html.parser')
    page_text = soup.get_text(' ', strip=True)

    start_date = None
    end_date   = None
    year       = None

    # Pattern: "MAY 14-17, 2026"  or  "May 14 - 17, 2026"
    date_pattern = re.compile(
        r'\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|'
        r'SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+'
        r'(\d{1,2})\s*[-–]\s*(\d{1,2}),?\s+(\d{4})\b',
        re.IGNORECASE
    )
    m = date_pattern.search(page_text)
    if m:
        month_str  = m.group(1).upper()
        start_day  = int(m.group(2))
        end_day    = int(m.group(3))
        year       = int(m.group(4))
        month_num  = MONTHS.get(month_str, 5)
        try:
            start_date = datetime(year, month_num, start_day)
            end_date   = datetime(year, month_num, end_day)
            print(f"[RoosterDays] Parsed dates: {start_date.date()} → {end_date.date()}")
        except ValueError as e:
            print(f"[RoosterDays] Date parse error: {e}")

    # Fallback: look for standalone year to at least get something
    if not start_date:
        year_m = re.search(r'\b(202\d)\b', page_text)
        if year_m:
            year = int(year_m.group(1))
            # Default to mid-May if we found a year but no range
            start_date = datetime(year, 5, 1)
            end_date   = None
            print(f"[RoosterDays] Fallback: found year {year}, using May 1 placeholder")
        else:
            print(f"[RoosterDays] Could not parse any date from page")
            return [], True

    # Future filter — keep if end_date (or start_date) >= today
    if future_only:
        cutoff  = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        check_dt = end_date or start_date
        if check_dt < cutoff:
            print(f"[RoosterDays] Event is in the past ({check_dt.date()}), skipping")
            return [], True

    start_str = start_date.strftime('%Y-%m-%d')
    end_str   = end_date.strftime('%Y-%m-%d') if end_date else ''

    # Build description from page text — first clean sentence mentioning the festival
    desc = ''
    desc_m = re.search(
        r'((?:Rooster Days|four-day festival)[^.!?]{20,200}[.!?])',
        page_text, re.IGNORECASE
    )
    if desc_m:
        desc = desc_m.group(1).strip()

    if not desc:
        desc = (
            "Rooster Days is Broken Arrow's annual four-day festival featuring "
            "carnival rides, food trucks, a vendor marketplace, 5K & 1-mile fun run, "
            "a parade, and live entertainment."
        )

    events = [{
        'title':          'Rooster Days Festival',
        'start_time':     start_str,
        'end_time':       end_str,
        'end_date':       end_str,
        'venue':          'Downtown Broken Arrow',
        'venue_address':  'Downtown Broken Arrow, OK',
        'description':    desc[:500],
        'source_url':     'https://www.roosterdays.com/',
        'image_url':      '',
        'source_name':    source_name or 'Rooster Days',
        'categories':     ['Festival', 'Family', 'Outdoor'],
        'outdoor':        True,
        'family_friendly': True,
    }]

    print(f"[RoosterDays] Returning 1 event: {start_str} to {end_str}")
    return events, True


# ============================================================================
# TULSA BRUNCH FEST (tulsabrunchfestival.org — Squarespace static site)
# ============================================================================

async def extract_tulsabrunchfest_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extractor for Tulsa Brunch Fest (tulsabrunchfestival.org).
    Squarespace static site — no API. Date, time, and location are parsed
    from the page text so this stays accurate year-to-year without code changes.

    Parsed fields (as of 2026 site):
      Date:     May 30, 2026
      Time:     7:00am - 3:00pm
      Location: Downtown Cathedral District, Tulsa
    """
    if 'tulsabrunchfestival.org' not in url.lower():
        return [], False

    print(f"[TulsaBrunchFest] Detected Tulsa Brunch Fest — parsing date/time from page text...")

    soup = BeautifulSoup(html, 'html.parser')
    page_text = soup.get_text(' ', strip=True)

    MONTHS = {
        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
        'MAY': 5, 'JUNE': 6, 'JULY': 7, 'AUGUST': 8,
        'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
    }

    start_dt   = None
    end_dt     = None

    # ── 1. Parse single-day date: "May 30, 2026" ──
    single_date_pat = re.compile(
        r'\b(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
        re.IGNORECASE
    )
    dm = single_date_pat.search(page_text)
    if dm:
        month_str = dm.group(1).upper()
        day       = int(dm.group(2))
        year      = int(dm.group(3))
        month_num = MONTHS.get(month_str, 5)
        try:
            start_dt = datetime(year, month_num, day)
            print(f"[TulsaBrunchFest] Parsed date: {start_dt.date()}")
        except ValueError as e:
            print(f"[TulsaBrunchFest] Date parse error: {e}")

    if not start_dt:
        print(f"[TulsaBrunchFest] Could not parse date from page")
        return [], True

    # ── 2. Parse time range: "7:00am - 3:00pm" or "7:00am-3:00pm" ──
    # Look in a window of text around the date match to avoid false positives
    time_pat = re.compile(
        r'(\d{1,2}:\d{2}\s*[aApP][mM])\s*[-–]\s*(\d{1,2}:\d{2}\s*[aApP][mM])',
        re.IGNORECASE
    )
    tm = time_pat.search(page_text)
    if tm:
        try:
            from dateutil import parser as _dp
            start_t = _dp.parse(f"{start_dt.strftime('%Y-%m-%d')} {tm.group(1)}", fuzzy=True)
            end_t   = _dp.parse(f"{start_dt.strftime('%Y-%m-%d')} {tm.group(2)}", fuzzy=True)
            start_dt = start_dt.replace(hour=start_t.hour, minute=start_t.minute)
            end_dt   = end_t
            print(f"[TulsaBrunchFest] Parsed times: {start_t.strftime('%I:%M%p')} – {end_t.strftime('%I:%M%p')}")
        except Exception as e:
            print(f"[TulsaBrunchFest] Time parse error: {e}")
            # Still have date, just no time
            end_dt = None

    # ── 3. Future filter ──
    if future_only:
        cutoff   = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        check_dt = end_dt or start_dt
        if check_dt < cutoff:
            print(f"[TulsaBrunchFest] Event is in the past, skipping")
            return [], True

    start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
    end_str   = end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else ''

    # ── 4. Pull description from page text ──
    desc_m = re.search(
        r'(Tulsa Brunch Fest is[^.]{20,300}\.)',
        page_text, re.IGNORECASE
    )
    desc = desc_m.group(1).strip() if desc_m else (
        "Tulsa Brunch Fest is a one-day outdoor festival celebrating the best brunch "
        "bites, drinks, and vibes in the city. Artful plates from Tulsa's favorite "
        "chefs, craft cocktails, live DJs, and lounge areas."
    )

    events = [{
        'title':          'Tulsa Brunch Fest',
        'start_time':     start_str,
        'end_time':       end_str,
        'venue':          'Downtown Cathedral District',
        'venue_address':  'Downtown Cathedral District, Tulsa, OK',
        'description':    desc[:500],
        'source_url':     'https://www.tulsabrunchfestival.org/',
        'image_url':      '',
        'source_name':    source_name or 'Tulsa Brunch Fest',
        'categories':     ['Festival', 'Food & Drink', 'Outdoor'],
        'outdoor':        True,
        'family_friendly': False,
    }]

    print(f"[TulsaBrunchFest] Returning 1 event: {start_str}")
    return events, True


# ============================================================================
# OKEQ (OKLAHOMANS FOR EQUALITY) — Simple Calendar / Google Calendar
# ============================================================================
# Plugin: Simple Calendar (simcal) WordPress plugin
# Method: Playwright (JS required to render calendar grid)
# DOM: .simcal-event elements, server-rendered monthly grid
# Navigation: click .simcal-next-wrapper → POST admin-ajax.php → DOM reloads
# ============================================================================

_OKEQ_SOURCE_URL = 'https://okeq.org/event-calendar/'
_OKEQ_DEFAULT_VENUE = 'Dennis R. Neill Equality Center'
_OKEQ_DEFAULT_ADDRESS = '621 E 4th St, Tulsa, OK 74120'

# Known OKEQ building rooms → map to full venue + address
_OKEQ_ROOM_MAP = {
    'event center':     (_OKEQ_DEFAULT_VENUE, _OKEQ_DEFAULT_ADDRESS),
    'wellness room':    (_OKEQ_DEFAULT_VENUE, _OKEQ_DEFAULT_ADDRESS),
    'dennis r. neill':  (_OKEQ_DEFAULT_VENUE, _OKEQ_DEFAULT_ADDRESS),
    'equality center':  (_OKEQ_DEFAULT_VENUE, _OKEQ_DEFAULT_ADDRESS),
    '621 e 4th':        (_OKEQ_DEFAULT_VENUE, _OKEQ_DEFAULT_ADDRESS),
    'okeq':             (_OKEQ_DEFAULT_VENUE, _OKEQ_DEFAULT_ADDRESS),
}


def _parse_okeq_events_from_dom(soup: 'BeautifulSoup', source_name: str,
                                future_only: bool, seen_keys: set) -> list:
    """
    Parse .simcal-event elements from a rendered Simple Calendar page.
    Returns a list of normalised event dicts.
    """
    from dateutil import parser as _dp

    events = []
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for el in soup.select('.simcal-event'):
        # ── 1. Skip cancelled events ──
        title_el = el.select_one('.simcal-event-title')
        raw_title = (title_el.get_text(' ', strip=True) if title_el
                     else el.get_text(' ', strip=True).split('\n')[0].strip())
        # simcal repeats the title twice in the DOM; just take first occurrence
        if '\n' in raw_title:
            raw_title = raw_title.split('\n')[0].strip()

        if re.search(r'\(cancelled\)', raw_title, re.I):
            continue
        title = re.sub(r'\(cancelled\)', '', raw_title, flags=re.I).strip()

        # ── 2. Parse date + time from event text ──
        full_text = el.get_text('\n', strip=True)
        # Pattern: "April 1, 2026 | 9:00 am - 4:00 pm"  or  "April 1, 2026 | 9:00 am"
        dt_match = re.search(
            r'([A-Z][a-z]+ \d{1,2},\s*\d{4})\s*\|\s*'
            r'(\d{1,2}:\d{2}\s*[ap]m)'
            r'(?:\s*[-–]\s*(\d{1,2}:\d{2}\s*[ap]m))?',
            full_text, re.I
        )
        if not dt_match:
            # Try date-only fallback: "April 1, 2026"
            date_only = re.search(r'([A-Z][a-z]+ \d{1,2},\s*\d{4})', full_text)
            if not date_only:
                continue
            try:
                start_dt = _dp.parse(date_only.group(1).replace(',', ', '))
            except Exception:
                continue
            end_dt = None
        else:
            date_str, start_time_str, end_time_str = (
                dt_match.group(1).replace(',', ', '),
                dt_match.group(2),
                dt_match.group(3),
            )
            try:
                start_dt = _dp.parse(f"{date_str} {start_time_str}", fuzzy=True)
                end_dt   = (_dp.parse(f"{date_str} {end_time_str}", fuzzy=True)
                            if end_time_str else None)
            except Exception:
                continue

        # ── 3. Future filter ──
        check_dt = end_dt or start_dt
        if future_only and check_dt < cutoff:
            continue

        # ── 4. Deduplicate (title + date) ──
        dedup_key = f"{title.lower()}|{start_dt.date()}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # ── 5. Location ──
        loc_el = el.select_one('.simcal-event-location')
        raw_loc = loc_el.get_text(' ', strip=True) if loc_el else ''

        venue = _OKEQ_DEFAULT_VENUE
        venue_address = _OKEQ_DEFAULT_ADDRESS

        if raw_loc:
            # Check if it's an external venue (has a comma + city/state or zip)
            if re.search(r'\d{5}|,\s*[A-Z]{2}\b', raw_loc):
                # Looks like a real external address
                # Try to extract venue name (first line) vs address
                parts = raw_loc.split(',')
                venue = parts[0].strip() if parts else raw_loc
                venue_address = raw_loc
            else:
                # It's a room name — check our map
                loc_lower = raw_loc.lower()
                matched = False
                for keyword, (v, a) in _OKEQ_ROOM_MAP.items():
                    if keyword in loc_lower:
                        venue = v
                        venue_address = a
                        matched = True
                        break
                if not matched:
                    # Unknown room at OKEQ building — use default venue
                    venue = f"{_OKEQ_DEFAULT_VENUE} – {raw_loc}"
                    venue_address = _OKEQ_DEFAULT_ADDRESS

        # ── 6. Description ──
        desc_el = el.select_one('.simcal-event-description')
        description = (desc_el.get_text(' ', strip=True)[:500]
                       if desc_el else '')

        # ── 7. External link (if any) ──
        link_el = el.select_one('a[href]')
        link_href = link_el['href'] if link_el else ''
        # Only use if it's not a mailto or phone link
        if link_href and re.match(r'https?://', link_href):
            source_url = link_href
        else:
            source_url = _OKEQ_SOURCE_URL

        # ── 8. Categories ──
        categories = ['LGBTQ+', 'Community']
        title_lower = title.lower()
        if any(w in title_lower for w in ['health', 'clinic', 'recovery', 'therapy', 'support']):
            categories.append('Health & Wellness')
        if any(w in title_lower for w in ['film', 'movie', 'theater', 'theatre', 'heller']):
            categories.append('Film & Theater')
        if any(w in title_lower for w in ['bowling', 'sport', 'game', 'bingo']):
            categories.append('Sports & Recreation')
        if any(w in title_lower for w in ['senior', 'elder']):
            categories.append('Seniors')
        if any(w in title_lower for w in ['youth', 'teen', 'kid']):
            categories.append('Youth')
        if any(w in title_lower for w in ['trans', 'gender', 'nonbinary']):
            categories.append('Trans & Gender Diverse')
        if any(w in title_lower for w in ['happy hour', 'social', 'mixer', 'collective']):
            categories.append('Social')

        events.append({
            'title':          title,
            'start_time':     start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':       end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':          venue,
            'venue_address':  venue_address,
            'description':    description,
            'source_url':     source_url,
            'image_url':      '',
            'source_name':    source_name or 'Oklahomans for Equality (OKEQ)',
            'categories':     categories,
            'outdoor':        False,
            'family_friendly': None,
        })

    return events


async def extract_okeq_events(html: str, source_name: str,
                              url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from the OKEQ event calendar (okeq.org/event-calendar/).

    Uses Playwright to render the Simple Calendar (simcal) Google Calendar
    integration. Navigates up to 3 additional months to capture ~4 months
    of upcoming events.
    """
    if 'okeq.org' not in url.lower():
        return [], False

    print(f"[OKEQ] Detected OKEQ URL, using Simple Calendar / Playwright...")
    all_events = []
    seen_keys: set = set()

    try:
        from playwright.async_api import async_playwright
        from bs4 import BeautifulSoup as _BS

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'
            )

            # ── Load the calendar page ──
            await page.goto(_OKEQ_SOURCE_URL, wait_until='networkidle', timeout=45000)
            # Wait for the calendar grid to appear
            try:
                await page.wait_for_selector('.simcal-event', timeout=15000)
            except Exception:
                print('[OKEQ] Timeout waiting for .simcal-event; proceeding with what loaded')

            # ── Scrape up to 4 months (current + 3 more) ──
            for month_idx in range(4):
                html_content = await page.content()
                soup = _BS(html_content, 'html.parser')
                batch = _parse_okeq_events_from_dom(soup, source_name, future_only, seen_keys)
                all_events.extend(batch)
                print(f"[OKEQ] Month {month_idx + 1}: found {len(batch)} new events "
                      f"(total {len(all_events)})")

                # Navigate to next month (skip on last iteration)
                if month_idx < 3:
                    next_btn = page.locator('.simcal-next-wrapper')
                    if await next_btn.count() == 0:
                        print('[OKEQ] No next button found, stopping month navigation')
                        break
                    await next_btn.click()
                    # Wait for AJAX reload
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        await page.wait_for_selector('.simcal-event', timeout=8000)
                    except Exception:
                        await page.wait_for_timeout(2000)  # fallback wait

            await browser.close()

    except Exception as e:
        print(f"[OKEQ] Playwright error: {e}")
        # Fallback: parse whatever HTML was passed in
        from bs4 import BeautifulSoup as _BS
        soup = _BS(html, 'html.parser')
        if soup.select('.simcal-event'):
            all_events = _parse_okeq_events_from_dom(soup, source_name, future_only, set())
        else:
            return [], True  # detected but no events

    print(f"[OKEQ] Total events collected: {len(all_events)}")
    return all_events, True


# ============================================================================
# FLYWHEEL TULSA — Static Avada/Fusion Builder Homepage Events
# ============================================================================
# Site: https://flywheeltulsa.com/
# Method: httpx (static HTML, server-rendered Avada/WordPress)
# Structure: 4 hardcoded event cards in .fusion_builder_column_inner elements
#            inside the row closest to id="events"
# No calendar plugin — events are manually updated on the homepage.
# ============================================================================

_FLYWHEEL_SOURCE_URL = 'https://flywheeltulsa.com/'
_FLYWHEEL_VENUE       = 'Various Venues'
_FLYWHEEL_DEFAULT_ADDR = 'Tulsa, OK'

# Known Flywheel event pages
_FLYWHEEL_EVENT_URLS = {
    'big bite':  'https://flywheeltulsa.com/big-bite/',
    'big ride':  'https://flywheeltulsa.com/big-ride/',
    'big scene': 'https://flywheeltulsa.com/big-scene/',
    'chroma':    'https://flywheeltulsa.com/chroma/',
}


def _parse_flywheel_date(date_str: str) -> tuple[datetime | None, datetime | None]:
    """
    Parse Flywheel date strings into (start_dt, end_dt).

    Handles:
      "April 18, 2026"          → (2026-04-18, None)
      "JUNE 6, 2026"            → (2026-06-06, None)
      "August 20-21, 2026"      → (2026-08-20, 2026-08-21)
      "February 2027"           → (2027-02-01, None)   # month-only
    """
    from dateutil import parser as _dp
    ds = date_str.strip()

    # Multi-day range: "August 20-21, 2026"
    range_m = re.match(
        r'([A-Za-z]+)\s+(\d{1,2})-(\d{1,2}),?\s+(\d{4})', ds, re.I
    )
    if range_m:
        month, d1, d2, year = range_m.groups()
        try:
            start = _dp.parse(f"{month} {d1}, {year}")
            end   = _dp.parse(f"{month} {d2}, {year}")
            return start, end
        except Exception:
            pass

    # Single date: "April 18, 2026" or "JUNE 6, 2026"
    single_m = re.match(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', ds, re.I)
    if single_m:
        try:
            return _dp.parse(ds), None
        except Exception:
            pass

    # Month + year only: "February 2027"
    month_only = re.match(r'([A-Za-z]+)\s+(\d{4})$', ds, re.I)
    if month_only:
        try:
            return _dp.parse(f"{month_only.group(1)} 1 {month_only.group(2)}"), None
        except Exception:
            pass

    return None, None


def _parse_flywheel_card(card_text_lines: list[str], img_src: str,
                         card_links: list[str]) -> dict | None:
    """
    Parse a single Flywheel event card from its text lines.

    Expected structure:
      lines[0] = title (e.g. "BIG BITE")
      lines[1] = date string (e.g. "April 18, 2026")
      lines[2..] = description text + address (mixed)
    """
    if len(card_text_lines) < 2:
        return None

    title    = card_text_lines[0].strip().title()   # normalise ALL-CAPS
    date_str = card_text_lines[1].strip()

    # ── Drop news articles ──
    # Event card titles are short (1-3 words: "Big Bite", "Chroma").
    # News articles are full sentences with 5+ words.
    if len(title.split()) > 4:
        return None
    _NEWS_PREFIXES = ('news ', 'tulsa world', 'features ', 'watch:', 'read:', 'press ')
    if any(title.lower().startswith(p) for p in _NEWS_PREFIXES):
        return None

    start_dt, end_dt = _parse_flywheel_date(date_str)
    if not start_dt:
        return None

    # ── Remaining lines: description + address ──
    rest = ' '.join(card_text_lines[2:]).strip()

    # Address heuristics: last sentence-like chunk with a street number or "Downtown"
    # Try to split on the last line that looks like an address
    address = _FLYWHEEL_DEFAULT_ADDR
    venue    = _FLYWHEEL_VENUE
    description = rest

    # Look for street address pattern: digits + street name
    addr_m = re.search(
        r'(\d+\s+[A-Z][a-zA-Z .]+(?:Ave|Blvd|St|Main|Cheyenne|Boulder|Way|Dr|Rd)[.?]?\s*(?:Tulsa,?\s*OK)?)',
        rest, re.I
    )
    if addr_m:
        address     = addr_m.group(1).strip().rstrip('.')
        if 'Tulsa' not in address:
            address += ', Tulsa, OK'
        description = rest[:addr_m.start()].strip()
    elif 'Downtown' in rest:
        venue       = 'Downtown Tulsa'
        address     = 'Downtown Tulsa, OK'
        description = re.sub(r'Downtown\s*Tulsa,?\s*OK', '', rest, flags=re.I).strip()

    # Venue from description if it mentions a named location
    venue_m = re.search(r'(Flywheel Field|Cains Ballroom|Brady Theater|BOK Center)', description, re.I)
    if venue_m:
        venue = venue_m.group(1)

    # Best source URL: prefer specific event page, else homepage
    title_key = title.lower()
    source_url = _FLYWHEEL_EVENT_URLS.get(title_key, _FLYWHEEL_SOURCE_URL + '#events')
    # Also check card links for a flywheeltulsa.com subpage
    for link in card_links:
        if 'flywheeltulsa.com' in link and link != _FLYWHEEL_SOURCE_URL:
            source_url = link
            break

    # Categories
    categories = ['Festival', 'Community', 'Tulsa']
    t_lower = title.lower()
    if 'food' in description.lower() or 'bite' in t_lower:
        categories.append('Food & Drink')
    if 'ride' in t_lower or 'bike' in description.lower() or 'tough' in description.lower():
        categories.append('Sports & Recreation')
    if 'art' in description.lower() or 'scene' in t_lower:
        categories.append('Arts')
    if 'business' in description.lower() or 'chroma' in t_lower or 'fortune' in description.lower():
        categories.append('Business & Networking')
    if 'outdoor' in description.lower() or 'field' in venue.lower():
        categories.append('Outdoor')

    return {
        'title':          title,
        'start_time':     start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'end_time':       end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
        'venue':          venue,
        'venue_address':  address,
        'description':    description[:500],
        'source_url':     source_url,
        'image_url':      img_src or '',
        'source_name':    'Flywheel Tulsa',
        'categories':     categories,
        'outdoor':        'Outdoor' in categories or 'field' in venue.lower(),
        'family_friendly': None,
    }


async def extract_flywheel_events(html: str, source_name: str,
                                  url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Flywheel Tulsa homepage (flywheeltulsa.com).

    Events are hardcoded in Avada/Fusion Builder nested columns on the
    homepage's #events section. Uses httpx (no Playwright needed).
    """
    if 'flywheeltulsa.com' not in url.lower():
        return [], False

    print(f"[Flywheel] Detected Flywheel Tulsa URL...")

    # ── Fetch homepage if we don't have it ──
    page_html = html
    if not page_html or 'fusion_builder_column_inner' not in page_html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_FLYWHEEL_SOURCE_URL,
                                        headers=HEADERS, timeout=20)
                resp.raise_for_status()
                page_html = resp.text
        except Exception as e:
            print(f"[Flywheel] HTTP error fetching homepage: {e}")
            return [], True  # detected but failed

    soup = BeautifulSoup(page_html, 'html.parser')

    # ── Find events row: nearest .fusion-builder-row-inner to id="events" ──
    events_anchor = soup.find(id='events')
    if not events_anchor:
        # Fallback: look for "Upcoming Events" heading
        events_anchor = soup.find(lambda tag: tag.name in ('h1','h2','h3','h4') and
                                              'upcoming events' in tag.get_text().lower())

    if not events_anchor:
        print('[Flywheel] Could not find #events section')
        return [], True

    # Walk up to find the container that holds the event cards row
    events_row = None
    node = events_anchor
    for _ in range(10):
        node = node.parent
        if not node:
            break
        # Look for a sibling .fusion-builder-row-inner with ≥3 inner columns
        for row in node.find_all('div', class_='fusion-builder-row-inner'):
            cols = row.find_all('div', class_='fusion_builder_column_inner')
            if len(cols) >= 3:
                # Make sure it has event-like content (date pattern)
                row_text = row.get_text()
                if re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b', row_text, re.I):
                    events_row = row
                    break
        if events_row:
            break

    if not events_row:
        print('[Flywheel] Could not locate events card row')
        return [], True

    # ── Parse each card ──
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []

    for card in events_row.find_all('div', class_='fusion_builder_column_inner'):
        img_tag  = card.find('img')
        img_src  = img_tag['src'] if img_tag and img_tag.get('src') else ''

        # Event cards always have a logo image; skip image-less cards (news articles)
        if not img_src:
            continue

        links    = [a['href'] for a in card.find_all('a', href=True)
                    if a['href'].startswith('http')]
        raw_text = card.get_text('\n').strip()
        lines    = [l.strip() for l in raw_text.split('\n') if l.strip()]

        event = _parse_flywheel_card(lines, img_src, links)
        if not event:
            continue

        # Future filter
        if future_only:
            try:
                from dateutil import parser as _dp
                check_dt = _dp.parse(event['end_time'] or event['start_time'])
                if check_dt < cutoff:
                    print(f"[Flywheel] Skipping past event: {event['title']}")
                    continue
            except Exception:
                pass

        events.append(event)
        print(f"[Flywheel] Added: {event['title']} on {event['start_time'][:10]}")

    print(f"[Flywheel] Total events: {len(events)}")
    return events, True

# ============================================================================
# ARVEST CONVENTION CENTER — Custom CMS with AJAX Pagination
# ============================================================================
# Site: https://www.arvestconventioncenter.com/events
# Method: httpx (no Playwright needed)
# Structure: AJAX endpoint /events/events_ajax/{offset} returns raw HTML
#            chunks of .eventItem cards. Paginate by 6 until empty.
#            Each card has date, title, venue, image, and a detail URL.
#            Detail pages provide start time and description.
# ============================================================================

_ARVEST_SOURCE_URL   = 'https://www.arvestconventioncenter.com/events'
_ARVEST_BASE_URL     = 'https://www.arvestconventioncenter.com'
_ARVEST_AJAX_URL     = 'https://www.arvestconventioncenter.com/events/events_ajax/{offset}'
_ARVEST_AJAX_PARAMS  = 'category=0&venue=0&team=0&exclude=&per_page=6&came_from_page=event-list-page'
_ARVEST_VENUE_ADDR   = '100 Civic Center, Tulsa, OK 74103'


def _parse_arvest_date(item_soup) -> tuple[datetime | None, datetime | None]:
    """
    Parse the date block from an .eventItem BeautifulSoup tag.

    Single day:  <span class="m-date__singleDate">March <26>, 2026</span>
    Multi-day:   <span class="m-date__rangeFirst">March <27></span> -
                 <span class="m-date__rangeLast"><29>, 2026</span>
    Returns (start_dt, end_dt) — end_dt is None for single-day events.
    """
    from dateutil import parser as _dp

    date_div = item_soup.select_one('div.date')
    if not date_div:
        return None, None

    # ── Single day ──
    single = date_div.select_one('.m-date__singleDate')
    if single:
        month = (single.select_one('.m-date__month') or BeautifulSoup('', 'html.parser')).get_text(strip=True)
        day   = (single.select_one('.m-date__day')   or BeautifulSoup('', 'html.parser')).get_text(strip=True)
        year  = (single.select_one('.m-date__year')  or BeautifulSoup('', 'html.parser')).get_text(strip=True).replace(',', '').strip()
        try:
            return _dp.parse(f"{month} {day} {year}"), None
        except Exception:
            return None, None

    # ── Multi-day range ──
    first = date_div.select_one('.m-date__rangeFirst')
    last  = date_div.select_one('.m-date__rangeLast')
    if first and last:
        start_month = (first.select_one('.m-date__month') or BeautifulSoup('', 'html.parser')).get_text(strip=True)
        start_day   = (first.select_one('.m-date__day')   or BeautifulSoup('', 'html.parser')).get_text(strip=True)
        end_day     = (last.select_one('.m-date__day')    or BeautifulSoup('', 'html.parser')).get_text(strip=True)
        end_year    = (last.select_one('.m-date__year')   or BeautifulSoup('', 'html.parser')).get_text(strip=True).replace(',', '').strip()
        # The month carries over from first to last
        try:
            start_dt = _dp.parse(f"{start_month} {start_day} {end_year}")
            end_dt   = _dp.parse(f"{start_month} {end_day} {end_year}")
            return start_dt, end_dt
        except Exception:
            return None, None

    return None, None


async def _fetch_arvest_detail(client: httpx.AsyncClient, detail_url: str) -> tuple[str, str]:
    """
    Fetch a single Arvest event detail page and return (time_str, description).
    time_str is like "1:00 PM"; description is plain text (up to 500 chars).
    Returns ('', '') on failure.
    """
    try:
        resp = await client.get(detail_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        detail_soup = BeautifulSoup(resp.text, 'html.parser')

        # ── Time ──
        time_el = detail_soup.select_one('span.time.cell')
        time_str = time_el.get_text(strip=True) if time_el else ''

        # ── Description ──
        desc_el = detail_soup.select_one('.description_inner')
        description = desc_el.get_text(separator=' ', strip=True)[:500] if desc_el else ''

        return time_str, description
    except Exception as e:
        print(f"[Arvest] Detail fetch failed for {detail_url}: {e}")
        return '', ''


def _arvest_categories(title: str) -> list[str]:
    """
    Infer categories from event title for Arvest Convention Center events.
    Defaults to ['Entertainment', 'Community'].
    """
    t = title.lower()
    cats = []

    if any(w in t for w in ['concert', 'music', 'band', 'jazz', 'blues', 'symphony', 'orchestra', 'guitarist']):
        cats = ['Music', 'Entertainment']
    elif any(w in t for w in ['gala', 'ball', 'banquet', 'dinner', 'luncheon', 'awards']):
        cats = ['Social', 'Community']
    elif any(w in t for w in ['dance', 'ballet', 'cheer', 'showstopper', 'starpower', 'stage one']):
        cats = ['Entertainment', 'Competition']
    elif any(w in t for w in ['wrestling', 'wrestling', 'sport', 'basketball', 'football', 'soccer', 'volleyball', 'gymnastics', 'roller derby']):
        cats = ['Sports', 'Competition']
    elif any(w in t for w in ['conference', 'convention', 'summit', 'symposium', 'seminar', 'expo', 'trade show', 'ffa', 'fccla', 'shrm', 'skills']):
        cats = ['Conference', 'Education']
    elif any(w in t for w in ['gaming', 'con', 'comicon', 'anime']):
        cats = ['Entertainment', 'Gaming']
    elif any(w in t for w in ['graduation', 'ceremony', 'graduation']):
        cats = ['Community']
    elif any(w in t for w in ['bridal', 'wedding', 'baby shower']):
        cats = ['Social']
    elif any(w in t for w in ['comedy', 'stand-up', 'improv']):
        cats = ['Comedy', 'Entertainment']

    if not cats:
        cats = ['Entertainment', 'Community']

    return cats


async def extract_arvest_events(html: str, source_name: str,
                                url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Arvest Convention Center (arvestconventioncenter.com).

    Uses httpx to paginate through the AJAX endpoint:
      GET /events/events_ajax/{offset}?category=0&venue=0&team=0&...
    Each response is a raw JSON-encoded HTML string of .eventItem cards.
    Loops with offset 0, 6, 12... until the response is empty.

    Fetches detail pages concurrently to obtain start times and descriptions.
    """
    if 'arvestconventioncenter.com' not in url.lower():
        return [], False

    print(f"[Arvest] Detected Arvest Convention Center URL, using AJAX pagination...")
    events = []
    now = datetime.now()
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 1. Collect all event cards via AJAX pagination ──
    raw_cards: list[dict] = []   # {title, detail_url, image_url, venue, start_dt, end_dt}

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        offset = 0
        while True:
            ajax_url = f"{_ARVEST_AJAX_URL.format(offset=offset)}?{_ARVEST_AJAX_PARAMS}"
            try:
                resp = await client.get(ajax_url, headers=HEADERS)
                resp.raise_for_status()
                # Response is a JSON-encoded HTML string, e.g. "\"<div class=...\"
                raw = resp.text.strip()
                # Strip surrounding JSON quotes if present
                if raw.startswith('"') and raw.endswith('"'):
                    raw = raw[1:-1]
                # Unescape JSON string escapes
                try:
                    raw = json.loads(f'"{raw}"')
                except Exception:
                    pass  # already decoded or not escaped
            except Exception as e:
                print(f"[Arvest] AJAX fetch failed at offset {offset}: {e}")
                break

            if not raw or len(raw) < 10:
                print(f"[Arvest] No more events at offset {offset}, stopping pagination.")
                break

            # ── Parse .eventItem cards from this chunk ──
            chunk_soup = BeautifulSoup(raw, 'html.parser')
            item_tags = chunk_soup.select('.eventItem')
            if not item_tags:
                print(f"[Arvest] No .eventItem found at offset {offset}, stopping.")
                break

            print(f"[Arvest] offset={offset}: found {len(item_tags)} cards")

            for item in item_tags:
                # Title + detail URL
                title_a = item.select_one('h3.title a')
                if not title_a:
                    continue
                title      = title_a.get_text(strip=True)
                detail_url = title_a.get('href', '').strip()
                if detail_url and not detail_url.startswith('http'):
                    detail_url = _ARVEST_BASE_URL + detail_url

                # Image
                img_el    = item.select_one('.thumb img')
                image_url = img_el['src'] if img_el and img_el.get('src') else ''
                if image_url and not image_url.startswith('http'):
                    image_url = _ARVEST_BASE_URL + image_url

                # Venue / hall
                tagline_el = item.select_one('h4.tagline, .tagline')
                venue_hall = tagline_el.get_text(strip=True) if tagline_el else 'Arvest Convention Center'
                if venue_hall:
                    venue_full = f"Arvest Convention Center – {venue_hall}"
                else:
                    venue_full = 'Arvest Convention Center'

                # Date
                start_dt, end_dt = _parse_arvest_date(item)
                if not start_dt:
                    print(f"[Arvest] Could not parse date for: {title}")
                    continue

                # Future filter (list-level, before detail fetch)
                if future_only:
                    check_dt = end_dt or start_dt
                    if check_dt < cutoff:
                        print(f"[Arvest] Skipping past event: {title}")
                        continue

                raw_cards.append({
                    'title':      title,
                    'detail_url': detail_url,
                    'image_url':  image_url,
                    'venue':      venue_full,
                    'start_dt':   start_dt,
                    'end_dt':     end_dt,
                })

            offset += 6

        # ── 2. Fetch detail pages concurrently for time + description ──
        if raw_cards:
            print(f"[Arvest] Fetching {len(raw_cards)} detail pages concurrently...")
            detail_tasks = [
                _fetch_arvest_detail(client, card['detail_url'])
                for card in raw_cards
            ]
            detail_results = await asyncio.gather(*detail_tasks)
        else:
            detail_results = []

    # ── 3. Build event objects ──
    for card, (time_str, description) in zip(raw_cards, detail_results):
        start_dt = card['start_dt']
        end_dt   = card['end_dt']

        # Apply time if available
        if time_str:
            try:
                from dateutil import parser as _dp
                t = _dp.parse(time_str)
                start_dt = start_dt.replace(hour=t.hour, minute=t.minute, second=0)
            except Exception:
                pass

        events.append({
            'title':           card['title'],
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           card['venue'],
            'venue_address':   _ARVEST_VENUE_ADDR,
            'description':     description,
            'source_url':      card['detail_url'] or _ARVEST_SOURCE_URL,
            'image_url':       card['image_url'],
            'source_name':     source_name or 'Arvest Convention Center',
            'categories':      _arvest_categories(card['title']),
            'outdoor':         False,
            'family_friendly': None,
        })
        print(f"[Arvest] Added: {card['title']} on {start_dt.strftime('%Y-%m-%d')} @ {time_str or 'TBD'}")

    print(f"[Arvest] Total events: {len(events)}")
    return events, True


# ============================================================================
# TULSA TOUGH — Annual Multi-Day Cycling Event (Static Squarespace Site)
# ============================================================================
# Site: https://www.tulsatough.com/
# Method: httpx (static site, no Playwright needed)
# Structure: Single annual 3-day event (Fri–Sun, first weekend of June).
#            Dates are scraped from /fondo-ride-schedule to stay current
#            each year rather than being hardcoded.
#            Falls back to the homepage if the schedule page changes.
# Event: Saint Francis Tulsa Tough — criterium races + gran fondo rides
#        across multiple Tulsa venues (Blue Dome, Arts District, Riverside)
# ============================================================================

_TULSATOUGH_HOME_URL     = 'https://www.tulsatough.com/'
_TULSATOUGH_SCHEDULE_URL = 'https://www.tulsatough.com/fondo-ride-schedule'
_TULSATOUGH_SOURCE_URL   = 'https://www.tulsatough.com/weekend-schedule'

# Day-of-week → offset from Friday (start day)
_TULSATOUGH_DAY_OFFSET = {'friday': 0, 'saturday': 1, 'sunday': 2}


def _parse_tulsatough_dates(page_text: str) -> tuple[datetime | None, datetime | None]:
    """
    Scrape start/end dates from Tulsa Tough schedule page text.

    Looks for patterns like:
      "Friday, June 5, 2026"
      "Saturday, June 6, 2026"
      "Sunday, June 7, 2026"

    Returns (start_dt, end_dt) where start = Friday, end = Sunday.
    Falls back to: find any "June X, YYYY" and compute the full weekend.
    """
    from dateutil import parser as _dp

    found: dict[str, datetime] = {}

    # Primary: named weekday + full date
    pattern = re.compile(
        r'\b(Friday|Saturday|Sunday),\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2}),\s+(\d{4})',
        re.I
    )
    for m in pattern.finditer(page_text):
        day_name = m.group(1).lower()
        date_str = f"{m.group(2)} {m.group(3)}, {m.group(4)}"
        try:
            dt = _dp.parse(date_str)
            found[day_name] = dt
        except Exception:
            pass

    if 'friday' in found and 'sunday' in found:
        return found['friday'], found['sunday']
    if 'friday' in found and 'saturday' in found:
        # Compute Sunday from Saturday + 1
        return found['friday'], found['saturday'] + timedelta(days=1)
    if 'friday' in found:
        # Only Friday found — derive full weekend
        fri = found['friday']
        return fri, fri + timedelta(days=2)

    # Fallback: any "Month D, YYYY" — assume it's start of the weekend
    fallback = re.search(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2}),\s+(\d{4})',
        page_text, re.I
    )
    if fallback:
        try:
            start = _dp.parse(f"{fallback.group(1)} {fallback.group(2)}, {fallback.group(3)}")
            return start, start + timedelta(days=2)
        except Exception:
            pass

    return None, None


async def extract_tulsatough_events(html: str, source_name: str,
                                    url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract the Saint Francis Tulsa Tough event from tulsatough.com.

    This is a single annual 3-day cycling event (criterium races + gran fondo
    rides) held the first weekend of June in Tulsa. Because the site is a
    static Squarespace build with no events calendar, we:
      1. Fetch /fondo-ride-schedule to scrape the current year's dates
      2. Return one event spanning Friday–Sunday
    """
    if 'tulsatough.com' not in url.lower():
        return [], False

    print(f"[TulsaTough] Detected Tulsa Tough URL, scraping annual event...")

    # ── Fetch schedule page for dates ──
    page_text = ''
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for fetch_url in [_TULSATOUGH_SCHEDULE_URL, _TULSATOUGH_HOME_URL]:
            try:
                resp = await client.get(fetch_url, headers=HEADERS)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                page_text = soup.get_text(separator='\n')
                if re.search(r'\b(Friday|Saturday|Sunday),\s+\w+\s+\d', page_text, re.I):
                    print(f"[TulsaTough] Got dates from {fetch_url}")
                    break
            except Exception as e:
                print(f"[TulsaTough] Fetch failed for {fetch_url}: {e}")

    start_dt, end_dt = _parse_tulsatough_dates(page_text)

    if not start_dt:
        print(f"[TulsaTough] Could not parse event dates — returning no events")
        return [], True  # detected but couldn't parse

    print(f"[TulsaTough] Dates: {start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d') if end_dt else 'N/A'}")

    # ── Future filter ──
    if future_only:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        check_dt = end_dt or start_dt
        if check_dt < cutoff:
            print(f"[TulsaTough] Event is in the past, skipping")
            return [], True

    year = start_dt.year
    event = {
        'title':          f'Saint Francis Tulsa Tough {year}',
        'start_time':     start_dt.replace(hour=17, minute=0, second=0).strftime('%Y-%m-%dT%H:%M:%S'),
        'end_time':       end_dt.replace(hour=18, minute=0, second=0).strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
        'venue':          'Blue Dome District & Riverside',
        'venue_address':  'Blue Dome District, Tulsa, OK 74103',
        'description':    (
            f'Saint Francis Tulsa Tough is a three-day cycling festival in Tulsa featuring '
            f'professional criterium races across three unique downtown courses and gran fondo '
            f'rides for all levels. Live music, vendors, and festivities throughout the weekend. '
            f'Races run Friday evening through Sunday. Free to spectate.'
        ),
        'source_url':     _TULSATOUGH_SOURCE_URL,
        'image_url':      '',
        'source_name':    source_name or 'Tulsa Tough',
        'categories':     ['Sports', 'Cycling', 'Outdoor', 'Community', 'Festival'],
        'outdoor':        True,
        'family_friendly': True,
    }

    print(f"[TulsaTough] Added: {event['title']}")
    return [event], True


# ============================================================================
# GRADIENT TULSA — Webflow CMS Dynamic List
# ============================================================================
# Site: https://www.joingradient.com/events
# Method: httpx (static Webflow page, CMS items server-rendered)
# Structure: .w-dyn-item cards each containing:
#   .events-list-date     → "Mar 24, 2026"
#   .h2-event             → event title
#   .event-card-pillar    → pillar tag (Connect, Start, Scale, etc.)
#   .link-event[href]     → detail URL (events.joingradient.com/...)
#   .event-image-thumb    → background-image inline style with CDN URL
# No time in list view; detail pages are on a separate domain.
# Venue: always Gradient, 12 N Cheyenne Ave, Tulsa OK 74103
# ============================================================================

_GRADIENT_SOURCE_URL = 'https://www.joingradient.com/events'
_GRADIENT_VENUE      = 'Gradient'
_GRADIENT_ADDR       = '12 N Cheyenne Ave, Tulsa, OK 74103'

# Pillar → categories mapping
_GRADIENT_PILLAR_CATS = {
    'connect': ['Networking', 'Entrepreneurship', 'Community'],
    'start':   ['Entrepreneurship', 'Startup', 'Education'],
    'scale':   ['Entrepreneurship', 'Business', 'Education'],
    'learn':   ['Education', 'Workshop', 'Entrepreneurship'],
}


def _gradient_categories(pillar: str, title: str) -> list[str]:
    """Map Gradient pillar + title keywords to categories."""
    base = _GRADIENT_PILLAR_CATS.get(pillar.lower().strip(), ['Entrepreneurship', 'Community'])
    t = title.lower()
    cats = list(base)
    if any(w in t for w in ['women', "women's"]):
        cats.append("Women's")
    if any(w in t for w in ['tech', 'software', 'ai', 'startup', 'saas', 'product']):
        if 'Tech' not in cats:
            cats.append('Tech')
    if any(w in t for w in ['pitch', 'investor', 'venture', 'vc', 'capital']):
        if 'Startup' not in cats:
            cats.append('Startup')
    return cats


async def extract_gradient_events(html: str, source_name: str,
                                  url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Gradient Tulsa (joingradient.com/events).

    Gradient is a Webflow site — events are rendered as .w-dyn-item elements
    in a dynamic list. Fetches the /events page with httpx and parses the DOM.
    Images are CSS background-image inline styles on .event-image-thumb.
    No time data in list view; defaults to 09:00.
    """
    if 'joingradient.com' not in url.lower():
        return [], False

    print(f"[Gradient] Detected Gradient Tulsa URL, using Webflow CMS parser...")

    # ── Fetch the events page ──
    page_html = html
    if not page_html or 'w-dyn-item' not in page_html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_GRADIENT_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                page_html = resp.text
        except Exception as e:
            print(f"[Gradient] Fetch error: {e}")
            return [], True

    soup = BeautifulSoup(page_html, 'html.parser')
    items = soup.select('.w-dyn-item')
    if not items:
        print(f"[Gradient] No .w-dyn-item elements found")
        return [], True

    print(f"[Gradient] Found {len(items)} CMS items")

    events = []
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for item in items:
        # ── Date ──
        date_el = item.select_one('.events-list-date')
        if not date_el:
            continue
        date_str = date_el.get_text(strip=True)  # "Mar 24, 2026"
        try:
            from dateutil import parser as _dp
            start_dt = _dp.parse(date_str)
        except Exception:
            print(f"[Gradient] Could not parse date: {date_str!r}")
            continue

        # Future filter
        if future_only and start_dt < cutoff:
            continue

        # ── Title ──
        title_el = item.select_one('.h2-event')
        title = title_el.get_text(strip=True) if title_el else ''
        if not title:
            continue

        # ── Pillar / tag ──
        pillar_el = item.select_one('.event-card-pillar')
        pillar = pillar_el.get_text(strip=True) if pillar_el else ''

        # ── Detail URL ──
        link_el = item.select_one('.link-event')
        detail_url = link_el.get('href', '').strip() if link_el else _GRADIENT_SOURCE_URL

        # ── Image — CSS background-image inline style ──
        thumb_el = item.select_one('.event-image-thumb')
        image_url = ''
        if thumb_el:
            style = thumb_el.get('style', '')
            bg_match = re.search(r'background-image:\s*url\(["\']?(https?://[^"\')\s]+)["\']?\)', style)
            if bg_match:
                image_url = bg_match.group(1)

        # ── Build event ──
        start_with_time = start_dt.replace(hour=9, minute=0, second=0)
        events.append({
            'title':           title,
            'start_time':      start_with_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        '',
            'venue':           _GRADIENT_VENUE,
            'venue_address':   _GRADIENT_ADDR,
            'description':     f'Gradient {pillar} event.' if pillar else '',
            'source_url':      detail_url or _GRADIENT_SOURCE_URL,
            'image_url':       image_url,
            'source_name':     source_name or 'Gradient Tulsa',
            'categories':      _gradient_categories(pillar, title),
            'outdoor':         False,
            'family_friendly': None,
        })
        print(f"[Gradient] Added: {title} on {start_dt.strftime('%Y-%m-%d')} [{pillar}]")

    print(f"[Gradient] Total events: {len(events)}")
    return events, True


# ============================================================================
# TULSA FARMERS' MARKET — Year-Round Recurring Market (Computed Schedule)
# ============================================================================
# Site: https://www.tulsafarmersmarket.org/visit
# Method: Computed — no scraping needed. Schedule is stable year-to-year.
#         Generates rolling 4-week window of upcoming market days.
# Schedule:
#   Saturdays Apr–Sep  → 7:00 AM – 11:00 AM
#   Saturdays Oct–Mar  → 8:00 AM – 12:00 PM
#   Wednesdays May–Aug → 8:00 AM – 11:00 AM  (in-person market)
#   Closed: Saturday immediately following Thanksgiving & Christmas
# Location: Whittier Square, 1 S Lewis Ave, Tulsa, OK 74104
# ============================================================================

_TFM_SOURCE_URL = 'https://www.tulsafarmersmarket.org/visit'
_TFM_VENUE      = "Tulsa Farmers' Market"
_TFM_ADDR       = '1 S Lewis Ave, Tulsa, OK 74104'
_TFM_DESC       = (
    "Oklahoma's premier farmers' market at Whittier Square in Tulsa's Kendall Whittier "
    "neighborhood. Over 100 local farmers, ranchers, chefs, and artisans offering fresh "
    "produce, meats, eggs, honey, baked goods, plants, and handcrafted goods. "
    "Free admission, year-round. SNAP/EBT accepted."
)
# Lookahead window in days
_TFM_LOOKAHEAD_DAYS = 28


def _tfm_skip_saturday(dt: datetime) -> bool:
    """
    Returns True if this Saturday should be skipped (post-Thanksgiving or post-Christmas).
    Rules: closed on the Saturday immediately following Thanksgiving and Christmas Day.
    """
    if dt.weekday() != 5:  # not a Saturday
        return False

    year = dt.year

    # Thanksgiving: 4th Thursday of November
    # Find first Thursday of November, then add 3 weeks
    nov1 = datetime(year, 11, 1)
    days_to_thu = (3 - nov1.weekday()) % 7  # Thursday = weekday 3
    first_thu = nov1 + timedelta(days=days_to_thu)
    thanksgiving = first_thu + timedelta(weeks=3)
    # Saturday after Thanksgiving
    days_to_sat = (5 - thanksgiving.weekday()) % 7
    if days_to_sat == 0:
        days_to_sat = 7
    post_thanksgiving_sat = thanksgiving + timedelta(days=days_to_sat)

    if dt.date() == post_thanksgiving_sat.date():
        return True

    # Christmas: Dec 25 — Saturday immediately following
    christmas = datetime(year, 12, 25)
    days_to_sat = (5 - christmas.weekday()) % 7
    if days_to_sat == 0:
        days_to_sat = 7
    post_christmas_sat = christmas + timedelta(days=days_to_sat)

    if dt.date() == post_christmas_sat.date():
        return True

    return False


def _tfm_saturday_hours(dt: datetime) -> tuple[int, int, int, int]:
    """Return (start_hour, start_min, end_hour, end_min) for a Saturday market."""
    month = dt.month
    # Apr–Sep: 7am–11am
    if 4 <= month <= 9:
        return 7, 0, 11, 0
    # Oct–Mar: 8am–12pm
    return 8, 0, 12, 0


def _tfm_generate_market_days(lookahead_days: int = _TFM_LOOKAHEAD_DAYS) -> list[dict]:
    """
    Generate upcoming TFM market days from today through lookahead_days.
    Returns a list of event dicts ready for the events pipeline.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today + timedelta(days=lookahead_days)

    events = []
    current = today

    while current <= end_date:
        month = current.month
        weekday = current.weekday()  # 0=Mon, 5=Sat, 2=Wed

        # ── Saturday market ──
        if weekday == 5 and not _tfm_skip_saturday(current):
            sh, sm, eh, em = _tfm_saturday_hours(current)
            start_dt = current.replace(hour=sh, minute=sm, second=0)
            end_dt   = current.replace(hour=eh, minute=em, second=0)

            season = 'Spring/Summer' if 4 <= month <= 9 else 'Fall/Winter'
            events.append({
                'title':           f"Tulsa Farmers' Market — Saturday",
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'venue':           _TFM_VENUE,
                'venue_address':   _TFM_ADDR,
                'description':     _TFM_DESC,
                'source_url':      _TFM_SOURCE_URL,
                'image_url':       '',
                'source_name':     "Tulsa Farmers' Market",
                'categories':      ['Farmers Market', 'Food & Drink', 'Community', 'Outdoor'],
                'outdoor':         True,
                'family_friendly': True,
            })

        # ── Wednesday market (May–Aug only) ──
        elif weekday == 2 and 5 <= month <= 8:
            start_dt = current.replace(hour=8, minute=0, second=0)
            end_dt   = current.replace(hour=11, minute=0, second=0)

            events.append({
                'title':           f"Tulsa Farmers' Market — Wednesday",
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'venue':           _TFM_VENUE,
                'venue_address':   _TFM_ADDR,
                'description':     _TFM_DESC,
                'source_url':      _TFM_SOURCE_URL,
                'image_url':       '',
                'source_name':     "Tulsa Farmers' Market",
                'categories':      ['Farmers Market', 'Food & Drink', 'Community', 'Outdoor'],
                'outdoor':         True,
                'family_friendly': True,
            })

        current += timedelta(days=1)

    return events


async def extract_tulsafarmersmarket_events(html: str, source_name: str,
                                            url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Generate upcoming Tulsa Farmers' Market events from a computed schedule.

    The TFM has a stable year-round schedule that rarely changes:
      - Saturdays, Apr–Sep: 7–11am
      - Saturdays, Oct–Mar: 8am–12pm
      - Wednesdays, May–Aug: 8–11am
      - Closed the Saturday after Thanksgiving and Christmas

    Instead of scraping individual event pages (there are none), this extractor
    computes the next 4 weeks of market days and returns them as individual events.
    Re-running always returns a fresh, rolling window of upcoming dates.
    """
    if 'tulsafarmersmarket.org' not in url.lower():
        return [], False

    print(f"[TFM] Detected Tulsa Farmers' Market URL, generating schedule...")

    events = _tfm_generate_market_days(_TFM_LOOKAHEAD_DAYS)

    print(f"[TFM] Generated {len(events)} upcoming market days")
    for ev in events:
        print(f"[TFM]   {ev['start_time'][:10]} ({ev['title'].split('—')[-1].strip()})")

    return events, True


# ============================================================================
# OKLAHOMA RENAISSANCE FESTIVAL — Annual Multi-Weekend Event (okcastle.com)
# ============================================================================
# Site: https://okcastle.com/
# Method: httpx — scrapes date range from homepage, generates individual days
# Schedule: Saturdays, Sundays & Memorial Day, late April through end of May
#   2026: April 25 – May 31, 10:30 AM – 6:00 PM
# Location: The Castle of Muskogee, 3400 Fern Mountain Rd, Muskogee, OK 74401
# Strategy: Parse start/end dates from homepage text, then yield each
#   Saturday, Sunday, and Memorial Day (last Monday of May) in that window.
# ============================================================================

_OKRF_SOURCE_URL = 'https://okcastle.com/'
_OKRF_VENUE      = 'The Castle of Muskogee'
_OKRF_ADDR       = '3400 Fern Mountain Rd, Muskogee, OK 74401'
_OKRF_DESC       = (
    "The Oklahoma Renaissance Festival at The Castle of Muskogee is one of the largest "
    "Renaissance festivals in the Southwest. Six themed weekends of jousting, live performances, "
    "artisan vendors, food, costumed characters, and family activities. Open Saturdays, Sundays, "
    "and Memorial Day. Costumes welcome and encouraged."
)


def _okrf_parse_dates(page_text: str) -> tuple[datetime | None, datetime | None]:
    """
    Scrape the festival's start and end dates from the homepage text.

    Looks for patterns like:
      "APRIL 25 - MAY 31, 2026"
      "April 25 – May 31, 2026"
      "April 25 to May 31, 2026"
    Returns (start_dt, end_dt).
    """
    from dateutil import parser as _dp

    # Pattern: "Month D - Month D, YYYY" (same or different months)
    m = re.search(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2})\s*[-–—to]+\s*'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2}),?\s+(\d{4})',
        page_text, re.I
    )
    if m:
        try:
            start = _dp.parse(f"{m.group(1)} {m.group(2)}, {m.group(5)}")
            end   = _dp.parse(f"{m.group(3)} {m.group(4)}, {m.group(5)}")
            return start, end
        except Exception:
            pass

    # Pattern: same month "April 25 - 31, 2026"
    m2 = re.search(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),?\s+(\d{4})',
        page_text, re.I
    )
    if m2:
        try:
            start = _dp.parse(f"{m2.group(1)} {m2.group(2)}, {m2.group(4)}")
            end   = _dp.parse(f"{m2.group(1)} {m2.group(3)}, {m2.group(4)}")
            return start, end
        except Exception:
            pass

    return None, None


def _okrf_memorial_day(year: int) -> datetime:
    """Return Memorial Day (last Monday of May) for a given year."""
    # Last Monday of May = May 31 or earlier
    may31 = datetime(year, 5, 31)
    # weekday(): Monday=0 ... Sunday=6
    days_back = (may31.weekday() - 0) % 7  # days back to last Monday
    return may31 - timedelta(days=days_back)


def _okrf_generate_days(start_dt: datetime, end_dt: datetime) -> list[datetime]:
    """
    Generate all festival days between start and end (inclusive):
    Saturdays (weekday 5), Sundays (weekday 6), and Memorial Day (last Mon of May).
    """
    memorial_day = _okrf_memorial_day(start_dt.year)
    days = []
    current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end:
        wd = current.weekday()
        if wd in (5, 6):  # Saturday or Sunday
            days.append(current)
        elif current.date() == memorial_day.date():  # Memorial Day Monday
            days.append(current)
        current += timedelta(days=1)

    return days


async def extract_okcastle_events(html: str, source_name: str,
                                  url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract Oklahoma Renaissance Festival events from okcastle.com.

    Scrapes the homepage to parse the current year's date range
    (e.g. "April 25 – May 31, 2026"), then generates one event per
    festival day (Saturdays, Sundays, and Memorial Day).

    Returns individual day events so each weekend shows up distinctly
    in the events feed throughout the festival season.
    """
    if 'okcastle.com' not in url.lower():
        return [], False

    print(f"[OKCastle] Detected Oklahoma Renaissance Festival URL...")

    # ── Fetch homepage for current year dates ──
    page_text = ''
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            resp = await client.get(_OKRF_SOURCE_URL, headers=HEADERS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            page_text = soup.get_text(separator=' ')
        except Exception as e:
            print(f"[OKCastle] Fetch error: {e}")
            # Fall through — try parsing whatever html was passed in
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                page_text = soup.get_text(separator=' ')

    start_dt, end_dt = _okrf_parse_dates(page_text)

    if not start_dt or not end_dt:
        print(f"[OKCastle] Could not parse festival dates from homepage")
        return [], True  # detected but couldn't parse

    print(f"[OKCastle] Festival: {start_dt.strftime('%b %d')} – {end_dt.strftime('%b %d, %Y')}")

    # ── Generate festival days ──
    festival_days = _okrf_generate_days(start_dt, end_dt)

    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []

    for day in festival_days:
        # Future filter
        if future_only and day < now:
            continue

        wd = day.weekday()
        memorial_day = _okrf_memorial_day(day.year)

        if day.date() == memorial_day.date():
            day_label = 'Memorial Day'
        elif wd == 5:
            day_label = 'Saturday'
        else:
            day_label = 'Sunday'

        start_time = day.replace(hour=10, minute=30, second=0)
        end_time   = day.replace(hour=18, minute=0,  second=0)

        events.append({
            'title':           f'Oklahoma Renaissance Festival — {day_label}',
            'start_time':      start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'venue':           _OKRF_VENUE,
            'venue_address':   _OKRF_ADDR,
            'description':     _OKRF_DESC,
            'source_url':      _OKRF_SOURCE_URL,
            'image_url':       'https://okcastle.com/wp-content/uploads/2025/01/Untitled-design-38.png',
            'source_name':     source_name or 'Oklahoma Renaissance Festival',
            'categories':      ['Festival', 'Entertainment', 'Family', 'Outdoor', 'Arts & Culture'],
            'outdoor':         True,
            'family_friendly': True,
        })
        print(f"[OKCastle] Added: {day_label} {day.strftime('%Y-%m-%d')}")

    print(f"[OKCastle] Total days: {len(events)}")
    return events, True


# ============================================================================
# BROKEN ARROW COMMUNITY CALENDAR — CivicPlus / Vision CMS
# ============================================================================
# Site: https://www.brokenarrowok.gov/our-city/resources/community-calendar/community-calendar-list
# CMS: CivicPlus / Vision Government Solutions (used by many OK municipalities)
# Method: httpx — parses schema.org JSON-LD embedded in <script> tags
# Pagination: /-npage-{N} suffix, 20 events per page
# Dates: UTC offset format ("2026-03-24T23:30+00:00") or date-only ("2026-03-23")
#        Converts UTC to Central Time (UTC-6 standard / UTC-5 daylight)
# Filter: skips government/admin events (council meetings, bond elections, etc.)
#         to surface only community-relevant events for Locate918
# ============================================================================

_BA_BASE_URL   = 'https://www.brokenarrowok.gov/our-city/resources/community-calendar/community-calendar-list'
_BA_SOURCE_URL = _BA_BASE_URL
_BA_MAX_PAGES  = 10  # safety ceiling

# Title patterns to skip (government/administrative, not community events)
_BA_SKIP_PATTERNS = re.compile(
    r'\b(city council|planning commission|board of adjustment|'
    r'authority meeting|committee meeting|go bond|absentee ballot|'
    r'early voting|election day|city holiday|city offices closed|'
    r'city offices will be|tentative)\b',
    re.I
)

# Category mapping by title keywords
_BA_CATEGORY_MAP = [
    (re.compile(r'\b(festival|fair|bazaar|carnival|expo|gala)\b', re.I),
     ['Festival', 'Community', 'Entertainment']),
    (re.compile(r'\b(5k|run|walk|race|marathon|triathlon)\b', re.I),
     ['Sports', 'Outdoor', 'Community']),
    (re.compile(r'\b(tournament|championship|competition|game|match)\b', re.I),
     ['Sports', 'Community']),
    (re.compile(r'\b(concert|music|band|performance|show|live)\b', re.I),
     ['Music', 'Entertainment', 'Community']),
    (re.compile(r'\b(parade|celebration|ceremony|memorial)\b', re.I),
     ['Community', 'Family']),
    (re.compile(r'\b(class|camp|workshop|clinic|training|seminar|program)\b', re.I),
     ['Education', 'Community']),
    (re.compile(r'\b(farmers.?market|market|bazaar|craft)\b', re.I),
     ['Farmers Market', 'Community', 'Shopping']),
    (re.compile(r'\b(park|trail|outdoor|nature|garden)\b', re.I),
     ['Outdoor', 'Parks & Recreation', 'Community']),
    (re.compile(r'\b(fiesta|cultural|heritage|diversity)\b', re.I),
     ['Cultural', 'Community', 'Entertainment']),
]


def _ba_categories(title: str) -> list[str]:
    """Infer categories from event title."""
    for pattern, cats in _BA_CATEGORY_MAP:
        if pattern.search(title):
            return cats
    return ['Community', 'Broken Arrow']


def _ba_city_name(url: str) -> str:
    """Extract a readable city name from the URL domain."""
    import re as _re
    domain = url.split('/')[2].lower() if '/' in url else url.lower()
    domain = domain.replace('www.', '')
    name_map = {
        'brokenarrowok.gov': 'Broken Arrow',
        'jenksok.gov': 'Jenks',
        'sandspringsok.gov': 'Sand Springs',
        'bixbyok.gov': 'Bixby',
        'owassook.gov': 'Owasso',
        'claremorecity.com': 'Claremore',
        'glenpool.com': 'Glenpool',
        'cowetaok.gov': 'Coweta',
        'sapulpa.com': 'Sapulpa',
    }
    for k, v in name_map.items():
        if k in domain:
            return v
    # Fallback: strip TLD and capitalize
    base = domain.split('.')[0]
    return base.replace('-', ' ').title()


def _ba_parse_dt(date_str: str) -> datetime | None:
    """
    Parse a date string from BA calendar JSON-LD.
    Handles:
      "2026-03-23"                  → date-only, no time
      "2026-03-24T23:30+00:00"      → UTC datetime → convert to Central
    Returns a naive datetime in local (Central) time, or None on failure.
    """
    if not date_str:
        return None
    try:
        from dateutil import parser as _dp
        dt = _dp.parse(date_str)
        # If timezone-aware, convert to Central Time
        if dt.tzinfo is not None:
            # Central Time: UTC-6 standard (Nov–Mar), UTC-5 daylight (Mar–Nov)
            # Approximate: use UTC-6 for Nov 1–Mar 7, UTC-5 for Mar 8–Nov 1
            month = dt.month
            is_dst = 3 <= month <= 10  # rough approximation
            offset_hours = -5 if is_dst else -6
            from datetime import timezone as _tz
            utc_dt = dt.astimezone(_tz.utc)
            local_dt = utc_dt.replace(tzinfo=None) + timedelta(hours=offset_hours)
            return local_dt
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def _ba_parse_jsonld_events(html: str) -> list[dict]:
    """
    Extract all schema.org Event JSON-LD objects from a page's HTML.
    Returns list of raw dicts with keys: name, startDate, endDate, location.
    """
    soup = BeautifulSoup(html, 'html.parser')
    events = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
            if data.get('@type') == 'Event':
                events.append(data)
        except Exception:
            continue
    return events


async def extract_broken_arrow_events(html: str, source_name: str,
                                      url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract community events from the City of Broken Arrow community calendar.

    Uses CivicPlus / Vision CMS — events are embedded as schema.org JSON-LD
    in <script type="application/ld+json"> tags. Paginates through all pages
    using the /-npage-{N} URL pattern. Filters out government/administrative
    events (council meetings, elections, etc.) to surface only community events.
    """
    # Detect CivicPlus / Vision Government Solutions calendar
    # Pattern: /-npage-N pagination + script[type="application/ld+json"] events
    # Used by: Broken Arrow, Jenks, Sand Springs, Bixby, Owasso, Claremore, etc.
    url_lower = url.lower()
    is_civicplus = (
                           'community-calendar' in url_lower or
                           'city-calendar' in url_lower or
                           'events-calendar' in url_lower or
                           'calendar-list' in url_lower
                   ) and any(d in url_lower for d in [
        'brokenarrowok.gov', 'jenksok.gov', 'sandspringsok.gov',
        'bixbyok.gov', 'owassook.gov', 'claremorecity.com',
        'glenpool.com', 'cowetaok.gov', 'sapulpa.com',
    ])

    # Also detect by HTML fingerprint (CivicPlus /-npage- pagination is truly unique to this CMS)
    # NOTE: do NOT use ld+json/EventScheduled — many non-CivicPlus sites (e.g. Guthrie Green)
    #       have schema.org event markup for SEO and would false-positive.
    if not is_civicplus and html:
        is_civicplus = '/-npage-' in html

    if not is_civicplus:
        return [], False

    city_name = _ba_city_name(url)
    print(f"[CivicPlus] Detected CivicPlus calendar for: {city_name} ({url})")

    events = []
    seen_keys: set = set()
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # scraperRoutes.py already fetched the HTML via fetch_with_playwright before
    # calling this extractor. Use it directly for page 1 to avoid a second
    # request that Akamai would block. Only fetch subsequent pages via httpx
    # (they share the same Akamai context once the first page succeeded).
    base_url = url.rstrip('/').split('/-')[0]  # strip any existing /-npage- etc.

    async def _ba_fetch_page(client: httpx.AsyncClient, page_num: int) -> str:
        """Fetch a specific page using httpx with browser headers."""
        _hdrs = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': base_url,
        }
        page_url = base_url if page_num == 1 else f"{base_url}/-npage-{page_num}"
        resp = await client.get(page_url, headers=_hdrs, timeout=20)
        resp.raise_for_status()
        return resp.text

    def _ba_process_page(page_html: str, page_num: int) -> tuple[list, bool]:
        """Parse JSON-LD events from a page, return (raw_events, page_had_content)."""
        has_jsonld = 'EventScheduled' in page_html or 'application/ld+json' in page_html
        print(f"[CivicPlus] Page {page_num} len={len(page_html)}, has_jsonld={has_jsonld}")
        raw = _ba_parse_jsonld_events(page_html)
        return raw, has_jsonld

    # ── Page 1: use the html already fetched by scraperRoutes ──
    page1_html = html if html and ('EventScheduled' in html or 'ld+json' in html) else None

    if not page1_html:
        print(f"[CivicPlus] html param empty/missing content, will fetch page 1 directly")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for page_num in range(1, _BA_MAX_PAGES + 1):
            # Use pre-fetched HTML for page 1, httpx for subsequent pages
            if page_num == 1 and page1_html:
                page_html = page1_html
                print(f"[CivicPlus] Page 1: using pre-fetched HTML (len={len(page_html)})")
            else:
                try:
                    page_html = await _ba_fetch_page(client, page_num)
                except Exception as e:
                    print(f"[CivicPlus] Fetch error page {page_num}: {e}")
                    break

            raw_events, has_content = _ba_process_page(page_html, page_num)
            if not raw_events:
                if not has_content and page_num == 1:
                    print(f"[CivicPlus] Page 1 blocked/empty — cannot proceed")
                else:
                    print(f"[CivicPlus] No events on page {page_num}, stopping")
                break

            print(f"[CivicPlus] Page {page_num}: {len(raw_events)} raw events")
            page_had_new = False

            for ev in raw_events:
                title = ev.get('name', '').strip()
                if not title:
                    continue

                # Dedup
                dedup_key = title.lower()[:60]
                start_raw = ev.get('startDate', '')
                if start_raw:
                    dedup_key += '|' + start_raw[:10]
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                page_had_new = True

                # Skip government/admin events
                if _BA_SKIP_PATTERNS.search(title):
                    continue

                # Parse dates
                start_dt = _ba_parse_dt(start_raw)
                end_dt   = _ba_parse_dt(ev.get('endDate', ''))

                if not start_dt:
                    print(f"[CivicPlus] Skipping (no date): {title}")
                    continue

                # Future filter
                if future_only:
                    check_dt = end_dt or start_dt
                    if check_dt.date() < cutoff.date():
                        continue

                # Location
                loc = ev.get('location', {}) or {}
                venue_name    = loc.get('name') or city_name
                venue_address = loc.get('address', '').strip()

                if venue_address and city_name not in venue_address and 'OK' not in venue_address:
                    venue_address += f', {city_name}, OK'
                elif not venue_address:
                    venue_address = f'{city_name}, OK'

                events.append({
                    'title':           title,
                    'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
                    'venue':           venue_name,
                    'venue_address':   venue_address,
                    'description':     title,
                    'source_url':      base_url,
                    'image_url':       '',
                    'source_name':     source_name or f'City of {city_name}',
                    'categories':      _ba_categories(title),
                    'outdoor':         None,
                    'family_friendly': None,
                })
                print(f"[CivicPlus] Added: {title} on {start_dt.strftime('%Y-%m-%d')}")

            if not page_had_new:
                print(f"[CivicPlus] No new events on page {page_num}, done")
                break

    print(f"[CivicPlus/{city_name}] Total community events: {len(events)}")
    return events, True


# ============================================================================
# TULSA ZOO — Custom CMS Event Calendar
# ============================================================================
# Site: https://tulsazoo.org/events
# Method: httpx (static HTML, custom CMS — no WordPress/Tribe)
# Structure:
#   Featured event: .content-feature div → date in <p>, title in <h1/h2/h3>
#   Event cards: .column-cell divs containing <h4> date elements
#     - Single-date: one <h4>
#     - Multi-date: multiple <h4> tags (e.g. Zoo Nights has 4 dates)
#     - Date range: text like "October 2026" or "October 29 & 30, 2026"
#   Each card also has: title (first text line), description, <a> link, <img>
# ============================================================================

_TULSAZOO_SOURCE_URL = 'https://tulsazoo.org/events'
_TULSAZOO_VENUE      = 'Tulsa Zoo'
_TULSAZOO_ADDR       = '6421 E 36th St N, Tulsa, OK 74115'


def _zoo_parse_date_str(date_str: str) -> tuple[datetime | None, datetime | None]:
    """
    Parse a Tulsa Zoo date string into (start_dt, end_dt).

    Handles:
      "April 4, 2026"              → single day
      "April 24, 2026"             → single day
      "October 29 & 30, 2026"      → two-day range
      "March 26 - June 7, 2026"    → multi-week range
      "October 2026"               → month-only → first of month
    """
    from dateutil import parser as _dp
    ds = date_str.strip()

    # Multi-week range: "March 26 - June 7, 2026"
    range_m = re.match(
        r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(\d{1,2})\s*[-–]\s*'
        r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(\d{1,2}),?\s+(\d{4})', ds, re.I
    )
    if range_m:
        try:
            start = _dp.parse(f"{range_m.group(1)} {range_m.group(2)}, {range_m.group(5)}")
            end   = _dp.parse(f"{range_m.group(3)} {range_m.group(4)}, {range_m.group(5)}")
            return start, end
        except Exception:
            pass

    # Two-day range same month: "October 29 & 30, 2026"
    twoday_m = re.match(
        r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(\d{1,2})\s*[&]\s*(\d{1,2}),?\s+(\d{4})', ds, re.I
    )
    if twoday_m:
        try:
            start = _dp.parse(f"{twoday_m.group(1)} {twoday_m.group(2)}, {twoday_m.group(4)}")
            end   = _dp.parse(f"{twoday_m.group(1)} {twoday_m.group(3)}, {twoday_m.group(4)}")
            return start, end
        except Exception:
            pass

    # Month-only: "October 2026"
    month_m = re.match(
        r'^(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(\d{4})$', ds, re.I
    )
    if month_m:
        try:
            start = _dp.parse(f"{month_m.group(1)} 1, {month_m.group(2)}")
            return start, None
        except Exception:
            pass

    # Standard single date: "April 4, 2026"
    try:
        start = _dp.parse(ds)
        return start, None
    except Exception:
        pass

    return None, None


def _zoo_categories(title: str, desc: str) -> list[str]:
    t = (title + ' ' + desc).lower()
    cats = ['Family', 'Animals & Nature']
    if any(w in t for w in ['run', '5k', '10k', 'race', 'walk']):
        cats = ['Sports', 'Outdoor', 'Family']
    elif any(w in t for w in ['halloween', 'spooky', 'goblin', 'pirates', 'princess']):
        cats = ['Family', 'Festival', 'Entertainment']
    elif any(w in t for w in ['santa', 'holiday', 'christmas', 'sweets']):
        cats = ['Family', 'Holiday', 'Entertainment']
    elif any(w in t for w in ['after hours', 'adults only', 'adult', 'beer', 'tap', 'drink', 'nights']):
        cats = ['Adults Only', 'Entertainment', 'Nightlife']
    elif any(w in t for w in ['fundrais', 'gala', 'waltz', 'conservation on tap']):
        cats = ['Fundraiser', 'Community', 'Entertainment']
    elif any(w in t for w in ['earth', 'conservation', 'wildlife', 'nature']):
        cats = ['Family', 'Education', 'Animals & Nature']
    elif any(w in t for w in ['lantern', 'light', 'illuminate', 'glow']):
        cats = ['Family', 'Festival', 'Entertainment']
    return cats


async def extract_tulsazoo_events(html: str, source_name: str,
                                  url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Tulsa Zoo's event calendar (tulsazoo.org/events).

    Custom CMS — static HTML with no calendar plugin. Events are in two formats:
    1. Featured event: .content-feature with date in <p> tag (may be a range)
    2. Event cards: .column-cell divs with <h4> date tags. Cards with multiple
       dates (like Zoo Nights) produce one event per date.
    Uses httpx (no Playwright needed — no bot protection on this site).
    """
    if 'tulsazoo.org' not in url.lower():
        return [], False

    print(f"[TulsaZoo] Detected Tulsa Zoo events page...")

    # Fetch if html not usable
    page_html = html
    if not page_html or 'column-cell' not in page_html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_TULSAZOO_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                page_html = resp.text
        except Exception as e:
            print(f"[TulsaZoo] Fetch error: {e}")
            return [], True

    soup = BeautifulSoup(page_html, 'html.parser')
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []

    def _make_event(title, date_str, start_dt, end_dt, desc, link, img):
        """Build a single event dict."""
        if future_only:
            check = end_dt or start_dt
            if check < cutoff:
                return None
        return {
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           _TULSAZOO_VENUE,
            'venue_address':   _TULSAZOO_ADDR,
            'description':     desc[:500],
            'source_url':      link or _TULSAZOO_SOURCE_URL,
            'image_url':       img or '',
            'source_name':     source_name or 'Tulsa Zoo',
            'categories':      _zoo_categories(title, desc),
            'outdoor':         True,
            'family_friendly': True,
        }

    # ── 1. Featured event (.content-feature) ──
    featured = soup.select_one('.content-feature')
    if featured:
        feat_title = ''
        for tag in ['h1', 'h2', 'h3']:
            el = featured.select_one(tag)
            if el:
                feat_title = el.get_text(strip=True)
                break
        feat_date_el = featured.select_one('p')
        feat_date_str = feat_date_el.get_text(strip=True) if feat_date_el else ''
        feat_desc = ' '.join(
            p.get_text(strip=True) for p in featured.select('p')
            if not re.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', p.get_text(strip=True), re.I)
        )[:500]
        feat_link_el = featured.select_one('a[href]')
        feat_link = feat_link_el['href'] if feat_link_el else _TULSAZOO_SOURCE_URL
        if feat_link and not feat_link.startswith('http'):
            feat_link = 'https://tulsazoo.org' + feat_link
        feat_img_el = featured.select_one('img')
        feat_img = feat_img_el.get('src', '') if feat_img_el else ''

        if feat_title and feat_date_str:
            start_dt, end_dt = _zoo_parse_date_str(feat_date_str)
            if start_dt:
                ev = _make_event(feat_title, feat_date_str, start_dt, end_dt, feat_desc, feat_link, feat_img)
                if ev:
                    events.append(ev)
                    print(f"[TulsaZoo] Featured: {feat_title} ({feat_date_str})")

    # ── 2. Event cards (.column-cell containing <h4> dates) ──
    for card in soup.select('.column-cell'):
        date_tags = card.select('h4')
        if not date_tags:
            continue

        # Extract title (first non-empty text node before the first h4)
        all_lines = [l.strip() for l in card.get_text('\n').split('\n') if l.strip()]
        if not all_lines:
            continue
        title = all_lines[0]

        # Description: text after the last date, before "Learn More"
        last_date_idx = max(
            i for i, l in enumerate(all_lines)
            if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', l, re.I)
        )
        desc_lines = [l for l in all_lines[last_date_idx + 1:] if l.lower() != 'learn more']
        desc = ' '.join(desc_lines)[:500]

        link_el = card.select_one('a[href]')
        link = link_el['href'] if link_el else _TULSAZOO_SOURCE_URL
        if link and not link.startswith('http'):
            link = 'https://tulsazoo.org' + link

        img_el = card.select_one('img')
        img = img_el.get('src', '') if img_el else ''
        if img and not img.startswith('http'):
            img = 'https://tulsazoo.org' + img

        # One event per date tag (handles multi-date cards like Zoo Nights)
        for date_tag in date_tags:
            date_str = date_tag.get_text(strip=True)
            start_dt, end_dt = _zoo_parse_date_str(date_str)
            if not start_dt:
                print(f"[TulsaZoo] Could not parse date: {date_str!r} for {title}")
                continue
            ev = _make_event(title, date_str, start_dt, end_dt, desc, link, img)
            if ev:
                events.append(ev)
                print(f"[TulsaZoo] Added: {title} on {start_dt.strftime('%Y-%m-%d')}")

    print(f"[TulsaZoo] Total events: {len(events)}")
    return events, True


# ============================================================================
# HARD ROCK CASINO TULSA — Entertainment Calendar
# ============================================================================
# Site: https://www.hardrockcasinotulsa.com/entertainment
# CMS: Next.js App Router + Contentstack headless CMS
# Method: httpx — GET requests to /?page=N (0-indexed in URL, displayed 1-5)
#   - No page param = page 1
#   - ?page=1 = page 2, ?page=2 = page 3, ... ?page=4 = last page
#   - Redirects back to page 1 when out of range
# Structure: .EntertainmentCard_card__ divs, each with:
#   - lines[0]: title (e.g. "NIKO MOON")
#   - lines[1]: "FRI, APR 3   |   8:00 PM"
#   - lines[2]: admission (e.g. "21+ | Free Show" or "Door: 7PM | Tickets start: $19.50")
#   - lines[3]: venue tag (RIFFS, TRACK5., AMPBAR, HARDROCKLIVE)
#   - CTA link: ticket URL (hardrocklive events only)
#   - img: Contentstack CDN URL
# ============================================================================

_HRCT_SOURCE_URL = 'https://www.hardrockcasinotulsa.com/entertainment'
_HRCT_ADDR       = '777 W Cherokee St, Catoosa, OK 74015'

# Venue tag → full venue name
_HRCT_VENUE_MAP = {
    'hardrocklive': 'Hard Rock Live',
    'riffs':        'Riffs',
    'track5.':      'Track5.',
    'track5':       'Track5.',
    'ampbar':       'AmpBar',
    'amp bar':      'AmpBar',
}


def _hrct_parse_datetime(dt_str: str) -> tuple:
    """
    Parse Hard Rock's date/time string: "FRI, APR 3   |   8:00 PM"
    Returns (start_dt, end_dt=None).
    """
    from dateutil import parser as _dp
    dt_str = dt_str.strip()
    if '|' in dt_str:
        date_part, time_part = dt_str.split('|', 1)
        date_part = re.sub(r'^[A-Z]{3},\s*', '', date_part.strip())  # strip "FRI, "
        time_part = time_part.strip()
        try:
            base = _dp.parse(date_part.strip())
            t    = _dp.parse(time_part.strip())
            return base.replace(hour=t.hour, minute=t.minute, second=0), None
        except Exception:
            pass
    try:
        return _dp.parse(dt_str), None
    except Exception:
        return None, None


def _hrct_categories(title: str, venue_tag: str, admission: str) -> list[str]:
    t = (title + ' ' + venue_tag).lower()
    cats = ['Music', 'Entertainment']
    if 'dj' in title.lower():
        cats = ['Music', 'Nightlife', 'Entertainment']
    elif any(w in t for w in ['comedy', 'comedian', 'stand up', 'stand-up']):
        cats = ['Comedy', 'Entertainment']
    elif any(w in t for w in ['hardrocklive', 'hard rock live']):
        cats = ['Music', 'Concert', 'Entertainment']
    if 'free' in admission.lower():
        cats.append('Free')
    return cats


async def extract_hardrock_tulsa_events(html: str, source_name: str,
                                        url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract entertainment events from Hard Rock Casino Tulsa.

    Next.js + Contentstack site. Pagination via GET ?page=N (0-indexed).
    Cards contain title, date/time string, admission info, venue tag, and
    optionally a ticket purchase URL for Hard Rock Live shows.
    Fetches up to page=4 (5 pages), stopping when a page has fewer cards
    than expected (last page) or redirects back to page 1.
    """
    if 'hardrockcasinotulsa.com' not in url.lower():
        return [], False

    print(f"[HardRockTulsa] Detected Hard Rock Casino Tulsa entertainment...")

    events = []
    seen_keys: set = set()
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    _HRCT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        for page_num in range(5):  # pages 0-4
            page_url = _HRCT_SOURCE_URL if page_num == 0 else f"{_HRCT_SOURCE_URL}?page={page_num}"

            try:
                resp = await client.get(page_url, headers=_HRCT_HEADERS)
                # If redirected (out of range), stop
                if resp.status_code in (301, 302, 307, 308):
                    print(f"[HardRockTulsa] Page {page_num+1} redirected — done")
                    break
                resp.raise_for_status()
                page_html = resp.text
            except Exception as e:
                print(f"[HardRockTulsa] Fetch error page {page_num+1}: {e}")
                break

            # Use pre-fetched html for page 0 if it has the right content
            if page_num == 0 and html and 'EntertainmentCard_card' in html:
                page_html = html
                print(f"[HardRockTulsa] Page 1: using pre-fetched HTML")

            soup = BeautifulSoup(page_html, 'html.parser')
            cards = soup.select('[class*="EntertainmentCard_card"]')
            if not cards:
                print(f"[HardRockTulsa] No cards on page {page_num+1}, stopping")
                break

            print(f"[HardRockTulsa] Page {page_num+1}: {len(cards)} cards")

            for card in cards:
                lines = [l.strip() for l in card.get_text('\n').split('\n')
                         if l.strip() and l.strip().lower() != 'buy tickets']
                if len(lines) < 3:
                    continue

                title     = lines[0]
                dt_raw    = lines[1] if len(lines) > 1 else ''
                admission = lines[2] if len(lines) > 2 else ''
                venue_tag = lines[3].lower() if len(lines) > 3 else ''

                # Dedup
                dedup_key = f"{title.lower()}|{dt_raw}"
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                # Date
                start_dt, _ = _hrct_parse_datetime(dt_raw)
                if not start_dt:
                    print(f"[HardRockTulsa] Could not parse date: {dt_raw!r}")
                    continue

                if future_only and start_dt < cutoff:
                    continue

                # Venue
                venue_name = _HRCT_VENUE_MAP.get(venue_tag, venue_tag.title() or 'Hard Rock Casino Tulsa')
                full_venue = f"{venue_name} at Hard Rock Casino Tulsa"

                # Ticket link (only on Hard Rock Live events)
                ticket_link = ''
                cta = card.select_one('a[href*="tickets"], a[href*="ticket"]')
                if cta:
                    ticket_link = cta.get('href', '')

                # Detail page link
                detail_link = ''
                detail_a = card.select_one(f'a[href*="/entertainment/"]')
                if detail_a:
                    detail_link = detail_a.get('href', '')
                    if detail_link and not detail_link.startswith('http'):
                        detail_link = 'https://www.hardrockcasinotulsa.com' + detail_link

                source_url = ticket_link or detail_link or _HRCT_SOURCE_URL

                # Image
                img_el = card.select_one('img')
                img_url = ''
                if img_el:
                    src = img_el.get('src', '') or img_el.get('data-src', '')
                    # Strip Next.js image optimization params, keep clean Contentstack URL
                    if 'contentstack.io' in src:
                        img_url = src.split('?')[0]
                    elif src:
                        img_url = src

                events.append({
                    'title':           title,
                    'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end_time':        '',
                    'venue':           full_venue,
                    'venue_address':   _HRCT_ADDR,
                    'description':     admission,
                    'source_url':      source_url,
                    'image_url':       img_url,
                    'source_name':     source_name or 'Hard Rock Casino Tulsa',
                    'categories':      _hrct_categories(title, venue_tag, admission),
                    'outdoor':         False,
                    'family_friendly': False,
                })
                print(f"[HardRockTulsa] Added: {title} on {start_dt.strftime('%Y-%m-%d')} @ {venue_name}")

            # If last page had fewer cards, we're done
            if len(cards) < 16:
                print(f"[HardRockTulsa] Partial page ({len(cards)} cards) — last page")
                break

    print(f"[HardRockTulsa] Total events: {len(events)}")
    return events, True


# ============================================================================
# GYPSY COFFEE HOUSE — Computed Recurring Event Schedule (Weebly Site)
# ============================================================================
# Site: https://www.gypsycoffee.com/events--music.html
# Method: Computed — no scraping needed. Schedule is stable and recurring.
#         Specific performers are booked via email/Facebook, not posted online.
# Schedule:
#   Every Tuesday  → Open Mic Night, 7:00 PM
#   Every Friday   → Live Music, 9:00 PM
#   Every Saturday → Live Music, 9:00 PM
#   First Friday   → First Friday Art Crawl (labeled separately)
# Location: 303 N Cincinnati Ave, Tulsa, OK 74103 (Tulsa Arts District)
# ============================================================================

_GYPSY_SOURCE_URL = 'https://www.gypsycoffee.com/events--music.html'
_GYPSY_VENUE      = 'The Gypsy Coffee House'
_GYPSY_ADDR       = '303 N Cincinnati Ave, Tulsa, OK 74103'
_GYPSY_LOOKAHEAD  = 28  # days


def _gypsy_is_first_friday(dt: datetime) -> bool:
    """Returns True if dt is the first Friday of its month."""
    return dt.weekday() == 4 and dt.day <= 7


async def extract_gypsy_events(html: str, source_name: str,
                               url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Generate recurring events for The Gypsy Coffee House (gypsycoffee.com).

    The site is a Weebly page with no structured event data — specific
    performers are booked via email/Facebook. The recurring schedule is:
      - Tuesday Open Mic Night (7pm, every week)
      - Friday Live Music (9pm, every week — First Friday labeled separately)
      - Saturday Live Music (9pm, every week)

    Generates a rolling 28-day window of upcoming dates.
    """
    if 'gypsycoffee.com' not in url.lower():
        return [], False

    print(f"[Gypsy] Detected Gypsy Coffee House, generating recurring schedule...")

    today  = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end    = today + timedelta(days=_GYPSY_LOOKAHEAD)
    events = []
    current = today

    while current <= end:
        wd = current.weekday()  # 0=Mon, 4=Fri, 5=Sat, 1=Tue

        if wd == 1:  # Tuesday — Open Mic
            start_dt = current.replace(hour=19, minute=0, second=0)
            events.append({
                'title':           'Tuesday Night Open Mic',
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        current.replace(hour=22, minute=0, second=0).strftime('%Y-%m-%dT%H:%M:%S'),
                'venue':           _GYPSY_VENUE,
                'venue_address':   _GYPSY_ADDR,
                'description':     "Tulsa's longest running open mic! All original material only — lyrics, music, poetry, comedy. No covers. Sign-ups at 6:30pm, show starts 7pm.",
                'source_url':      _GYPSY_SOURCE_URL,
                'image_url':       '',
                'source_name':     source_name or 'The Gypsy Coffee House',
                'categories':      ['Music', 'Open Mic', 'Community', 'Arts & Culture'],
                'outdoor':         False,
                'family_friendly': True,
            })

        elif wd == 4:  # Friday — Live Music or First Friday Art Crawl
            start_dt = current.replace(hour=21, minute=0, second=0)
            if _gypsy_is_first_friday(current):
                title = 'First Friday Art Crawl at Gypsy Coffee House'
                desc  = ('First Friday Art Crawl in the Tulsa Arts District. '
                         'Gypsy hosts local musicians and a featured artist. '
                         'Part of the historic downtown Tulsa Arts District showcase.')
                cats  = ['Arts & Culture', 'Music', 'Community', 'Festival']
            else:
                title = 'Live Music at Gypsy Coffee House'
                desc  = 'Live original music at The Gypsy Coffee House in the Tulsa Arts District. Performers booked monthly — check their Facebook for specific artists.'
                cats  = ['Music', 'Live Music', 'Community', 'Arts & Culture']

            events.append({
                'title':           title,
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        '',
                'venue':           _GYPSY_VENUE,
                'venue_address':   _GYPSY_ADDR,
                'description':     desc,
                'source_url':      _GYPSY_SOURCE_URL,
                'image_url':       '',
                'source_name':     source_name or 'The Gypsy Coffee House',
                'categories':      cats,
                'outdoor':         False,
                'family_friendly': True,
            })

        elif wd == 5:  # Saturday — Live Music
            start_dt = current.replace(hour=21, minute=0, second=0)
            events.append({
                'title':           'Live Music at Gypsy Coffee House',
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        '',
                'venue':           _GYPSY_VENUE,
                'venue_address':   _GYPSY_ADDR,
                'description':     'Live original music at The Gypsy Coffee House in the Tulsa Arts District. Performers booked monthly — check their Facebook for specific artists.',
                'source_url':      _GYPSY_SOURCE_URL,
                'image_url':       '',
                'source_name':     source_name or 'The Gypsy Coffee House',
                'categories':      ['Music', 'Live Music', 'Community', 'Arts & Culture'],
                'outdoor':         False,
                'family_friendly': True,
            })

        current += timedelta(days=1)

    print(f"[Gypsy] Generated {len(events)} events over next {_GYPSY_LOOKAHEAD} days")
    return events, True


# ============================================================================
# BAD ASS RENEE'S — GoDaddy Website Builder Calendar API
# ============================================================================
# Site: https://badassrenees.net/bands%2Fevents
# Method: httpx — direct call to GoDaddy's calendar.apps.secureserver.net API
#         The widget-calendar on the page calls this public JSON endpoint.
#         IDs are tied to the GoDaddy account and stable unless site is rebuilt.
# API:    GET https://calendar.apps.secureserver.net/v1/events/{siteId}/{widgetId}/{calId}
# Returns: { events: [{title, desc, location, start, end, allDay}], timeZone }
#          Datetimes are ISO 8601 with CDT/CST offset (-05:00 / -06:00)
# Note:   31 events; ~30 are weekly "OPEN JAM NIGHT" recurring entries.
#         All are valid events — Open Jam is a real weekly fixture.
# ============================================================================

_BADASS_SOURCE_URL = 'https://badassrenees.net/bands%2Fevents'
_BADASS_API_URL    = (
    'https://calendar.apps.secureserver.net/v1/events'
    '/a88f02b1-1ade-4376-bf85-4ef71e950d9f'
    '/fdf891ac-b81c-4743-a05f-a5ae936001ed'
    '/17aa3db7-fee1-4c3a-a62e-4b0f3d24c4dc'
)
_BADASS_VENUE   = "Bad Ass Renee's"
_BADASS_ADDR    = '6373 E 31st St, Tulsa, OK 74135'


def _badass_categories(title: str) -> list[str]:
    t = title.lower()
    if 'open jam' in t or 'jam night' in t:
        return ['Music', 'Open Mic', 'Community']
    if any(w in t for w in ['massacre', 'metal', 'punk', 'hardcore']):
        return ['Music', 'Concert', 'Rock']
    if any(w in t for w in ['benefit', 'fundrais', 'charity']):
        return ['Music', 'Fundraiser', 'Community']
    if any(w in t for w in ['karaoke', 'trivia', 'bingo']):
        return ['Entertainment', 'Community']
    return ['Music', 'Live Music', 'Entertainment']


async def extract_badass_renees_events(html: str, source_name: str,
                                       url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Bad Ass Renee's via GoDaddy's calendar API.

    The GoDaddy Website Builder calendar widget fetches from a public JSON
    endpoint at calendar.apps.secureserver.net. The IDs are stable per account.
    Returns ISO 8601 datetimes in America/Chicago timezone.
    """
    if 'badassrenees.net' not in url.lower():
        return [], False

    print(f"[BadAssRenees] Detected Bad Ass Renee's, calling GoDaddy calendar API...")

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(_BADASS_API_URL, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[BadAssRenees] API error: {e}")
        return [], True

    raw_events = data.get('events', [])
    print(f"[BadAssRenees] API returned {len(raw_events)} events")

    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    seen: set = set()

    for ev in raw_events:
        title = (ev.get('title') or '').strip()
        if not title:
            continue

        start_raw = ev.get('start', '')
        end_raw   = ev.get('end', '')

        try:
            from dateutil import parser as _dp
            start_dt = _dp.parse(start_raw).replace(tzinfo=None)
            end_dt   = _dp.parse(end_raw).replace(tzinfo=None) if end_raw else None
        except Exception:
            print(f"[BadAssRenees] Could not parse date: {start_raw}")
            continue

        if future_only and start_dt < cutoff:
            continue

        # Dedup by title + date (recurring Open Jam creates many identical entries)
        dedup_key = f"{title.lower()}|{start_dt.date()}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        desc     = (ev.get('desc') or '').strip()
        location = (ev.get('location') or '').strip()

        # Open Jam has a standard description we can fill in
        if not desc and 'open jam' in title.lower():
            desc = 'Open Jam Night — bring your instrument and join in! All genres welcome. Bad Ass Renee\'s, 6373 E 31st St, Tulsa.'

        events.append({
            'title':           title,
            'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
            'venue':           _BADASS_VENUE,
            'venue_address':   location or _BADASS_ADDR,
            'description':     desc,
            'source_url':      _BADASS_SOURCE_URL,
            'image_url':       '',
            'source_name':     source_name or "Bad Ass Renee's",
            'categories':      _badass_categories(title),
            'outdoor':         False,
            'family_friendly': False,
        })
        print(f"[BadAssRenees] Added: {title} on {start_dt.strftime('%Y-%m-%d')}")

    print(f"[BadAssRenees] Total events: {len(events)}")
    return events, True

# ============================================================================