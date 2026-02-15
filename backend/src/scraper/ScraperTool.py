"""
Locate918 Universal Scraper Tool
================================
Smart extraction that handles ANY site format. No LLM required.
Respects robots.txt - will not scrape sites that disallow it.

Extraction strategies (in priority order):

DIRECT APIs:
1. EventCalendarApp API (Guthrie Green, Fly Loft, etc.)
2. Timely API (Starlite Bar, etc.)
3. BOK Center API
4. Expo Square / Saffire CMS API
5. Eventbrite API (any Eventbrite search/destination page)
6. Simpleview CMS API (VisitTulsa.com, etc.)

STRUCTURED DATA:
7. Schema.org/JSON-LD

TICKETING PLATFORMS:
6. WordPress Events Calendar (Tribe)
7. Eventbrite
8. Stubwire (Tulsa Shrine)
9. Dice.fm
10. Bandsintown
11. Songkick
12. Ticketmaster
13. AXS
14. Etix
15. See Tickets

FALLBACKS:
16. Timely HTML
17. Repeating structure detection
18. Date/time pattern matching

Usage:
    pip install flask playwright httpx beautifulsoup4 python-dotenv python-dateutil
    playwright install chromium
    python ScraperTool.py

Open http://localhost:5000
"""

import os
import re
import json
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from flask import Flask, render_template_string, request, jsonify, send_file
import httpx
from bs4 import BeautifulSoup, NavigableString
from dotenv import load_dotenv

load_dotenv()

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available - install with: pip install playwright && playwright install chromium")

app = Flask(__name__)

OUTPUT_DIR = Path("scraped_data")
OUTPUT_DIR.mkdir(exist_ok=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")
HEADERS = {"User-Agent": "Locate918 Event Aggregator (educational project)"}

# Cache for robots.txt parsers (avoid re-fetching)
_robots_cache = {}

# Cache for venue websites (avoid re-fetching listing pages)
_venue_website_cache = {}


def fetch_venue_website_from_listing(listing_url: str, base_url: str = "https://www.visittulsa.com") -> str:
    """
    Fetch a venue's website URL from their VisitTulsa listing page.
    Parses the HTML to find the "Visit Website" link.

    Args:
        listing_url: Relative URL like "/listing/circle-cinema/123/"
        base_url: Base URL of the site

    Returns:
        The venue's website URL, or empty string if not found
    """
    if not listing_url:
        return ''

    # Check cache first
    cache_key = listing_url
    if cache_key in _venue_website_cache:
        return _venue_website_cache[cache_key]

    try:
        # Build full URL
        if listing_url.startswith('/'):
            full_url = base_url + listing_url
        elif not listing_url.startswith('http'):
            full_url = base_url + '/' + listing_url
        else:
            full_url = listing_url

        # Fetch the listing page
        resp = httpx.get(full_url, headers=HEADERS, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            _venue_website_cache[cache_key] = ''
            return ''

        # Parse HTML
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for "Visit Website" link - common patterns
        # 1. Link with text "Visit Website"
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True).lower()
            if 'visit website' in link_text or 'official website' in link_text:
                href = link['href']
                # Skip internal links and aggregator links
                if href.startswith('http') and 'visittulsa.com' not in href:
                    _venue_website_cache[cache_key] = href
                    return href

        # 2. Link with class containing "website"
        for link in soup.find_all('a', class_=lambda c: c and 'website' in c.lower() if c else False):
            href = link.get('href', '')
            if href.startswith('http') and 'visittulsa.com' not in href:
                _venue_website_cache[cache_key] = href
                return href

        # 3. Look for links in a "contact" or "info" section
        for section in soup.find_all(['div', 'section'], class_=lambda c: c and any(x in c.lower() for x in ['contact', 'info', 'details']) if c else False):
            for link in section.find_all('a', href=True):
                href = link['href']
                if href.startswith('http') and 'visittulsa.com' not in href and 'google.com' not in href and 'facebook.com' not in href:
                    _venue_website_cache[cache_key] = href
                    return href

        _venue_website_cache[cache_key] = ''
        return ''

    except Exception as e:
        print(f"[VenueWebsite] Error fetching {listing_url}: {e}")
        _venue_website_cache[cache_key] = ''
        return ''


def check_robots_txt(url: str) -> dict:
    """
    Check if we're allowed to scrape this URL according to robots.txt.
    Returns: {'allowed': bool, 'message': str}
    """
    try:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_url}/robots.txt"

        # Check cache first
        if base_url in _robots_cache:
            rp = _robots_cache[base_url]
        else:
            rp = RobotFileParser()
            rp.set_url(robots_url)

            # Fetch with timeout
            try:
                response = httpx.get(robots_url, timeout=5, follow_redirects=True)
                if response.status_code == 200:
                    rp.parse(response.text.splitlines())
                else:
                    # No robots.txt or error - assume allowed
                    _robots_cache[base_url] = None
                    return {'allowed': True, 'message': 'No robots.txt found - proceeding'}
            except Exception as e:
                # Can't fetch robots.txt - assume allowed
                _robots_cache[base_url] = None
                return {'allowed': True, 'message': f'Could not fetch robots.txt - proceeding'}

            _robots_cache[base_url] = rp

        if rp is None:
            return {'allowed': True, 'message': 'No robots.txt'}

        # Check if our user-agent is allowed
        user_agent = HEADERS.get('User-Agent', '*')
        allowed = rp.can_fetch(user_agent, url)

        # Also check with * (generic)
        if not allowed:
            allowed = rp.can_fetch('*', url)

        if allowed:
            return {'allowed': True, 'message': 'Allowed by robots.txt'}
        else:
            # Get the crawl delay if any
            delay = rp.crawl_delay(user_agent)
            msg = f'Blocked by robots.txt for path: {parsed.path}'
            if delay:
                msg += f' (crawl-delay: {delay}s)'
            return {'allowed': False, 'message': msg}

    except Exception as e:
        # On any error, allow but warn
        return {'allowed': True, 'message': f'robots.txt check error: {str(e)[:50]}'}


# Simple URL history file
SAVED_URLS_FILE = OUTPUT_DIR / "saved_urls.json"


def load_saved_urls() -> list:
    """Load saved URLs from file."""
    if SAVED_URLS_FILE.exists():
        try:
            return json.loads(SAVED_URLS_FILE.read_text())
        except:
            return []
    return []


def save_url(url: str, name: str, use_playwright: bool = True) -> list:
    """Add a URL to saved list."""
    urls = load_saved_urls()
    # Update if exists, otherwise add
    for u in urls:
        if u['url'] == url:
            u['name'] = name
            u['playwright'] = use_playwright
            SAVED_URLS_FILE.write_text(json.dumps(urls, indent=2))
            return urls

    urls.append({'url': url, 'name': name, 'playwright': use_playwright})
    SAVED_URLS_FILE.write_text(json.dumps(urls, indent=2))
    return urls


def delete_saved_url(url: str) -> list:
    """Remove a URL from saved list."""
    urls = load_saved_urls()
    urls = [u for u in urls if u['url'] != url]
    SAVED_URLS_FILE.write_text(json.dumps(urls, indent=2))
    return urls


# ============================================================================
# DATE/TIME PATTERN MATCHING
# ============================================================================

# Regex patterns for dates
DATE_PATTERNS = [
    # "Feb 5", "February 5", "Feb 5, 2026"
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?',
    # "2/5/2026", "02/05/26"
    r'\d{1,2}/\d{1,2}/\d{2,4}',
    # "2026-02-05"
    r'\d{4}-\d{2}-\d{2}',
    # "Thursday, February 5"
    r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+[A-Z][a-z]+\s+\d{1,2}',
]

# Regex patterns for times
TIME_PATTERNS = [
    # "8:00pm", "8:00 PM", "20:00"
    r'\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?',
    # "8pm", "8 PM"
    r'\d{1,2}\s*(?:am|pm|AM|PM)',
    # "Doors: 7pm"
    r'[Dd]oors:?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?',
]

COMBINED_DATE_PATTERN = re.compile('|'.join(f'({p})' for p in DATE_PATTERNS), re.IGNORECASE)
COMBINED_TIME_PATTERN = re.compile('|'.join(f'({p})' for p in TIME_PATTERNS), re.IGNORECASE)


def extract_date_from_text(text):
    """Extract date string from text."""
    match = COMBINED_DATE_PATTERN.search(text)
    return match.group(0).strip() if match else None


def extract_time_from_text(text):
    """Extract time string from text."""
    match = COMBINED_TIME_PATTERN.search(text)
    return match.group(0).strip() if match else None


def text_has_date(text):
    """Check if text contains a date pattern."""
    return bool(COMBINED_DATE_PATTERN.search(text))


# ============================================================================
# KNOWN PLUGIN EXTRACTORS
# ============================================================================

def extract_tribe_events(soup, base_url, source_name):
    """Extract from The Events Calendar (WordPress plugin) - used by Starlite Bar."""
    events = []

    # Try multiple selectors used by different versions of the plugin
    selectors = [
        '.tribe-events-calendar-list__event',
        '.tribe-events-calendar-list__event-row',
        '.tribe_events',
        '.type-tribe_events',
        '[class*="tribe-events"]',
        '.tribe-event-featured',
    ]

    containers = []
    for sel in selectors:
        containers.extend(soup.select(sel))

    # Also try the list items in the calendar
    if not containers:
        # Look for the event list structure
        event_list = soup.select('.tribe-events-calendar-list')
        for lst in event_list:
            # Get direct article/div children that look like events
            for child in lst.find_all(['article', 'div', 'li'], recursive=False):
                containers.append(child)

    seen = set()
    for container in containers:
        # Get title
        title_el = (
                container.select_one('.tribe-events-calendar-list__event-title a') or
                container.select_one('.tribe-events-calendar-list__event-title') or
                container.select_one('.tribe-event-url') or
                container.select_one('h3 a') or
                container.select_one('h2 a') or
                container.select_one('a[href*="event"]')
        )

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or title in seen:
            continue
        seen.add(title)

        # Get link
        link = ''
        if title_el.name == 'a':
            link = title_el.get('href', '')
        else:
            link_el = title_el.find('a') or container.select_one('a[href*="event"]')
            if link_el:
                link = link_el.get('href', '')

        # Get date/time
        date_el = (
                container.select_one('.tribe-events-calendar-list__event-datetime') or
                container.select_one('.tribe-event-date-start') or
                container.select_one('time') or
                container.select_one('[datetime]') or
                container.select_one('.tribe-event-schedule-details')
        )

        date_str = ''
        if date_el:
            # Try datetime attribute first
            date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        # If no date found in element, look in container text
        if not date_str:
            container_text = container.get_text(' ', strip=True)
            date_str = extract_date_from_text(container_text) or ''
            time_str = extract_time_from_text(container_text)
            if time_str and date_str:
                date_str = f"{date_str} @ {time_str}"

        events.append({
            'title': title,
            'date': date_str,
            'source_url': urljoin(base_url, link) if link else '',
            'source': source_name,
            'venue': source_name,
        })

    return events


def extract_eventbrite_embed(soup, base_url, source_name):
    """Extract from Eventbrite embeds."""
    events = []

    for container in soup.select('[class*="eventbrite"], [data-eventbrite], .eb-event'):
        title_el = container.select_one('.eb-event-title, .event-title, h3, h2')
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        link_el = container.select_one('a[href*="eventbrite.com"]')
        link = link_el.get('href', '') if link_el else ''

        date_el = container.select_one('.eb-event-date, .event-date, time')
        date_str = date_el.get_text(strip=True) if date_el else ''

        events.append({
            'title': title,
            'date': date_str,
            'source_url': link,
            'source': source_name,
        })

    return events


def extract_schema_org(soup, base_url, source_name):
    """Extract from Schema.org JSON-LD structured data."""
    events = []

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string)

            # Handle both single objects and arrays
            items = data if isinstance(data, list) else [data]

            for item in items:
                if item.get('@type') in ['Event', 'MusicEvent', 'SocialEvent']:
                    events.append({
                        'title': item.get('name', ''),
                        'date': item.get('startDate', ''),
                        'end_date': item.get('endDate', ''),
                        'venue': item.get('location', {}).get('name', '') if isinstance(item.get('location'), dict) else '',
                        'description': item.get('description', '')[:200] if item.get('description') else '',
                        'source_url': item.get('url', ''),
                        'image_url': item.get('image', ''),
                        'source': source_name,
                    })
        except (json.JSONDecodeError, TypeError):
            continue

    return events


def extract_ical_links(soup, base_url, source_name):
    """Extract events from iCal/ICS links if present."""
    # Just note the presence of calendar feeds for now
    events = []
    for link in soup.select('a[href*=".ics"], a[href*="ical"], a[href*="webcal"]'):
        # Could fetch and parse ICS in future
        pass
    return events


# ============================================================================
# EVENTCALENDARAPP API EXTRACTOR (Direct JSON - No Scraping!)
# ============================================================================

# Known EventCalendarApp venues with their calendar IDs
# Add venues here as we discover them via browser DevTools Network tab
KNOWN_EVENTCALENDARAPP_VENUES = {
    # Guthrie Green complex (includes Fly Loft, LowDown)
    'guthriegreen.com': {'id': '11692', 'widgetUuid': 'dcafff1d-f2a8-4799-9a6b-a5ad3e3a6ff2'},
    'www.guthriegreen.com': {'id': '11692', 'widgetUuid': 'dcafff1d-f2a8-4799-9a6b-a5ad3e3a6ff2'},
    # The Colony Tulsa - TODO: Need to discover calendar ID via DevTools
    # 'thecolonytulsa.com': {'id': 'XXXXX', 'widgetUuid': 'XXXXX'},
    # Starlite Bar - Uses WordPress Events Calendar, not EventCalendarApp
    # Add more venues as discovered...
}


def detect_eventcalendarapp(html: str, url: str = '') -> dict | None:
    """
    Detect EventCalendarApp widget and extract API parameters.
    Returns dict with 'id' and 'widgetUuid' if found, else None.

    Used by: Guthrie Green, Fly Loft, LowDown, and many other venues.
    """
    # First check known venues by domain
    if url:
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            if domain in KNOWN_EVENTCALENDARAPP_VENUES:
                print(f"[EventCalendarApp] Known venue: {domain}")
                return KNOWN_EVENTCALENDARAPP_VENUES[domain]
        except:
            pass

    # Pattern 1: Script embed with id and widgetUuid
    # <script ... src="https://eventcalendarapp.com/widgets/...?id=11692&widgetUuid=dcafff1d-...">
    script_pattern = re.compile(
        r'eventcalendarapp\.com[^"\']*[?&]id=(\d+)[^"\']*widgetUuid=([a-f0-9-]+)',
        re.IGNORECASE
    )
    match = script_pattern.search(html)
    if match:
        return {'id': match.group(1), 'widgetUuid': match.group(2)}

    # Pattern 2: Reversed order (widgetUuid before id)
    script_pattern2 = re.compile(
        r'eventcalendarapp\.com[^"\']*widgetUuid=([a-f0-9-]+)[^"\']*[?&]id=(\d+)',
        re.IGNORECASE
    )
    match = script_pattern2.search(html)
    if match:
        return {'id': match.group(2), 'widgetUuid': match.group(1)}

    # Pattern 3: Look for API calls in inline scripts
    api_pattern = re.compile(
        r'api\.eventcalendarapp\.com/events\?id=(\d+)[^"\']*widgetUuid=([a-f0-9-]+)',
        re.IGNORECASE
    )
    match = api_pattern.search(html)
    if match:
        return {'id': match.group(1), 'widgetUuid': match.group(2)}

    # Pattern 4: Just look for the calendar ID in any eventcalendarapp reference
    id_only = re.compile(r'eventcalendarapp\.com[^"\']*[?&]id=(\d+)', re.IGNORECASE)
    match = id_only.search(html)
    if match:
        # Try to find widgetUuid separately
        uuid_pattern = re.compile(r'widgetUuid[=:]["\']?([a-f0-9-]{36})', re.IGNORECASE)
        uuid_match = uuid_pattern.search(html)
        if uuid_match:
            return {'id': match.group(1), 'widgetUuid': uuid_match.group(1)}
        # Return with just ID - API might work without UUID
        return {'id': match.group(1), 'widgetUuid': None}

    return None


async def fetch_eventcalendarapp_api(calendar_id: str, widget_uuid: str = None, max_pages: int = 50) -> list:
    """
    Fetch all events from EventCalendarApp API with pagination.

    API: GET https://api.eventcalendarapp.com/events?id={id}&page={page}&widgetUuid={uuid}

    Returns list of raw event dicts from API.
    """
    all_events = []
    page = 1

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        while page <= max_pages:
            # Build API URL
            url = f"https://api.eventcalendarapp.com/events?id={calendar_id}&page={page}"
            if widget_uuid:
                url += f"&widgetUuid={widget_uuid}"

            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                # Extract events from response
                events = data.get('events', [])
                if not events:
                    break

                all_events.extend(events)

                # Check pagination
                pages = data.get('pages', {})
                total_pages = pages.get('total', 1)

                if page >= total_pages:
                    break

                page += 1

            except Exception as e:
                print(f"EventCalendarApp API error page {page}: {e}")
                break

    return all_events


def parse_eventcalendarapp_events(raw_events: list, source_name: str, future_only: bool = True) -> list:
    """
    Convert raw EventCalendarApp API events to our standardized format.

    Args:
        raw_events: List of raw event dicts from API
        source_name: Name of the source/venue
        future_only: If True, only return events with start date >= today

    API fields:
    - summary: Event title
    - timezoneStart: ISO datetime (local) e.g. "2026-10-25T19:00:00"
    - timezoneEnd: ISO datetime (local)
    - location.description: Venue name
    - description / shortDescription: Event details (HTML)
    - thumbnail / image: CDN image URLs
    - ticketsLink: External ticket URL or null
    - url: EventCalendarApp event page URL
    - ticketTypes: Array of ticket options
    - featured: Boolean
    - timezone: e.g. "US/Central"
    """
    events = []
    seen = set()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for raw in raw_events:
        title = raw.get('summary', '').strip()
        if not title or title in seen:
            continue
        seen.add(title)

        # Parse date/time
        start = raw.get('timezoneStart', '')
        end = raw.get('timezoneEnd', '')

        # Filter past events if future_only is True
        if future_only and start:
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '').split('+')[0])
                if start_dt < today:
                    continue
            except:
                pass  # Keep event if we can't parse the date

        # Format nicely: "Oct 25, 2026 @ 7:00 PM - 10:00 PM"
        date_str = ''
        if start:
            try:
                dt = datetime.fromisoformat(start.replace('Z', '').split('+')[0])
                date_str = dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')

                if end:
                    end_dt = datetime.fromisoformat(end.replace('Z', '').split('+')[0])
                    # Only show end time if same day
                    if dt.date() == end_dt.date():
                        date_str += f" - {end_dt.strftime('%I:%M %p').lstrip('0')}"
            except:
                date_str = start

        # Get venue from location
        location = raw.get('location', {})
        venue = location.get('description', '') if isinstance(location, dict) else ''
        if not venue:
            venue = source_name

        # Get description (strip HTML)
        desc = raw.get('shortDescription', '') or raw.get('description', '')
        if desc:
            # Simple HTML strip
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()[:200]

        # Get image
        image = raw.get('image', '') or raw.get('thumbnail', '')

        # Get ticket link
        tickets = raw.get('ticketsLink', '')

        # Get event URL
        event_url = raw.get('url', '')

        events.append({
            'title': title,
            'date': date_str,
            'end_date': end,
            'venue': venue,
            'description': desc,
            'source_url': event_url,
            'tickets_url': tickets,
            'image_url': image,
            'source': source_name,
            'featured': raw.get('featured', False),
        })

    return events


async def extract_eventcalendarapp(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Main EventCalendarApp extraction function.

    Args:
        html: Page HTML content
        source_name: Name of the source/venue
        url: Page URL (used for known venue lookup)
        future_only: If True, only return events with start date >= today

    Returns: (events_list, was_detected)
    - events_list: List of events if found
    - was_detected: True if EventCalendarApp widget was detected (even if no events)
    """
    params = detect_eventcalendarapp(html, url)
    if not params:
        return [], False

    print(f"[EventCalendarApp] Detected calendar ID: {params['id']}")

    # Fetch from API
    raw_events = await fetch_eventcalendarapp_api(
        params['id'],
        params.get('widgetUuid')
    )

    print(f"[EventCalendarApp] Fetched {len(raw_events)} total events from API")

    # Parse to our format (with optional date filtering)
    events = parse_eventcalendarapp_events(raw_events, source_name, future_only)

    if future_only:
        print(f"[EventCalendarApp] {len(events)} upcoming events after date filter")

    return events, True


# ============================================================================
# TIMELY API EXTRACTOR (Direct JSON - No Scraping!)
# ============================================================================

# Known Timely venues with their calendar IDs
# Discover via DevTools: events.timely.fun/api/calendars/{ID}/events
KNOWN_TIMELY_VENUES = {
    'thestarlitebar.com': {'id': '54755961'},
    'www.thestarlitebar.com': {'id': '54755961'},
    # Add more venues as discovered...
}


def detect_timely(html: str, url: str = '') -> dict | None:
    """
    Detect Timely calendar widget and extract calendar ID.
    Returns dict with 'id' if found, else None.
    """
    # First check known venues by domain
    if url:
        try:
            domain = urlparse(url).netloc.lower()
            if domain in KNOWN_TIMELY_VENUES:
                print(f"[Timely] Known venue: {domain}")
                return KNOWN_TIMELY_VENUES[domain]
        except:
            pass

    # Pattern 1: Look for timely embed script or iframe
    # <script src="https://events.timely.fun/embed.js" data-calendar-id="54755961">
    id_pattern = re.compile(r'data-calendar-id[=:]["\']?(\d+)', re.IGNORECASE)
    match = id_pattern.search(html)
    if match:
        return {'id': match.group(1)}

    # Pattern 2: Look for timely.fun URL with calendar ID
    url_pattern = re.compile(r'events\.timely\.fun/(?:api/calendars/)?(\d+)', re.IGNORECASE)
    match = url_pattern.search(html)
    if match:
        return {'id': match.group(1)}

    # Pattern 3: Look for timelyapp references
    timely_pattern = re.compile(r'timelyapp\.time\.ly/[^/]*/calendars/(\d+)', re.IGNORECASE)
    match = timely_pattern.search(html)
    if match:
        return {'id': match.group(1)}

    return None


async def fetch_timely_api(calendar_id: str, referer_url: str = '', max_pages: int = 10) -> list:
    """
    Fetch all events from Timely API with pagination.

    API: GET https://events.timely.fun/api/calendars/{id}/events?group_by_date=1&timezone=America/Chicago&view=agenda&start_date_utc={timestamp}&per_page=30&page={page}

    Returns list of raw event dicts from API.
    """
    import time
    all_events = []
    page = 1

    # Start from today
    start_timestamp = int(time.time())

    # Timely API requires Referer header from the embedding site
    headers = dict(HEADERS)
    if referer_url:
        headers['Referer'] = referer_url
        headers['Origin'] = referer_url.rstrip('/')

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        while page <= max_pages:
            url = (
                f"https://events.timely.fun/api/calendars/{calendar_id}/events"
                f"?group_by_date=1&timezone=America%2FChicago&view=agenda"
                f"&start_date_utc={start_timestamp}&per_page=30&page={page}"
            )

            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                # Timely returns {data: {items: [{date: ..., events: [...]}]}}
                items = data.get('data', {}).get('items', [])
                if not items:
                    break

                # Extract events from grouped structure
                for item in items:
                    events_in_group = item.get('events', [])
                    all_events.extend(events_in_group)

                # Check if there are more pages
                total = data.get('data', {}).get('total', 0)
                if len(all_events) >= total or not items:
                    break

                page += 1

            except Exception as e:
                print(f"Timely API error page {page}: {e}")
                break

    return all_events


def parse_timely_events(raw_events: list, source_name: str, future_only: bool = True) -> list:
    """
    Convert raw Timely API events to our standardized format.

    Timely API fields (typical):
    - title: Event title
    - start_datetime: ISO datetime
    - end_datetime: ISO datetime
    - description: Event details (may be HTML)
    - url: Event page URL
    - featured_image: Image URL
    - venue: {name: ..., address: ...}
    - taxonomies: {category: [...], tag: [...]}
    """
    events = []
    seen = set()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for raw in raw_events:
        title = raw.get('title', '').strip()
        if not title or title in seen:
            continue
        seen.add(title)

        # Parse date/time
        start = raw.get('start_datetime', '')
        end = raw.get('end_datetime', '')

        # Filter past events if future_only is True
        if future_only and start:
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '').split('+')[0])
                if start_dt < today:
                    continue
            except:
                pass

        # Format nicely
        date_str = ''
        if start:
            try:
                dt = datetime.fromisoformat(start.replace('Z', '').split('+')[0])
                date_str = dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')

                if end:
                    end_dt = datetime.fromisoformat(end.replace('Z', '').split('+')[0])
                    if dt.date() == end_dt.date():
                        date_str += f" - {end_dt.strftime('%I:%M %p').lstrip('0')}"
            except:
                date_str = start

        # Get venue
        venue_data = raw.get('venue', {})
        venue = venue_data.get('name', '') if isinstance(venue_data, dict) else ''
        if not venue:
            venue = source_name

        # Get description (strip HTML)
        desc = raw.get('description', '') or raw.get('excerpt', '')
        if desc:
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()[:200]

        # Get image
        image = raw.get('featured_image', {})
        image_url = image.get('url', '') if isinstance(image, dict) else (image if isinstance(image, str) else '')

        # Get event URL
        event_url = raw.get('url', '') or raw.get('canonical_url', '')

        # Get ticket link
        tickets = raw.get('ticket_url', '') or raw.get('custom_ticket_url', '')

        events.append({
            'title': title,
            'date': date_str,
            'end_date': end,
            'venue': venue,
            'description': desc,
            'source_url': event_url,
            'tickets_url': tickets,
            'image_url': image_url,
            'source': source_name,
        })

    return events


async def extract_timely(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Main Timely extraction function.

    Returns: (events_list, was_detected)
    """
    params = detect_timely(html, url)
    if not params:
        return [], False

    print(f"[Timely] Detected calendar ID: {params['id']}")

    # Try API first
    raw_events = await fetch_timely_api(params['id'], referer_url=url)

    if raw_events:
        print(f"[Timely] Fetched {len(raw_events)} total events from API")
        events = parse_timely_events(raw_events, source_name, future_only)
        if future_only:
            print(f"[Timely] {len(events)} upcoming events after date filter")
        return events, True

    # API failed - try HTML extraction
    print(f"[Timely] API returned 0 events, trying HTML extraction...")
    soup = BeautifulSoup(html, 'html.parser')
    events = extract_timely_from_html(soup, url, source_name)
    print(f"[Timely] Found {len(events)} events from HTML")

    return events, True


def clean_timely_title(title: str) -> str:
    """
    Clean up Timely titles that have concatenated tags.

    Example: "Starlite Trivia NightTriviatriviatrivia nighttrivianighttriviapub quiz..."
    Should become: "Starlite Trivia Night"

    Pattern: Title text followed by tags concatenated without spaces
    """
    if not title or len(title) < 20:
        return title

    # Look for the pattern where a word is followed by itself (lowercase) or similar
    # "NightTrivia" or "PartyThe" - capital letter in middle of what should be a word

    # Find position where lowercase is immediately followed by uppercase (tag boundary)
    # Pattern: lowercase letter followed by uppercase letter (except normal cases like "McDonald")
    # This often indicates where the title ends and tags begin
    matches = list(re.finditer(r'[a-z][A-Z]', title))

    if matches:
        # Take the first occurrence as potential title end
        first_match = matches[0]
        potential_title = title[:first_match.start() + 1]

        # Verify it's reasonable (at least 3 words or 15 chars)
        if len(potential_title) >= 10 or potential_title.count(' ') >= 2:
            return potential_title.strip()

    # Alternative: look for repeated words
    words = title.split()
    if len(words) >= 2:
        # Check if any word appears multiple times (indicates tag repetition)
        seen_words = {}
        for i, word in enumerate(words):
            word_lower = word.lower()
            if word_lower in seen_words and i > 1:
                # Found a repeat - title probably ends before first occurrence
                return ' '.join(words[:seen_words[word_lower]]).strip()
            seen_words[word_lower] = i

    # If title is very long with few spaces, it's probably polluted
    if len(title) > 50 and title.count(' ') < 5:
        # Try to find a reasonable stopping point
        # Look for common patterns like "- " which often end the main title
        if ' - ' in title:
            parts = title.split(' - ')
            if len(parts[0]) >= 10:
                return parts[0].strip()

        # Just take first ~50 chars up to a word boundary
        if len(title) > 50:
            truncated = title[:50]
            last_space = truncated.rfind(' ')
            if last_space > 20:
                return truncated[:last_space].strip()

    return title


def extract_timely_from_html(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Timely widget's rendered HTML structure.
    Fallback when API access is blocked.

    Timely renders events with structure like:
    - .timely-event or [data-event-id]
    - Event title in heading
    - Date/time in various formats
    """
    events = []
    seen = set()

    # Timely event selectors
    selectors = [
        '.timely-event',
        '[data-event-id]',
        '.timely-calendar .event',
        '.tc-event',
        # Agenda view items
        '.timely-agenda-event',
        '.agenda-event',
    ]

    containers = []
    for sel in selectors:
        containers.extend(soup.select(sel))

    # Also look for the agenda structure
    if not containers:
        # Look for date groups with events
        date_groups = soup.select('[class*="agenda"], [class*="event-list"]')
        for group in date_groups:
            # Find individual event items
            items = group.select('a[href*="event"], div[class*="event"], li')
            containers.extend(items)

    for container in containers:
        # Get title - look for specific title element first
        title_el = (
                container.select_one('.timely-title, .event-title, [class*="title"]:not([class*="subtitle"])') or
                container.select_one('h1, h2, h3, h4')
        )

        if not title_el:
            # Try first link text
            link_el = container.select_one('a[href]')
            if link_el:
                title_el = link_el

        if not title_el:
            continue

        # Get just the direct text, not nested tag text
        title = ''
        for child in title_el.children:
            if isinstance(child, str):
                title += child.strip()
            elif hasattr(child, 'name') and child.name in ['span', 'strong', 'b', 'em']:
                # Only include certain inline elements
                if not child.get('class') or not any('tag' in c.lower() for c in child.get('class', [])):
                    title += child.get_text(strip=True)

        # Fallback to full text if empty
        if not title:
            title = title_el.get_text(strip=True)

        # Clean up duplicated text (Timely sometimes doubles the title)
        if len(title) > 10:
            half = len(title) // 2
            first_half = title[:half]
            second_half = title[half:half + len(first_half)]
            if first_half == second_half:
                title = first_half

        if not title or len(title) < 3 or title in seen:
            continue

        # Skip navigation/UI elements
        skip_words = ['read full', 'more', 'view all', 'click here', 'get a timely', 'powered by', 'buy tickets']
        if any(skip in title.lower() for skip in skip_words):
            continue

        # Skip if title looks like a tag dump (too many words without spaces in original)
        if len(title) > 50 and title.count(' ') < 3:
            continue

        # Clean up tag pollution from Timely
        title = clean_timely_title(title)

        if not title or len(title) < 3:
            continue

        seen.add(title)

        # Get date/time - look for specific date element
        date_el = container.select_one('.timely-date, .event-date, time, [class*="date"]:not([class*="update"])')
        date_str = ''
        if date_el:
            # Get datetime attribute first
            date_str = date_el.get('datetime', '')
            if not date_str:
                # Get text but clean it
                date_text = date_el.get_text(strip=True)
                # Extract just the date/time part
                date_match = extract_date_from_text(date_text)
                time_match = extract_time_from_text(date_text)
                if date_match:
                    date_str = date_match
                    if time_match:
                        date_str = f"{date_match} @ {time_match}"
                elif time_match:
                    date_str = time_match

        if not date_str:
            # Look for date in container text more carefully
            container_text = container.get_text(' ', strip=True)
            date_str = extract_date_from_text(container_text) or ''
            time_str = extract_time_from_text(container_text)
            if time_str:
                date_str = f"{date_str} @ {time_str}" if date_str else time_str

        # Get link
        link = ''
        link_el = container if container.name == 'a' else container.select_one('a[href]')
        if link_el:
            href = link_el.get('href', '')
            if href and not href.startswith('#') and 'javascript:' not in href:
                link = urljoin(base_url, href)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': link,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# BOK CENTER API EXTRACTOR
# ============================================================================

KNOWN_BOK_VENUES = {
    'bokcenter.com': True,
    'www.bokcenter.com': True,
}


# ============================================================================
# STUBWIRE / SHRINE EXTRACTOR
# ============================================================================

def extract_stubwire_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Stubwire-powered sites like Tulsa Shrine.

    Structure:
    - Day number in standalone element
    - Month abbreviation
    - h2 > a with title linking to /event/{id}/{slug}/
    - Time like "8:00PM"
    - Stubwire ticket links
    """
    events = []
    seen = set()

    # Find all event links to /event/ pages
    event_links = soup.select('a[href*="/event/"]')

    for link in event_links:
        href = link.get('href', '')
        title = link.get_text(strip=True)

        # Skip non-title links (Buy Tickets, More Info, images)
        if not title or len(title) < 2:
            continue
        if title.lower() in ['buy tickets', 'more info', 'all session tickets']:
            continue
        if '/event/' not in href:
            continue

        # Deduplicate by URL
        if href in seen:
            continue
        seen.add(href)

        # Find the parent container to get date/time
        container = link.find_parent(['div', 'article', 'li'])
        date_str = ''
        time_str = ''

        if container:
            # Look for the full text which should have day, month, time
            container_text = container.get_text(' ', strip=True)

            # Extract month and day - look for patterns like "06 Feb" or "Feb 06"
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            for month in months:
                if month in container_text:
                    # Try to find day number near the month
                    month_idx = container_text.find(month)

                    # Look for day before month (like "06 Feb")
                    before = container_text[:month_idx].strip()
                    day_match = re.search(r'(\d{1,2})\s*$', before)
                    if day_match:
                        date_str = f"{month} {day_match.group(1)}"
                        break

                    # Look for day after month (like "Feb 06")
                    after = container_text[month_idx + len(month):].strip()
                    day_match = re.search(r'^[\s,]*(\d{1,2})', after)
                    if day_match:
                        date_str = f"{month} {day_match.group(1)}"
                        break

            # Extract time - look for patterns like "7:00PM", "8:00 PM"
            time_match = re.search(r'(\d{1,2}:\d{2}\s*[APap][Mm])', container_text)
            if time_match:
                time_str = time_match.group(1)

        # Combine date and time
        full_date = date_str
        if time_str:
            full_date = f"{date_str} @ {time_str}" if date_str else time_str

        # Build full URL
        full_url = href if href.startswith('http') else urljoin(base_url, href)

        # Get image if available
        image_url = ''
        if container:
            img = container.select_one('img[src*="stubwire"]')
            if img:
                image_url = img.get('src', '')

        # Get ticket URL
        ticket_url = ''
        if container:
            ticket_link = container.select_one('a[href*="stubwire.com"]')
            if ticket_link:
                ticket_url = ticket_link.get('href', '')

        events.append({
            'title': title,
            'date': full_date,
            'source_url': full_url,
            'tickets_url': ticket_url,
            'image_url': image_url,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# DICE.FM EXTRACTOR
# ============================================================================

def extract_dice_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Dice.fm embeds or pages.
    Dice uses data attributes and specific class patterns.
    """
    events = []
    seen = set()

    # Look for Dice event links
    dice_links = soup.select('a[href*="dice.fm"], a[href*="link.dice.fm"]')

    for link in dice_links:
        href = link.get('href', '')
        if href in seen:
            continue
        seen.add(href)

        # Get title from link text or nearby heading
        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            parent = link.find_parent(['div', 'article'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"]')
                if heading:
                    title = heading.get_text(strip=True)

        if not title or title.lower() in ['buy tickets', 'get tickets', 'book now']:
            continue

        # Look for date in parent container
        date_str = ''
        parent = link.find_parent(['div', 'article', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"], [datetime]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# BANDSINTOWN EXTRACTOR
# ============================================================================

def extract_bandsintown_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Bandsintown embeds or widgets.
    Only captures actual event links (containing /e/ in the URL path).
    Filters out navigation elements, genre filters, and UI chrome.
    """
    events = []
    seen = set()

    # Only match actual event detail links (they contain /e/ in the path)
    # This filters out nav links like /today/, /all-dates/genre/, etc.
    bit_links = soup.select('a[href*="bandsintown.com/e/"]')

    for link in bit_links:
        href = link.get('href', '')
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Clean up BIT titles that concatenate artist + venue + date
        # Pattern: "Artist NameVenue NameFeb 14 - 9:00 PM"
        # Look for date pattern and truncate there
        date_match = re.search(
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{1,2}',
            title
        )
        event_date = ''
        if date_match:
            # Extract date portion
            date_portion = title[date_match.start():]
            event_date = date_portion.strip()
            # Title is everything before the date
            title = title[:date_match.start()].strip()

        if not title:
            continue

        # Get date from parent if we didn't extract one
        if not event_date:
            parent = link.find_parent(['div', 'li', 'tr'])
            if parent:
                date_el = parent.select_one('time, [class*="date"]')
                if date_el:
                    event_date = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': event_date,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# SONGKICK EXTRACTOR
# ============================================================================

def extract_songkick_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Songkick embeds or widgets.
    """
    events = []
    seen = set()

    # Look for Songkick links
    sk_links = soup.select('a[href*="songkick.com"]')

    # Also look for Songkick widget
    sk_widgets = soup.select('[class*="songkick"], #songkick-widget')

    for link in sk_links:
        href = link.get('href', '')
        if '/concerts/' not in href and '/events/' not in href:
            continue
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        date_str = ''
        parent = link.find_parent(['div', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# TICKETMASTER EXTRACTOR
# ============================================================================

def extract_ticketmaster_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Ticketmaster links/embeds on venue pages.
    """
    events = []
    seen = set()

    # Look for Ticketmaster links
    tm_links = soup.select('a[href*="ticketmaster.com"], a[href*="livenation.com"]')

    for link in tm_links:
        href = link.get('href', '')
        # Only event pages, not artist pages or homepage
        if '/event/' not in href and '/venue/' not in href:
            continue
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)

        # Try to get better title from parent
        if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets', 'buy now']:
            parent = link.find_parent(['div', 'article', 'li'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"], [class*="name"]')
                if heading:
                    title = heading.get_text(strip=True)

        if not title or len(title) < 3:
            continue

        date_str = ''
        parent = link.find_parent(['div', 'article', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"], [datetime]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# AXS EXTRACTOR
# ============================================================================

def extract_axs_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from AXS links/embeds.
    """
    events = []
    seen = set()

    axs_links = soup.select('a[href*="axs.com"]')

    for link in axs_links:
        href = link.get('href', '')
        if '/events/' not in href:
            continue
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets']:
            parent = link.find_parent(['div', 'article', 'li'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"]')
                if heading:
                    title = heading.get_text(strip=True)

        if not title or len(title) < 3:
            continue

        date_str = ''
        parent = link.find_parent(['div', 'article', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# ETIX EXTRACTOR
# ============================================================================

def extract_etix_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Etix links/embeds OR from Etix venue pages directly.
    Also parses captured API responses if available.
    """
    events = []
    seen = set()

    # Check if we're ON an Etix page (venue page)
    is_etix_page = 'etix.com' in base_url

    # FIRST: Try to parse captured API data (most reliable)
    api_scripts = soup.select('script[type="etix-api-data"]')
    for script in api_scripts:
        try:
            api_data = json.loads(script.get_text())
            print(f"[Etix] Parsing API data with {len(api_data) if isinstance(api_data, list) else 'object'} items")

            # API returns array of performances/events
            if isinstance(api_data, list):
                for item in api_data:
                    perf = item.get('performance', item)  # Sometimes nested

                    title = perf.get('name', '') or perf.get('title', '') or perf.get('performanceName', '')
                    if not title:
                        continue

                    # Get date/time
                    date_str = perf.get('performanceDate', '') or perf.get('date', '') or perf.get('startDate', '')
                    time_str = perf.get('performanceTime', '') or perf.get('time', '') or perf.get('startTime', '')
                    if date_str and time_str:
                        date_str = f"{date_str} {time_str}"

                    # Get URL
                    perf_id = perf.get('performanceID', '') or perf.get('id', '')
                    event_url = f"https://www.etix.com/ticket/p/{perf_id}" if perf_id else base_url

                    # Get image
                    image_url = perf.get('imageUrl', '') or perf.get('image', '') or perf.get('performanceImage', '')

                    # Get venue
                    venue = perf.get('venueName', '') or perf.get('venue', '') or source_name

                    if event_url not in seen:
                        seen.add(event_url)
                        events.append({
                            'title': title,
                            'date': date_str,
                            'source_url': event_url,
                            'tickets_url': event_url,
                            'source': source_name,
                            'venue': venue,
                            'image_url': image_url,
                        })

            # Or might be object with results array
            elif isinstance(api_data, dict):
                results = api_data.get('results', []) or api_data.get('performances', []) or api_data.get('events', [])
                for perf in results:
                    title = perf.get('name', '') or perf.get('title', '') or perf.get('performanceName', '')
                    if not title:
                        continue

                    date_str = perf.get('performanceDate', '') or perf.get('date', '') or perf.get('startDate', '')
                    time_str = perf.get('performanceTime', '') or perf.get('time', '') or perf.get('startTime', '')
                    if date_str and time_str:
                        date_str = f"{date_str} {time_str}"

                    perf_id = perf.get('performanceID', '') or perf.get('id', '')
                    event_url = f"https://www.etix.com/ticket/p/{perf_id}" if perf_id else base_url

                    image_url = perf.get('imageUrl', '') or perf.get('image', '')
                    venue = perf.get('venueName', '') or perf.get('venue', '') or source_name

                    if event_url not in seen:
                        seen.add(event_url)
                        events.append({
                            'title': title,
                            'date': date_str,
                            'source_url': event_url,
                            'tickets_url': event_url,
                            'source': source_name,
                            'venue': venue,
                            'image_url': image_url,
                        })
        except Exception as e:
            print(f"[Etix] Error parsing API data: {e}")

    # If we got events from API, return them
    if events:
        print(f"[Etix] Extracted {len(events)} events from API data")
        return events

    if is_etix_page:
        # Extract from Etix's rendered React content
        # Look for event cards - they use MUI components

        # Try various selectors for Etix event cards
        event_cards = soup.select('[class*="MuiCard"], [class*="performance"], [class*="event-card"], [class*="EventCard"]')

        # Also look for links to /ticket/p/ (performance pages)
        perf_links = soup.select('a[href*="/ticket/p/"]')

        for link in perf_links:
            href = link.get('href', '')
            if href in seen:
                continue
            seen.add(href)

            # Make absolute URL
            if href.startswith('/'):
                href = 'https://www.etix.com' + href

            # Get title from link or nearby heading
            title = link.get_text(strip=True)
            if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets', 'buy', 'tickets']:
                # Look for title in parent card
                parent = link.find_parent(['div', 'article', 'li', 'section'])
                if parent:
                    heading = parent.select_one('h1, h2, h3, h4, h5, [class*="title"], [class*="Title"], [class*="name"], [class*="Name"]')
                    if heading:
                        title = heading.get_text(strip=True)

            if not title or len(title) < 3:
                continue

            # Get date
            date_str = ''
            parent = link.find_parent(['div', 'article', 'li', 'section'])
            if parent:
                date_el = parent.select_one('time, [class*="date"], [class*="Date"], [class*="time"], [class*="Time"]')
                if date_el:
                    date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

            # Get image
            image_url = ''
            if parent:
                img = parent.select_one('img')
                if img:
                    image_url = img.get('src', '')

            events.append({
                'title': title,
                'date': date_str,
                'source_url': href,
                'tickets_url': href,
                'source': source_name,
                'venue': source_name,
                'image_url': image_url,
            })

        # Also try to extract from any visible text patterns if no links found
        if not events:
            # Look for any divs with event-like structure
            all_divs = soup.select('div')
            for div in all_divs:
                text = div.get_text(separator=' ', strip=True)
                # Look for patterns like "Artist Name Feb 15, 2026 8:00 PM"
                if len(text) > 10 and len(text) < 200:
                    # Check for date-like patterns
                    if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d', text):
                        # Find any ticket link in this div
                        ticket_link = div.select_one('a[href*="ticket"]')
                        if ticket_link:
                            href = ticket_link.get('href', '')
                            if href.startswith('/'):
                                href = 'https://www.etix.com' + href

                            if href not in seen:
                                seen.add(href)
                                events.append({
                                    'title': text[:100],  # Use text as title
                                    'date': '',
                                    'source_url': href,
                                    'tickets_url': href,
                                    'source': source_name,
                                    'venue': source_name,
                                })

    # Also check for links TO etix (for non-Etix pages embedding Etix links)
    etix_links = soup.select('a[href*="etix.com"]')

    for link in etix_links:
        href = link.get('href', '')
        if '/ticket/' not in href and '/event/' not in href:
            continue
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets']:
            parent = link.find_parent(['div', 'article', 'li'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"]')
                if heading:
                    title = heading.get_text(strip=True)

        if not title or len(title) < 3:
            continue

        date_str = ''
        parent = link.find_parent(['div', 'article', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# SEE TICKETS EXTRACTOR
# ============================================================================

def extract_seetickets_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from See Tickets links/embeds.
    """
    events = []
    seen = set()

    st_links = soup.select('a[href*="seetickets.us"], a[href*="seetickets.com"]')

    for link in st_links:
        href = link.get('href', '')
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets']:
            parent = link.find_parent(['div', 'article', 'li'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"]')
                if heading:
                    title = heading.get_text(strip=True)

        if not title or len(title) < 3:
            continue

        date_str = ''
        parent = link.find_parent(['div', 'article', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': href,
            'tickets_url': href,
            'source': source_name,
            'venue': source_name,
        })

    return events


# ============================================================================
# EVENTBRITE EXTRACTOR (Enhanced)
# ============================================================================


async def fetch_bok_center_events(max_pages: int = 20) -> list:
    """
    Fetch all events from BOK Center's AJAX API.

    API: GET https://www.bokcenter.com/events/events_ajax/{offset}?category=0&venue=0&team=0&exclude=&per_page=6

    Returns parsed events.
    """
    all_events = []
    offset = 0
    per_page = 6

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        while offset < max_pages * per_page:
            url = f"https://www.bokcenter.com/events/events_ajax/{offset}?category=0&venue=0&team=0&exclude=&per_page={per_page}&came_from_page=event-list-page"

            try:
                resp = await client.get(url)
                resp.raise_for_status()

                # API returns HTML wrapped in a JSON string - decode it
                raw_text = resp.text

                try:
                    html = json.loads(raw_text)
                except Exception as je:
                    html = raw_text  # Fallback if not JSON-encoded

                if not html or len(html.strip()) < 50:
                    break

                # Parse the HTML fragment
                soup = BeautifulSoup(html, 'html.parser')

                # Find all h3 elements (event titles)
                titles = soup.select('h3 a')

                if not titles:
                    # Try alternate selectors
                    titles = soup.select('a[href*="/events/detail/"]')

                if not titles:
                    break

                for title_link in titles:
                    title = title_link.get_text(strip=True)
                    href = title_link.get('href', '')

                    if not title or not href or '/events/detail/' not in href:
                        continue

                    # Find the parent event container
                    # Walk up until we find a div that contains the date
                    container = title_link.parent
                    date_str = ''

                    for _ in range(8):
                        if container is None:
                            break

                        # Look for spans with date content
                        spans = container.find_all('span', recursive=True)
                        span_texts = [s.get_text(strip=True) for s in spans]

                        # Check if we have month names
                        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                        if any(month in ' '.join(span_texts) for month in months):
                            # Join span texts to form date
                            date_str = ' '.join(span_texts)
                            # Clean up
                            date_str = re.sub(r'\s+', ' ', date_str).strip()
                            break

                        container = container.parent

                    # Build full URL
                    full_url = href if href.startswith('http') else f"https://www.bokcenter.com{href}"

                    all_events.append({
                        'title': title,
                        'date': date_str,
                        'source_url': full_url,
                    })

                offset += per_page

            except Exception as e:
                print(f"BOK Center API error at offset {offset}: {e}")
                break

    return all_events


async def extract_bok_center(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from BOK Center.

    Returns: (events_list, was_detected)
    """
    # Check if this is BOK Center
    try:
        domain = urlparse(url).netloc.lower()
        if domain not in KNOWN_BOK_VENUES:
            return [], False
    except:
        return [], False

    print(f"[BOK Center] Detected BOK Center site")

    # Fetch from AJAX API
    raw_events = await fetch_bok_center_events()

    print(f"[BOK Center] Fetched {len(raw_events)} events from API")

    # Deduplicate by URL and clean up
    seen = set()
    events = []
    for event in raw_events:
        url_key = event.get('source_url', '')
        if url_key in seen:
            continue
        seen.add(url_key)

        # Clean up duplicated dates
        date_str = event.get('date', '')
        if date_str:
            # Dates are duplicated like "Thu,Feb5, 2026 Thu, Feb 5 , 2026"
            # or "Mar6 Mar 6 - 7, 2026 7 , 2026"

            # First, normalize spacing
            date_str = re.sub(r'\s+', ' ', date_str).strip()

            # Strategy: Find first year (4 digits) and cut there
            year_match = re.search(r'\d{4}', date_str)
            if year_match:
                date_str = date_str[:year_match.end()]

            # Now clean up the remaining duplicates
            # If a day name appears twice, take the second (cleaner) version
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            for day in days:
                if date_str.count(day) >= 2:
                    # Find second occurrence and take from there
                    first_idx = date_str.find(day)
                    second_idx = date_str.find(day, first_idx + 1)
                    if second_idx > first_idx:
                        date_str = date_str[second_idx:]
                    break

            # If a month appears twice, take the second (cleaner) version
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'June', 'July']
            for month in months:
                if date_str.count(month) >= 2:
                    first_idx = date_str.find(month)
                    second_idx = date_str.find(month, first_idx + 1)
                    if second_idx > first_idx:
                        date_str = date_str[second_idx:]
                    break

            # Final cleanup
            date_str = re.sub(r',(\S)', r', \1', date_str)  # Space after comma
            date_str = re.sub(r'([A-Za-z])(\d)', r'\1 \2', date_str)  # Space between letter and number
            date_str = re.sub(r'\s+', ' ', date_str).strip()

            # Remove "On Sale Soon" etc.
            date_str = re.sub(r'\s*On Sale.*$', '', date_str, flags=re.IGNORECASE)

            event['date'] = date_str.strip()

        event['source'] = source_name
        event['venue'] = 'BOK Center'
        events.append(event)

    return events, True


# ============================================================================
# EXPO SQUARE (SAFFIRE CMS) API EXTRACTOR
# ============================================================================

async def extract_expo_square_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Expo Square using their Saffire CMS API.

    API workflow:
    1. GetEventDays - returns all dates with events
    2. GetEventDaysByList - returns event details for given dates

    Returns: (events_list, was_detected)
    """
    # Check if this is an Expo Square URL
    if 'exposquare.com' not in url.lower():
        return [], False

    print(f"[Expo Square] Detected Expo Square URL, using Saffire API...")

    events = []
    seen_event_ids = set()  # Deduplicate multi-day events

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/json; charset=utf-8',
                'Origin': 'https://www.exposquare.com',
                'Referer': 'https://www.exposquare.com/events',
                'X-Requested-With': 'XMLHttpRequest',
            }

            # Step 1: Get all event dates
            days_url = 'https://www.exposquare.com/services/eventsservice.asmx/GetEventDays'
            days_payload = {
                'day': '',
                'startDate': '',
                'endDate': '',
                'categoryID': 0,
                'currentUserItems': 'false',
                'tagID': 0,
                'keywords': '%25%25',
                'isFeatured': 'false',
                'fanPicks': 'false',
                'myPicks': 'false',
                'pastEvents': 'false',
                'allEvents': 'false',
                'memberEvents': 'false',
                'memberOnly': 'false',
                'showCategoryExceptionID': 0,
                'isolatedSchedule': 0,
                'customFieldFilters': [],
                'searchInDescription': True
            }

            print(f"[Expo Square] Fetching event dates...")
            days_response = await client.post(days_url, json=days_payload, headers=headers)

            if days_response.status_code != 200:
                print(f"[Expo Square] GetEventDays failed: {days_response.status_code}")
                return [], False

            days_data = days_response.json()
            all_dates = days_data.get('d', [])

            # Filter to only future dates (next 12 months)
            from datetime import datetime, timedelta
            today = datetime.now()
            max_date = today + timedelta(days=365)

            future_dates = []
            for date_str in all_dates:
                try:
                    dt = datetime.strptime(date_str, '%m/%d/%Y')
                    if today <= dt <= max_date:
                        future_dates.append(date_str)
                except:
                    continue

            print(f"[Expo Square] Found {len(future_dates)} future event dates (from {len(all_dates)} total)")

            # Step 2: Fetch events in batches of 30 dates
            batch_size = 30
            details_url = 'https://www.exposquare.com/services/eventsservice.asmx/GetEventDaysByList'

            for i in range(0, len(future_dates), batch_size):
                batch = future_dates[i:i+batch_size]
                dates_str = ','.join(batch)

                details_payload = {
                    'dates': dates_str,
                    'day': '',
                    'categoryID': 0,
                    'tagID': 0,
                    'keywords': '%25%25',
                    'isFeatured': 'false',
                    'fanPicks': 'false',
                    'pastEvents': 'false',
                    'allEvents': 'false',
                    'memberEvents': 'false',
                    'memberOnly': 'false',
                    'showCategoryExceptionID': 0,
                    'isolatedSchedule': 0,
                    'customFieldFilters': [],
                    'searchInDescription': True
                }

                details_response = await client.post(details_url, json=details_payload, headers=headers)

                if details_response.status_code != 200:
                    print(f"[Expo Square] GetEventDaysByList failed for batch {i//batch_size + 1}")
                    continue

                details_data = details_response.json()
                days = details_data.get('d', {}).get('Days', [])

                for day in days:
                    # Events are in Times[0].Unique or directly in Unique
                    unique_events = day.get('Unique', [])
                    if not unique_events:
                        times = day.get('Times', [])
                        if times:
                            unique_events = times[0].get('Unique', [])

                    for evt in unique_events:
                        try:
                            event_id = evt.get('EventID')
                            if event_id in seen_event_ids:
                                continue  # Skip duplicate (multi-day event)
                            seen_event_ids.add(event_id)

                            title = evt.get('Name', '')
                            if not title:
                                continue

                            # Parse date range (e.g., "Feb 13 - Feb 15, 2026")
                            date_range = evt.get('EventDateRangeString', '')
                            date_str = day.get('DateString', '')  # e.g., "02/13/2026"

                            # Try to extract end date from range
                            end_date_str = None
                            if date_range and '-' in date_range:
                                # Parse "Feb 13 - Feb 15, 2026" format
                                try:
                                    parts = date_range.split('-')
                                    if len(parts) == 2:
                                        end_part = parts[1].strip()
                                        # Parse the end date
                                        from dateutil import parser as date_parser
                                        end_date_str = str(date_parser.parse(end_part, fuzzy=True).date())
                                except:
                                    pass

                            # Get detail URL - this is the actual event page
                            detail_url = evt.get('DetailURL', '')

                            # Get image
                            image_url = evt.get('ImageOrVideoThumbnailWithPath', '')
                            if 'no_img_available' in image_url:
                                image_url = ''

                            # Get description
                            description = evt.get('ShortDescription', '') or evt.get('LongDescription', '') or ''
                            if not description and date_range:
                                description = date_range

                            # Get location/venue
                            locations = evt.get('Locations', [])
                            venue = 'Expo Square'
                            if locations and isinstance(locations, list) and len(locations) > 0:
                                loc = locations[0]
                                if isinstance(loc, dict):
                                    venue = loc.get('Name', 'Expo Square') or 'Expo Square'

                            # Get categories from CategoryMaps
                            categories = []
                            cat_maps = evt.get('CategoryMaps', [])
                            if cat_maps and isinstance(cat_maps, list):
                                for cat in cat_maps:
                                    if isinstance(cat, dict):
                                        cat_name = cat.get('CategoryName', '')
                                        if cat_name:
                                            categories.append(cat_name)

                            event = {
                                'title': title,
                                'start_time': date_str,
                                'end_time': end_date_str,
                                'venue': venue,
                                'venue_address': '4145 E 21st St, Tulsa, OK 74114',
                                'location': 'Tulsa',
                                'description': description[:500] if description else '',
                                'source_url': detail_url,  # Actual event page
                                'image_url': image_url,
                                'source_name': source_name or 'Expo Square',
                                'categories': categories if categories else [],
                                'outdoor': False,
                                'family_friendly': False,
                            }

                            events.append(event)

                        except Exception as e:
                            print(f"[Expo Square] Error parsing event: {e}")
                            continue

                # Small delay between batches
                await asyncio.sleep(0.2)

            print(f"[Expo Square] Successfully extracted {len(events)} unique events")
            return events, True

    except Exception as e:
        print(f"[Expo Square] Error: {e}")
        import traceback
        traceback.print_exc()
        return [], False


# ============================================================================
# EVENTBRITE API EXTRACTOR
# ============================================================================

# Known Eventbrite place IDs
EVENTBRITE_PLACES = {
    'tulsa': '101714291',
    'oklahoma-city': '101714211',
    'broken-arrow': '101712989',
}

async def extract_eventbrite_api_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Eventbrite using their internal API.
    Works for any Eventbrite search/destination page.

    Returns: (events_list, was_detected)
    """
    # Check if this is an Eventbrite URL
    if 'eventbrite.com' not in url.lower():
        return [], False

    print(f"[Eventbrite API] Detected Eventbrite URL, using API...")

    # Determine place ID from URL or default to Tulsa
    place_id = EVENTBRITE_PLACES['tulsa']  # Default
    url_lower = url.lower()
    for city, pid in EVENTBRITE_PLACES.items():
        if city in url_lower:
            place_id = pid
            break

    events = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # First, get cookies by visiting the main page
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Referer': 'https://www.eventbrite.com/',
                'Origin': 'https://www.eventbrite.com',
            }

            # Call the search API
            api_url = 'https://www.eventbrite.com/home/api/search/'
            payload = {
                'placeId': place_id,
                'tab': 'all'
            }

            print(f"[Eventbrite API] Fetching events for place ID {place_id}...")
            response = await client.post(api_url, json=payload, headers=headers)

            if response.status_code != 200:
                print(f"[Eventbrite API] API returned status {response.status_code}")
                return [], False

            data = response.json()
            raw_events = data.get('events', [])
            print(f"[Eventbrite API] Got {len(raw_events)} events")

            for evt in raw_events:
                try:
                    # Extract basic info
                    title = evt.get('name', '')
                    if not title:
                        continue

                    # Build start datetime
                    start_date = evt.get('start_date', '')
                    start_time = evt.get('start_time', '00:00:00')
                    if start_date:
                        date_str = f"{start_date}T{start_time}"
                    else:
                        date_str = ''

                    # Get venue info
                    venue_data = evt.get('primary_venue', {}) or {}
                    venue_name = venue_data.get('name', 'TBA')

                    address_data = venue_data.get('address', {}) or {}
                    venue_address = ''
                    if address_data:
                        parts = []
                        if address_data.get('address_1'):
                            parts.append(address_data['address_1'])
                        if address_data.get('city'):
                            parts.append(address_data['city'])
                        if address_data.get('region'):
                            parts.append(address_data['region'])
                        if address_data.get('postal_code'):
                            parts.append(address_data['postal_code'])
                        venue_address = ', '.join(parts)

                    # Get pricing
                    ticket_info = evt.get('ticket_availability', {}) or {}
                    is_free = ticket_info.get('is_free', False)

                    price_min = None
                    price_max = None
                    if is_free:
                        price_min = 0
                        price_max = 0
                    else:
                        min_price = ticket_info.get('minimum_ticket_price', {})
                        max_price = ticket_info.get('maximum_ticket_price', {})
                        if min_price:
                            try:
                                price_min = float(min_price.get('major_value', 0))
                            except (ValueError, TypeError):
                                pass
                        if max_price:
                            try:
                                price_max = float(max_price.get('major_value', 0))
                            except (ValueError, TypeError):
                                pass

                    # Get image
                    image_data = evt.get('image', {}) or {}
                    image_url = image_data.get('url', '')

                    # Get event URL - this is the actual event detail page
                    event_url = evt.get('url', '')
                    if not event_url:
                        event_id = evt.get('id', '')
                        if event_id:
                            event_url = f"https://www.eventbrite.com/e/{event_id}"

                    # Get description/summary
                    description = evt.get('summary', '') or ''

                    # Check if online event
                    is_online = evt.get('is_online_event', False)
                    if is_online:
                        venue_name = 'Online Event'

                    # Get end time
                    end_date = evt.get('end_date', '')
                    end_time = evt.get('end_time', '')
                    end_datetime = ''
                    if end_date:
                        end_datetime = f"{end_date}T{end_time}" if end_time else end_date

                    # Get city/location from address
                    city = address_data.get('city', 'Tulsa') if address_data else 'Tulsa'

                    event = {
                        'title': title,
                        'start_time': date_str,  # Use start_time instead of date
                        'end_time': end_datetime if end_datetime else None,
                        'venue': venue_name,
                        'venue_address': venue_address,
                        'location': city,  # City/area
                        'description': description[:500] if description else '',
                        'source_url': event_url,  # Actual event page URL
                        'image_url': image_url,
                        'price_min': price_min,
                        'price_max': price_max,
                        'is_free': is_free,
                        'source_name': source_name or 'Eventbrite',
                        'categories': [],
                        'outdoor': False,  # Could be inferred later
                        'family_friendly': False,  # Could be inferred later
                    }

                    events.append(event)

                except Exception as e:
                    print(f"[Eventbrite API] Error parsing event: {e}")
                    continue

            print(f"[Eventbrite API] Successfully extracted {len(events)} events")
            return events, True

    except Exception as e:
        print(f"[Eventbrite API] Error: {e}")
        return [], False


# ============================================================================
# VISITTULSA / SIMPLEVIEW CMS EXTRACTOR
# ============================================================================

# Known Simpleview CMS sites
KNOWN_SIMPLEVIEW_SITES = {
    'www.visittulsa.com': 'Visit Tulsa',
    'visittulsa.com': 'Visit Tulsa',
}


async def extract_simpleview_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from Simpleview CMS sites (like VisitTulsa.com).
    Uses their REST API to fetch all events with pagination.

    Returns: (events_list, was_detected)
    """
    # Check if this is a Simpleview site
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain not in KNOWN_SIMPLEVIEW_SITES:
            # Also check HTML for Simpleview markers
            if 'simpleview' not in html.lower() and 'plugins_events' not in html.lower():
                return [], False
    except:
        return [], False

    print(f"[Simpleview] Detected Simpleview CMS site: {domain}")

    base_url = f"{parsed.scheme}://{parsed.netloc}"

    try:
        events = await fetch_simpleview_events(base_url, source_name, future_only)
        return events, True
    except Exception as e:
        print(f"[Simpleview] Error fetching events: {e}")
        return [], True  # Detected but failed


async def fetch_simpleview_events(base_url: str, source_name: str, future_only: bool = True) -> list:
    """
    Fetch all events from Simpleview CMS API with pagination.
    """
    import urllib.parse
    from datetime import datetime, timedelta, timezone

    events = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        # Step 1: Get authentication token
        token_url = f"{base_url}/plugins/core/get_simple_token/"
        print(f"[Simpleview] Fetching token from {token_url}")

        try:
            token_resp = await client.get(token_url)
            token = token_resp.text.strip()
            if not token or len(token) > 100:  # Token should be a short hash
                print(f"[Simpleview] Invalid token received")
                return []
            print(f"[Simpleview] Got token: {token[:20]}...")
        except Exception as e:
            print(f"[Simpleview] Failed to get token: {e}")
            return []

        # Step 2: Build query
        # Date range - from today to 1 year ahead (or all time if not future_only)
        now = datetime.now(timezone.utc)
        if future_only:
            start_date = now.strftime("%Y-%m-%dT06:00:00.000Z")
        else:
            start_date = "2020-01-01T06:00:00.000Z"
        end_date = (now + timedelta(days=365)).strftime("%Y-%m-%dT06:00:00.000Z")

        # Query with all categories (empty filter = all events)
        batch_size = 100
        skip = 0
        total_fetched = 0

        while True:
            query = {
                "filter": {
                    "active": True,
                    "date_range": {
                        "start": {"$date": start_date},
                        "end": {"$date": end_date}
                    }
                },
                "options": {
                    "limit": batch_size,
                    "skip": skip,
                    "count": True,
                    "castDocs": False,
                    "fields": {
                        "_id": 1, "location": 1, "date": 1, "startDate": 1, "endDate": 1,
                        "recurrence": 1, "recurType": 1, "latitude": 1, "longitude": 1,
                        "media_raw": 1, "recid": 1, "title": 1, "url": 1, "description": 1,
                        "categories": 1, "listing.primary_category": 1, "listing.title": 1,
                        "listing.url": 1, "address": 1, "location": 1
                    },
                    "hooks": [],
                    "sort": {"date": 1, "rank": 1, "title_sort": 1}
                }
            }

            json_str = json.dumps(query)
            api_url = f"{base_url}/includes/rest_v2/plugins_events_events_by_date/find/?json={urllib.parse.quote(json_str)}&token={token}"

            print(f"[Simpleview] Fetching events (skip={skip})...")

            try:
                resp = await client.get(api_url)
                data = resp.json()
                print(f"[Simpleview] Raw response (first 500 chars): {str(data)[:500]}")
            except Exception as e:
                print(f"[Simpleview] API request failed: {e}")
                break

            # Debug: print response structure
            print(f"[Simpleview] Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")

            # Parse response - handle different response formats
            docs = []
            total_count = 0

            if isinstance(data, dict):
                # Check for nested structure: {'docs': {'count': N, 'docs': [...]}}
                if 'docs' in data and isinstance(data['docs'], dict):
                    inner = data['docs']
                    docs = inner.get('docs', [])
                    total_count = inner.get('count', 0)
                    print(f"[Simpleview] Found nested structure with {total_count} total events")
                else:
                    # Flat structure: {'docs': [...], 'count': N}
                    docs = data.get('docs', [])
                    total_count = data.get('count', 0)

                # Some responses have data nested differently
                if not docs and 'results' in data:
                    docs = data.get('results', [])
                if not docs and 'items' in data:
                    docs = data.get('items', [])
            elif isinstance(data, list):
                docs = data
                total_count = len(data)

            if not docs:
                print(f"[Simpleview] No more events")
                break

            print(f"[Simpleview] Got {len(docs)} events (total available: {total_count})")

            # Debug first doc structure - print ALL keys and look for URL fields
            if docs and len(docs) > 0:
                first_doc = docs[0]
                print(f"[Simpleview] First doc type: {type(first_doc)}")
                if isinstance(first_doc, dict):
                    print(f"[Simpleview] First doc keys: {list(first_doc.keys())}")
                    # Debug: print any field that might contain a URL
                    for key in first_doc.keys():
                        val = first_doc.get(key)
                        if isinstance(val, str) and ('http' in val or 'url' in key.lower() or 'link' in key.lower() or 'ticket' in key.lower() or 'web' in key.lower()):
                            print(f"[Simpleview] URL field '{key}': {val[:200]}")
                        elif isinstance(val, dict):
                            print(f"[Simpleview] Dict field '{key}' keys: {list(val.keys())}")
                else:
                    print(f"[Simpleview] First doc value: {str(first_doc)[:200]}")

            # Transform to our format
            for i, doc in enumerate(docs):
                try:
                    # Skip if doc is not a dict
                    if not isinstance(doc, dict):
                        print(f"[Simpleview] Skipping non-dict doc {i}: {type(doc)} = {str(doc)[:50]}")
                        continue

                    title = doc.get('title', '')
                    if not title:
                        continue

                    # Get date
                    date_str = ''
                    if doc.get('startDate'):
                        # Parse ISO date
                        try:
                            start_dt = doc['startDate']
                            if isinstance(start_dt, dict) and '$date' in start_dt:
                                start_dt = start_dt['$date']
                            date_str = start_dt
                        except:
                            date_str = doc.get('date', '')
                    else:
                        date_str = doc.get('date', '')

                    # Get URL - prioritize external ticket URL over listing page
                    event_url = ''

                    # First, look for external/ticket URLs (the actual event page, not VisitTulsa)
                    external_url = (
                            doc.get('ticketUrl') or
                            doc.get('ticket_url') or
                            doc.get('externalUrl') or
                            doc.get('external_url') or
                            doc.get('registrationUrl') or
                            doc.get('registration_url') or
                            doc.get('eventUrl') or
                            doc.get('event_url') or
                            doc.get('websiteUrl') or
                            doc.get('website_url') or
                            doc.get('link') or
                            ''
                    )

                    # Check listing object for external URL
                    listing = doc.get('listing')
                    if not external_url and listing and isinstance(listing, dict):
                        external_url = (
                                listing.get('ticketUrl') or
                                listing.get('externalUrl') or
                                listing.get('websiteUrl') or
                                listing.get('website') or
                                listing.get('web') or
                                ''
                        )

                    # Use external URL if found, otherwise fall back to listing page
                    if external_url:
                        event_url = external_url
                        if not event_url.startswith('http'):
                            if event_url.startswith('www.'):
                                event_url = 'https://' + event_url
                            elif '.' in event_url:
                                event_url = 'https://' + event_url
                    else:
                        # Fall back to VisitTulsa event page
                        event_url = doc.get('url', '')
                        if event_url and not event_url.startswith('http'):
                            event_url = base_url + event_url

                    # Get venue/location - prioritize 'location' field (has actual venue name)
                    venue = ''
                    loc = doc.get('location', '')
                    if loc and isinstance(loc, str):
                        venue = loc
                    if not venue:
                        listing = doc.get('listing')
                        if listing and isinstance(listing, dict):
                            venue = listing.get('title', '')

                    # Get image
                    image_url = ''
                    media_raw = doc.get('media_raw')
                    if media_raw and isinstance(media_raw, list) and len(media_raw) > 0:
                        media = media_raw[0]
                        if isinstance(media, dict):
                            image_url = media.get('mediaurl', '') or media.get('url', '')
                        elif isinstance(media, str):
                            image_url = media

                    # Get description
                    description = doc.get('description', '')
                    if isinstance(description, str):
                        # Strip HTML
                        description = re.sub(r'<[^>]+>', '', description)[:500]
                    else:
                        description = ''

                    # Get categories
                    categories = []
                    cats = doc.get('categories')
                    if cats and isinstance(cats, list):
                        for cat in cats:
                            if isinstance(cat, dict):
                                cat_name = cat.get('catName', '')
                                if cat_name:
                                    categories.append(cat_name)
                            elif isinstance(cat, str):
                                categories.append(cat)

                    # Get address
                    address = doc.get('address', '')
                    if not isinstance(address, str):
                        address = ''

                    # Get coordinates
                    lat = doc.get('latitude')
                    lng = doc.get('longitude')
                    location = f"{lat},{lng}" if lat and lng else None

                    # Get venue website directly from listing object in API response
                    venue_website = ''
                    listing = doc.get('listing')
                    if listing and isinstance(listing, dict):
                        # Debug: print listing keys on first event to see what's available
                        if i == 0:
                            print(f"[Simpleview] Listing object keys: {list(listing.keys())}")

                        # Try common website field names
                        venue_website = (
                                listing.get('website') or
                                listing.get('websiteUrl') or
                                listing.get('web') or
                                listing.get('url_website') or
                                listing.get('externalUrl') or
                                ''
                        )

                        # If website found, ensure it's a full URL
                        if venue_website and not venue_website.startswith('http'):
                            if venue_website.startswith('www.'):
                                venue_website = 'https://' + venue_website
                            elif '.' in venue_website:
                                venue_website = 'https://' + venue_website

                    events.append({
                        'title': title,
                        'start_time': date_str,  # Use start_time
                        'end_time': doc.get('endDate'),  # Capture end date if available
                        'source_url': event_url or f"{base_url}/events/",  # Actual event page
                        'source_name': source_name,
                        'venue': venue or source_name,
                        'venue_address': address,
                        'location': 'Tulsa',  # Default location
                        'description': description,
                        'image_url': image_url,
                        'categories': categories if categories else [],
                        'outdoor': False,
                        'family_friendly': False,
                        '_venue_website': venue_website,  # Website from API listing object
                    })
                except Exception as doc_err:
                    print(f"[Simpleview] Error processing doc {i}: {doc_err}")
                    continue

            total_fetched += len(docs)
            skip += batch_size

            # Stop if we've got all events (or no count provided and fewer docs than batch)
            if total_count > 0 and total_fetched >= total_count:
                print(f"[Simpleview] Reached total count ({total_count})")
                break
            if len(docs) < batch_size:
                print(f"[Simpleview] Got fewer docs ({len(docs)}) than batch size ({batch_size}), stopping")
                break

            # Be nice to the server
            await asyncio.sleep(0.3)

        print(f"[Simpleview] Total events fetched: {len(events)}")

    return events


# ============================================================================
# GENERIC SMART EXTRACTION
# ============================================================================

def extract_by_date_proximity(soup, base_url, source_name):
    """
    Find events by looking for date patterns and grabbing nearby title-like text.
    This is the fallback for unknown formats.
    """
    events = []
    seen_titles = set()

    # Get all text nodes that contain dates
    body = soup.find('body') or soup

    # Find all elements that contain date-like text
    date_elements = []
    for element in body.find_all(text=True):
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text and text_has_date(text):
                date_elements.append(element.parent)

    for date_el in date_elements:
        # Look for the event container - walk up to find a reasonable parent
        container = date_el
        for _ in range(5):  # Walk up max 5 levels
            parent = container.parent
            if not parent or parent.name in ['body', 'html', 'main', 'section']:
                break
            container = parent
            # Stop if container has multiple date-containing children (we went too far up)
            date_count = len([c for c in container.find_all(text=True) if text_has_date(str(c))])
            if date_count > 3:
                container = date_el.parent
                break

        # Extract title - look for headings or prominent text near the date
        title = ''
        title_el = (
                container.select_one('h1, h2, h3, h4, h5, h6') or
                container.select_one('a[href]') or
                container.select_one('[class*="title"]') or
                container.select_one('strong, b')
        )

        if title_el:
            title = title_el.get_text(strip=True)

        # If no title element, look for the most prominent text
        if not title:
            texts = [t.strip() for t in container.stripped_strings]
            # Filter out date/time strings to find the title
            for t in texts:
                if len(t) > 5 and not text_has_date(t) and not COMBINED_TIME_PATTERN.search(t):
                    title = t[:100]
                    break

        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        # Extract date
        container_text = container.get_text(' ', strip=True)
        date_str = extract_date_from_text(container_text) or ''
        time_str = extract_time_from_text(container_text)
        if time_str:
            date_str = f"{date_str} @ {time_str}" if date_str else time_str

        # Extract link
        link = ''
        link_el = container.select_one('a[href]')
        if link_el:
            href = link_el.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                link = urljoin(base_url, href)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': link,
            'source': source_name,
        })

    return events


def extract_repeating_structures(soup, base_url, source_name):
    """
    Find events by detecting repeating HTML structures (lists of similar items).
    """
    events = []
    seen = set()

    # Common list containers
    list_selectors = [
        'ul > li',
        'ol > li',
        '.events-list > div',
        '.events-list > article',
        '.event-list > div',
        '.event-list > article',
        '[class*="list"] > [class*="item"]',
        '[class*="events"] > [class*="event"]',
        '[class*="calendar"] > div',
        '.row > .col',
        'table tbody tr',
    ]

    for selector in list_selectors:
        items = soup.select(selector)

        # Need at least 2 similar items to be a list
        if len(items) < 2:
            continue

        # Check if these items have consistent structure (likely a repeating pattern)
        first_classes = set(items[0].get('class', []))
        similar_count = sum(1 for item in items if set(item.get('class', [])) == first_classes)

        if similar_count < len(items) * 0.5:  # At least 50% should be similar
            continue

        for item in items:
            # Must contain a date to be considered an event
            item_text = item.get_text(' ', strip=True)
            if not text_has_date(item_text):
                continue

            # Get title
            title_el = item.select_one('h1, h2, h3, h4, h5, h6, a[href], [class*="title"], strong')
            title = title_el.get_text(strip=True) if title_el else ''

            if not title:
                # Use first substantial text that isn't a date
                for text in item.stripped_strings:
                    if len(text) > 5 and not text_has_date(text):
                        title = text[:100]
                        break

            if not title or title in seen:
                continue
            seen.add(title)

            # Get date
            date_str = extract_date_from_text(item_text) or ''
            time_str = extract_time_from_text(item_text)
            if time_str:
                date_str = f"{date_str} @ {time_str}" if date_str else time_str

            # Get link
            link = ''
            link_el = item.select_one('a[href]')
            if link_el:
                href = link_el.get('href', '')
                if href and not href.startswith('#'):
                    link = urljoin(base_url, href)

            events.append({
                'title': title,
                'date': date_str,
                'source_url': link,
                'source': source_name,
            })

    return events


# ============================================================================
# MASTER EXTRACTION FUNCTION
# ============================================================================

def extract_events_universal(html: str, base_url: str, source_name: str) -> list:
    """
    Universal event extraction - tries multiple strategies.
    Returns the best results found.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script/style/nav/footer noise (but keep iframes - we capture their content)
    for tag in soup.select('script, style, nav, footer, header, noscript'):
        tag.decompose()

    all_events = []
    methods_used = []

    # PRIORITY: If on Etix domain, try Etix extractor first
    if 'etix.com' in base_url:
        etix_events = extract_etix_events(soup, base_url, source_name)
        if etix_events:
            all_events.extend(etix_events)
            methods_used.append(f"Etix ({len(etix_events)})")
            # Return early if we found events on Etix
            if all_events:
                for e in all_events:
                    e['_extraction_methods'] = methods_used
                return all_events

    # Strategy 1: Schema.org structured data (most reliable if present)
    schema_events = extract_schema_org(soup, base_url, source_name)
    if schema_events:
        all_events.extend(schema_events)
        methods_used.append(f"Schema.org ({len(schema_events)})")

    # Strategy 2: Known plugin patterns
    tribe_events = extract_tribe_events(soup, base_url, source_name)
    if tribe_events:
        all_events.extend(tribe_events)
        methods_used.append(f"WordPress Events Calendar ({len(tribe_events)})")

    eventbrite_events = extract_eventbrite_embed(soup, base_url, source_name)
    if eventbrite_events:
        all_events.extend(eventbrite_events)
        methods_used.append(f"Eventbrite ({len(eventbrite_events)})")

    # Stubwire-powered sites (Tulsa Shrine, etc.)
    stubwire_events = extract_stubwire_events(soup, base_url, source_name)
    if stubwire_events:
        all_events.extend(stubwire_events)
        methods_used.append(f"Stubwire ({len(stubwire_events)})")

    # Dice.fm
    dice_events = extract_dice_events(soup, base_url, source_name)
    if dice_events:
        all_events.extend(dice_events)
        methods_used.append(f"Dice.fm ({len(dice_events)})")

    # Bandsintown
    bit_events = extract_bandsintown_events(soup, base_url, source_name)
    if bit_events:
        all_events.extend(bit_events)
        methods_used.append(f"Bandsintown ({len(bit_events)})")

    # Songkick
    sk_events = extract_songkick_events(soup, base_url, source_name)
    if sk_events:
        all_events.extend(sk_events)
        methods_used.append(f"Songkick ({len(sk_events)})")

    # Ticketmaster
    tm_events = extract_ticketmaster_events(soup, base_url, source_name)
    if tm_events:
        all_events.extend(tm_events)
        methods_used.append(f"Ticketmaster ({len(tm_events)})")

    # AXS
    axs_events = extract_axs_events(soup, base_url, source_name)
    if axs_events:
        all_events.extend(axs_events)
        methods_used.append(f"AXS ({len(axs_events)})")

    # Etix
    etix_events = extract_etix_events(soup, base_url, source_name)
    if etix_events:
        all_events.extend(etix_events)
        methods_used.append(f"Etix ({len(etix_events)})")

    # See Tickets
    st_events = extract_seetickets_events(soup, base_url, source_name)
    if st_events:
        all_events.extend(st_events)
        methods_used.append(f"See Tickets ({len(st_events)})")

    # Strategy 3: Timely widget HTML (for when API fails)
    if not all_events:
        timely_html_events = extract_timely_from_html(soup, base_url, source_name)
        if timely_html_events:
            all_events.extend(timely_html_events)
            methods_used.append(f"Timely HTML ({len(timely_html_events)})")

    # Strategy 4: Repeating structures
    if not all_events:
        repeat_events = extract_repeating_structures(soup, base_url, source_name)
        if repeat_events:
            all_events.extend(repeat_events)
            methods_used.append(f"Repeating structures ({len(repeat_events)})")

    # Strategy 5: Date proximity (fallback)
    if not all_events:
        proximity_events = extract_by_date_proximity(soup, base_url, source_name)
        if proximity_events:
            all_events.extend(proximity_events)
            methods_used.append(f"Date proximity ({len(proximity_events)})")

    # Deduplicate by title
    seen_titles = set()
    unique_events = []
    for event in all_events:
        title = event.get('title', '').lower().strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_events.append(event)

    # Add extraction metadata
    for event in unique_events:
        event['_extraction_methods'] = methods_used

    return unique_events


# ============================================================================
# SCRAPING FUNCTIONS
# ============================================================================

async def fetch_with_httpx(url: str) -> str:
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def fetch_with_playwright(url: str) -> str:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers(HEADERS)

        # Etix is a heavy React SPA - needs special handling
        is_etix = 'etix.com' in url
        etix_api_data = []

        if is_etix:
            # Intercept API responses to capture event data
            async def capture_response(response):
                if '/api/online/search' in response.url or '/api/online/venues/' in response.url:
                    try:
                        body = await response.text()
                        etix_api_data.append(body)
                        print(f"[Etix] Captured API response from {response.url[:60]}...")
                    except:
                        pass

            page.on('response', capture_response)

            # For Etix, use networkidle and wait longer
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except:
                await page.goto(url, timeout=45000)

            # Wait for Etix event cards to appear
            try:
                await page.wait_for_selector('[class*="performance"], [class*="event-card"], [class*="MuiCard"]', timeout=10000)
            except:
                pass

            # Extra wait for API calls to complete
            await page.wait_for_timeout(5000)

            # Scroll down to trigger lazy loading
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(2000)
        else:
            # Use domcontentloaded instead of networkidle (faster, more reliable)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except:
                # Fallback if even that times out
                await page.goto(url, timeout=30000)

            # Wait for dynamic content to load
            await page.wait_for_timeout(3000)

            # Try to wait for common event containers
            try:
                await page.wait_for_selector('[class*="event"], [class*="calendar"], [class*="timely"]', timeout=5000)
            except:
                pass  # Continue anyway

        # Get main page content
        html = await page.content()

        # If we captured Etix API data, append it as a special section
        if etix_api_data:
            html += "\n<!-- ETIX_API_DATA -->\n"
            for data in etix_api_data:
                html += f"<script type='etix-api-data'>{data}</script>\n"
            print(f"[Etix] Appended {len(etix_api_data)} API responses to HTML")

        # Also try to get iframe content (Timely and other widgets often use iframes)
        try:
            frames = page.frames
            for frame in frames:
                if frame != page.main_frame:
                    try:
                        frame_content = await frame.content()
                        # Append iframe content wrapped in a marker
                        html += f"\n<!-- IFRAME_CONTENT -->\n{frame_content}"
                    except:
                        pass
        except:
            pass

        await browser.close()
    return html


# ============================================================================
# HTML TEMPLATE
# ============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Locate918 Scraper</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 30px 20px;
            color: #fff;
        }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { text-align: center; color: #D4AF37; margin-bottom: 5px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 25px; font-size: 13px; }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
        }
        .form-row { display: flex; gap: 12px; margin-bottom: 12px; }
        .form-row .form-group { flex: 1; }
        label { display: block; margin-bottom: 5px; color: #D4AF37; font-size: 12px; font-weight: 600; }
        input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 14px;
        }
        input:focus { outline: none; border-color: #D4AF37; }
        .checkbox-row { display: flex; align-items: center; gap: 8px; margin: 12px 0; }
        .checkbox-row input { width: 16px; height: 16px; }
        .checkbox-row label { margin: 0; color: #aaa; font-size: 13px; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
        }
        .btn-primary { background: #D4AF37; color: #1a1a2e; }
        .btn-primary:hover { background: #e5c04b; }
        .btn-primary:disabled { background: #555; }
        .btn-secondary { background: #444; color: #fff; }
        .btn-success { background: #28a745; color: #fff; }
        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }
        .status {
            padding: 10px 12px; border-radius: 6px; margin-top: 12px; font-size: 13px;
        }
        .status.loading { background: rgba(212,175,55,0.2); border: 1px solid #D4AF37; }
        .status.success { background: rgba(40,167,69,0.2); border: 1px solid #28a745; }
        .status.error { background: rgba(220,53,69,0.2); border: 1px solid #dc3545; }
        .spinner {
            display: inline-block; width: 14px; height: 14px;
            border: 2px solid rgba(255,255,255,0.3); border-radius: 50%;
            border-top-color: #D4AF37; animation: spin 0.7s linear infinite;
            margin-right: 8px; vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .hidden { display: none; }
        .log {
            background: #0a0a0a; border-radius: 5px; padding: 10px;
            margin-top: 10px; max-height: 150px; overflow-y: auto;
            font-family: monospace; font-size: 11px; color: #0f0;
        }
        .log-error { color: #f66; }
        .log-success { color: #6f6; }
        .log-info { color: #6cf; }
        h3 { color: #D4AF37; font-size: 15px; margin-bottom: 10px; }
        .stats { display: flex; gap: 20px; margin: 12px 0; }
        .stat { text-align: center; }
        .stat-val { font-size: 22px; font-weight: bold; color: #D4AF37; }
        .stat-lbl { font-size: 10px; color: #666; text-transform: uppercase; }
        .method-tag {
            display: inline-block;
            background: #444;
            color: #aaa;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            margin-right: 5px;
            margin-bottom: 8px;
        }
        .event-list { max-height: 400px; overflow-y: auto; }
        .event-item {
            background: rgba(0,0,0,0.25); border-radius: 6px;
            padding: 10px; margin-bottom: 6px; font-size: 13px;
        }
        .event-item strong { color: #fff; }
        .event-item p { color: #888; margin: 3px 0; font-size: 12px; }
        .event-item a { color: #6cf; font-size: 11px; }
        .footer { text-align: center; color: #333; margin-top: 25px; font-size: 11px; }
    </style>
</head>
<body>
<div class="container">
    <h1>🎯 Locate918 Scraper</h1>
    <p class="subtitle">Universal Extraction — No LLM Required</p>
    
    <div class="card">
        <div class="form-row">
            <div class="form-group" style="flex:2;">
                <label>URL</label>
                <input type="url" id="url" placeholder="https://www.cainsballroom.com/events/" />
            </div>
            <div class="form-group">
                <label>Source Name</label>
                <input type="text" id="source" placeholder="Cain's Ballroom" />
            </div>
        </div>
        
        <div class="checkbox-row">
            <input type="checkbox" id="playwright" checked />
            <label for="playwright">Use Playwright (for JavaScript sites)</label>
        </div>
        
        <div class="checkbox-row">
            <input type="checkbox" id="future-only" checked />
            <label for="future-only">Future events only (filter out past dates)</label>
        </div>
        
        <div class="btn-group">
            <button class="btn btn-primary" id="scrape-btn" onclick="scrape()">🔍 Scrape</button>
            <button class="btn btn-secondary" onclick="saveCurrentUrl()">📌 Save URL</button>
        </div>
        
        <div id="status" class="status hidden"></div>
        <div id="log-box" class="log hidden"></div>
        
        <div id="saved-urls" style="margin-top:15px;"></div>
    </div>
    
    <div id="results" class="card hidden">
        <h3>📋 Extracted Events</h3>
        <div class="stats">
            <div class="stat"><div class="stat-val" id="stat-count">0</div><div class="stat-lbl">Events</div></div>
            <div class="stat"><div class="stat-val" id="stat-html">0</div><div class="stat-lbl">HTML Size</div></div>
        </div>
        <div id="methods-used"></div>
        <div class="event-list" id="event-list"></div>
        <div class="btn-group" style="margin-top:12px;">
            <button class="btn btn-success" onclick="saveToDb()">💾 Save to Database</button>
        </div>
    </div>
    
    <!-- Venue Manager Section -->
    <div class="card" id="venue-manager">
        <h3>🏛️ Venue Manager</h3>
        <p style="color:#666;font-size:12px;margin-bottom:15px;">
            Fill in missing venue data. Generate SQL for Supabase.
        </p>
        
        <div class="btn-group" style="margin-bottom:15px;">
            <button class="btn btn-secondary" onclick="loadIncompleteVenues()">📋 Load Incomplete</button>
            <button class="btn btn-secondary" onclick="toggleManualEntry()">✏️ Manual Entry</button>
            <button class="btn btn-secondary" onclick="toggleSQLOutput()">📄 View SQL</button>
        </div>
        
        <div id="venue-stats" class="hidden" style="margin-bottom:15px;padding:10px;background:rgba(0,0,0,0.2);border-radius:6px;">
            <span style="color:#D4AF37;font-weight:bold;" id="venue-count">0</span> total venues, 
            <span style="color:#dc3545;font-weight:bold;" id="incomplete-count">0</span> need data
        </div>
        
        <!-- Incomplete venues list -->
        <div id="incomplete-venues" class="hidden" style="max-height:250px;overflow-y:auto;margin-bottom:15px;"></div>
        
        <!-- Manual entry form -->
        <div id="manual-entry" class="hidden" style="background:rgba(0,0,0,0.2);padding:15px;border-radius:8px;margin-bottom:15px;">
            <div class="form-row">
                <div class="form-group">
                    <label>Venue Name *</label>
                    <input type="text" id="ve-name" placeholder="Cain's Ballroom" />
                </div>
                <div class="form-group">
                    <label>Address</label>
                    <input type="text" id="ve-address" placeholder="423 N Main St, Tulsa, OK 74103" />
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Capacity</label>
                    <input type="number" id="ve-capacity" placeholder="1700" />
                </div>
                <div class="form-group">
                    <label>Venue Type</label>
                    <select id="ve-type" style="width:100%;padding:10px;background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.15);border-radius:6px;color:#fff;">
                        <option value="">Select type...</option>
                        <option value="Arena">Arena</option>
                        <option value="Concert Hall">Concert Hall</option>
                        <option value="Bar/Club">Bar/Club</option>
                        <option value="Theater">Theater</option>
                        <option value="Museum">Museum</option>
                        <option value="Gallery">Gallery</option>
                        <option value="Restaurant">Restaurant</option>
                        <option value="Brewery">Brewery</option>
                        <option value="Coffee Shop">Coffee Shop</option>
                        <option value="Park">Park</option>
                        <option value="Church">Church</option>
                        <option value="Library">Library</option>
                        <option value="University">University</option>
                        <option value="Casino">Casino</option>
                        <option value="Hotel">Hotel</option>
                        <option value="Conference Center">Conference Center</option>
                        <option value="Venue">Other Venue</option>
                    </select>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Noise Level</label>
                    <select id="ve-noise" style="width:100%;padding:10px;background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.15);border-radius:6px;color:#fff;">
                        <option value="">Select...</option>
                        <option value="Quiet">Quiet</option>
                        <option value="Moderate">Moderate</option>
                        <option value="Loud">Loud</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Website</label>
                    <input type="url" id="ve-website" placeholder="https://..." />
                </div>
            </div>
            <div class="form-group">
                <label>Parking Info</label>
                <input type="text" id="ve-parking" placeholder="On-site parking available. Street parking free after 5pm." />
            </div>
            <div class="form-group">
                <label>Accessibility Info</label>
                <input type="text" id="ve-access" placeholder="Wheelchair accessible. Elevators available." />
            </div>
            
            <div class="btn-group" style="margin-top:15px;">
                <button class="btn btn-primary" onclick="lookupVenueGoogle()">🔍 Lookup (Google)</button>
                <button class="btn btn-success" onclick="addToSQLQueue()">➕ Add to SQL</button>
                <button class="btn btn-secondary" onclick="clearManualEntry()">Clear</button>
            </div>
        </div>
        
        <!-- Paste box for edge cases -->
        <div id="paste-box" class="hidden" style="margin-bottom:15px;">
            <label>📋 Paste Info (from web research)</label>
            <textarea id="paste-text" style="width:100%;height:80px;background:rgba(0,0,0,0.3);color:#fff;border:1px solid rgba(255,255,255,0.15);border-radius:6px;padding:10px;font-size:12px;" placeholder="Paste venue info here... Address, hours, parking, etc."></textarea>
            <button class="btn btn-secondary" style="margin-top:8px;" onclick="parseFromPaste()">Parse Info</button>
        </div>
        
        <!-- SQL output -->
        <div id="sql-output" class="hidden">
            <label>Generated SQL <span style="color:#666;font-size:11px;">(copy to Supabase)</span></label>
            <textarea id="sql-text" style="width:100%;height:180px;background:#0a0a0a;color:#0f0;font-family:monospace;font-size:11px;border:1px solid #333;border-radius:6px;padding:10px;"></textarea>
            <div class="btn-group" style="margin-top:10px;">
                <button class="btn btn-secondary" onclick="copySQL()">📋 Copy</button>
                <button class="btn btn-secondary" onclick="downloadSQL()">💾 Download</button>
                <button class="btn btn-secondary" onclick="clearSQL()">🗑️ Clear</button>
            </div>
        </div>
    </div>
    
    <div class="footer">Scrape → Save → Done</div>
</div>

<script>
let events = [];
let lastFilename = '';

function log(msg, type='') {
    const box = document.getElementById('log-box');
    box.classList.remove('hidden');
    box.innerHTML += '<div class="'+(type?'log-'+type:'')+'">'+msg+'</div>';
    box.scrollTop = box.scrollHeight;
}

function status(msg, type='loading') {
    const el = document.getElementById('status');
    el.className = 'status ' + type;
    el.innerHTML = type==='loading' ? '<span class="spinner"></span>'+msg : msg;
    el.classList.remove('hidden');
}

async function scrape() {
    const url = document.getElementById('url').value.trim();
    const source = document.getElementById('source').value.trim() || 'unknown';
    const pw = document.getElementById('playwright').checked;
    const futureOnly = document.getElementById('future-only').checked;
    
    if (!url) { status('Enter a URL', 'error'); return; }
    
    document.getElementById('log-box').innerHTML = '';
    document.getElementById('scrape-btn').disabled = true;
    document.getElementById('results').classList.add('hidden');
    
    log('Checking robots.txt...');
    log('Fetching: ' + url);
    log('Method: ' + (pw ? 'Playwright' : 'httpx'));
    log('Future only: ' + futureOnly);
    status('Scraping...');
    
    try {
        const r = await fetch('/scrape', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({url, source_name: source, use_playwright: pw, future_only: futureOnly})
        });
        const d = await r.json();
        
        if (d.robots_blocked) {
            log('🚫 BLOCKED by robots.txt', 'error');
            log('This site has requested not to be scraped.', 'error');
            status('🚫 ' + d.error, 'error');
            return;
        }
        
        if (d.error) {
            log('ERROR: ' + d.error, 'error');
            status('Error: ' + d.error, 'error');
            return;
        }
        
        log('✓ robots.txt allows scraping', 'success');
        events = d.events;
        lastFilename = d.filename;
        
        log('HTML size: ' + d.html_size.toLocaleString() + ' chars', 'success');
        log('Found ' + events.length + ' events', 'success');
        if (d.methods && d.methods.length) {
            log('Extraction methods: ' + d.methods.join(', '), 'info');
        }
        
        document.getElementById('stat-count').textContent = events.length;
        document.getElementById('stat-html').textContent = (d.html_size/1024).toFixed(1)+'KB';
        
        // Show methods used
        const methodsDiv = document.getElementById('methods-used');
        if (d.methods && d.methods.length) {
            methodsDiv.innerHTML = d.methods.map(m => '<span class="method-tag">'+m+'</span>').join('');
        } else {
            methodsDiv.innerHTML = '';
        }
        
        const list = document.getElementById('event-list');
        if (events.length === 0) {
            list.innerHTML = '<p style="color:#888;">No events found. The site may use an unusual format.</p>';
        } else {
            list.innerHTML = events.map(e => `
                <div class="event-item">
                    <strong>${e.title || 'Untitled'}</strong>
                    ${e.date ? '<p>📅 '+e.date+'</p>' : ''}
                    ${e.venue && e.venue !== e.source ? '<p>📍 '+e.venue+'</p>' : ''}
                    ${e.source_url ? '<a href="'+e.source_url+'" target="_blank">🔗 Link</a>' : ''}
                </div>
            `).join('');
        }
        
        document.getElementById('results').classList.remove('hidden');
        status('Done! Found ' + events.length + ' events.', 'success');
        
    } catch (e) {
        log('ERROR: ' + e.message, 'error');
        status('Error: ' + e.message, 'error');
    } finally {
        document.getElementById('scrape-btn').disabled = false;
    }
}

async function saveToDb() {
    if (!events.length) { status('No events to save', 'error'); return; }
    
    status('Saving ' + events.length + ' events to database...');
    
    try {
        const r = await fetch('/to-database', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({events})
        });
        const d = await r.json();
        
        if (d.error) {
            status('Error: ' + d.error, 'error');
        } else {
            log('Saved ' + d.saved + ' of ' + d.total + ' to database', 'success');
            status('✓ Saved ' + d.saved + '/' + d.total + ' events to database!', 'success');
        }
    } catch (e) {
        status('Error: ' + e.message + ' (Is backend running on port 3000?)', 'error');
    }
}

// Saved URLs
async function loadSavedUrls() {
    try {
        const r = await fetch('/saved-urls');
        const urls = await r.json();
        const container = document.getElementById('saved-urls');
        
        if (!urls.length) {
            container.innerHTML = '';
            return;
        }
        
        container.innerHTML = `
            <div style="font-size:12px;color:#888;margin-bottom:8px;">📌 Saved URLs (click to load):</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;">
                ${urls.map(u => `
                    <div style="display:flex;align-items:center;background:rgba(0,0,0,0.3);border-radius:4px;padding:4px 8px;font-size:12px;">
                        <span onclick="loadUrl('${u.url}', '${u.name}', ${u.playwright !== false})" style="cursor:pointer;color:#6cf;">${u.name}</span>
                        <span onclick="deleteSavedUrl('${u.url}')" style="cursor:pointer;color:#666;margin-left:8px;">✕</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        console.error('Error loading saved URLs:', e);
    }
}

async function saveCurrentUrl() {
    const url = document.getElementById('url').value.trim();
    const name = document.getElementById('source').value.trim() || 'Unnamed';
    const playwright = document.getElementById('playwright').checked;
    
    if (!url) {
        status('Enter a URL first', 'error');
        return;
    }
    
    try {
        await fetch('/saved-urls', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ url, name, playwright })
        });
        loadSavedUrls();
        status(`Saved "${name}"`, 'success');
    } catch (e) {
        status('Error saving URL', 'error');
    }
}

async function deleteSavedUrl(url) {
    try {
        await fetch('/saved-urls', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ url })
        });
        loadSavedUrls();
    } catch (e) {
        console.error('Error deleting URL:', e);
    }
}

function loadUrl(url, name, playwright) {
    document.getElementById('url').value = url;
    document.getElementById('source').value = name;
    if (playwright !== undefined) {
        document.getElementById('playwright').checked = playwright;
    }
}

// ========================================
// VENUE MANAGER
// ========================================

let venueQueue = [];  // Queue of venues for SQL generation

function toggleManualEntry() {
    const el = document.getElementById('manual-entry');
    const paste = document.getElementById('paste-box');
    el.classList.toggle('hidden');
    paste.classList.toggle('hidden');
}

function toggleSQLOutput() {
    document.getElementById('sql-output').classList.toggle('hidden');
}

async function loadIncompleteVenues() {
    status('Loading venues...', 'loading');
    
    try {
        const r = await fetch('/api/venues/incomplete');
        const data = await r.json();
        
        if (data.error) {
            status('Error: ' + data.error, 'error');
            return;
        }
        
        document.getElementById('venue-stats').classList.remove('hidden');
        document.getElementById('venue-count').textContent = data.total;
        document.getElementById('incomplete-count').textContent = data.incomplete;
        
        const container = document.getElementById('incomplete-venues');
        container.classList.remove('hidden');
        
        if (data.venues.length === 0) {
            container.innerHTML = '<p style="color:#28a745;padding:10px;">✓ All venues have complete data!</p>';
        } else {
            container.innerHTML = data.venues.map(v => `
                <div class="event-item" style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="flex:1;">
                        <strong>${v.name}</strong>
                        <p style="color:#dc3545;font-size:11px;">Missing: ${v.missing.join(', ')}</p>
                    </div>
                    <div style="display:flex;gap:5px;">
                        <button class="btn btn-secondary" style="padding:4px 8px;font-size:10px;" 
                                onclick="editVenue('${v.name.replace(/'/g, "\\'")}', '${(v.address||'').replace(/'/g, "\\'")}', '${(v.website||'').replace(/'/g, "\\'")}')">
                            Edit
                        </button>
                        <button class="btn btn-primary" style="padding:4px 8px;font-size:10px;"
                                onclick="autoLookup('${v.name.replace(/'/g, "\\'")}')">
                            Auto
                        </button>
                    </div>
                </div>
            `).join('');
        }
        
        status('Loaded ' + data.incomplete + ' incomplete venues', 'success');
        
    } catch (e) {
        status('Error: ' + e.message + ' (Is backend running?)', 'error');
    }
}

function editVenue(name, address, website) {
    document.getElementById('ve-name').value = name;
    document.getElementById('ve-address').value = address || '';
    document.getElementById('ve-website').value = website || '';
    document.getElementById('manual-entry').classList.remove('hidden');
    document.getElementById('paste-box').classList.remove('hidden');
}

async function autoLookup(name) {
    document.getElementById('ve-name').value = name;
    document.getElementById('manual-entry').classList.remove('hidden');
    await lookupVenueGoogle();
}

async function lookupVenueGoogle() {
    const name = document.getElementById('ve-name').value.trim();
    if (!name) {
        status('Enter venue name first', 'error');
        return;
    }
    
    status('Looking up ' + name + ' on Google...', 'loading');
    
    try {
        const r = await fetch('/api/venues/lookup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, city: 'Tulsa, OK'})
        });
        const data = await r.json();
        
        if (data.error) {
            status('Not found or API error: ' + data.error, 'error');
            return;
        }
        
        // Fill in the form with found data
        if (data.address) document.getElementById('ve-address').value = data.address;
        if (data.website) document.getElementById('ve-website').value = data.website;
        if (data.inferred_type) {
            const sel = document.getElementById('ve-type');
            for (let opt of sel.options) {
                if (opt.value === data.inferred_type) { opt.selected = true; break; }
            }
        }
        if (data.wheelchair_accessible !== null) {
            document.getElementById('ve-access').value = data.wheelchair_accessible 
                ? 'Wheelchair accessible entrance' 
                : 'Contact venue for accessibility';
        }
        
        status('Found! Review data and add to SQL.', 'success');
        
    } catch (e) {
        status('Lookup error: ' + e.message, 'error');
    }
}

function parseFromPaste() {
    const text = document.getElementById('paste-text').value;
    if (!text.trim()) return;
    
    // Try to extract address (look for patterns like "123 N Main St")
    const addrMatch = text.match(/\d+\s+[NSEW]\.?\s+\w+\s+(St|Ave|Blvd|Dr|Rd|Way|Pl)[^,]*,?\s*(Tulsa|OK)?[^,]*,?\s*(OK\s*\d{5})?/i);
    if (addrMatch && !document.getElementById('ve-address').value) {
        document.getElementById('ve-address').value = addrMatch[0].trim();
    }
    
    // Try to extract capacity (look for numbers followed by "capacity", "seats", etc.)
    const capMatch = text.match(/(\d{1,5})\s*(capacity|seats|people|guests)/i) || 
                     text.match(/(capacity|seats)[:\s]*(\d{1,5})/i);
    if (capMatch && !document.getElementById('ve-capacity').value) {
        const cap = capMatch[1].match(/\d+/) ? capMatch[1] : capMatch[2];
        document.getElementById('ve-capacity').value = cap;
    }
    
    // Try to extract website
    const urlMatch = text.match(/https?:\/\/[^\s<>"]+/i);
    if (urlMatch && !document.getElementById('ve-website').value) {
        document.getElementById('ve-website').value = urlMatch[0];
    }
    
    // Look for parking info
    const parkMatch = text.match(/parking[^.]*\./i);
    if (parkMatch && !document.getElementById('ve-parking').value) {
        document.getElementById('ve-parking').value = parkMatch[0];
    }
    
    // Look for accessibility info  
    const accessMatch = text.match(/(wheelchair|ada|accessible|accessibility)[^.]*\./i);
    if (accessMatch && !document.getElementById('ve-access').value) {
        document.getElementById('ve-access').value = accessMatch[0];
    }
    
    status('Parsed! Review and adjust as needed.', 'success');
}

function addToSQLQueue() {
    const venue = {
        name: document.getElementById('ve-name').value.trim(),
        address: document.getElementById('ve-address').value.trim(),
        capacity: document.getElementById('ve-capacity').value.trim(),
        venue_type: document.getElementById('ve-type').value,
        noise_level: document.getElementById('ve-noise').value,
        website: document.getElementById('ve-website').value.trim(),
        parking_info: document.getElementById('ve-parking').value.trim(),
        accessibility_info: document.getElementById('ve-access').value.trim(),
    };
    
    if (!venue.name) {
        status('Venue name is required', 'error');
        return;
    }
    
    // Check if already in queue, update if so
    const idx = venueQueue.findIndex(v => v.name.toLowerCase() === venue.name.toLowerCase());
    if (idx >= 0) {
        venueQueue[idx] = {...venueQueue[idx], ...venue};
    } else {
        venueQueue.push(venue);
    }
    
    updateSQLOutput();
    clearManualEntry();
    status('Added ' + venue.name + ' to SQL queue (' + venueQueue.length + ' total)', 'success');
}

function updateSQLOutput() {
    const sqlLines = [
        '-- Venue Updates - Generated by ScraperTool',
        '-- Run in Supabase SQL Editor',
        ''
    ];
    
    for (const v of venueQueue) {
        const sets = [];
        if (v.address) sets.push(`address = '${v.address.replace(/'/g, "''")}'`);
        if (v.capacity) sets.push(`capacity = ${parseInt(v.capacity)}`);
        if (v.venue_type) sets.push(`venue_type = '${v.venue_type}'`);
        if (v.noise_level) sets.push(`noise_level = '${v.noise_level}'`);
        if (v.website) sets.push(`website = '${v.website.replace(/'/g, "''")}'`);
        if (v.parking_info) sets.push(`parking_info = '${v.parking_info.replace(/'/g, "''")}'`);
        if (v.accessibility_info) sets.push(`accessibility_info = '${v.accessibility_info.replace(/'/g, "''")}'`);
        
        if (sets.length > 0) {
            sqlLines.push(`UPDATE venues SET`);
            sqlLines.push(`    ${sets.join(',\\n    ')}`);
            sqlLines.push(`WHERE name ILIKE '%${v.name.replace(/'/g, "''")}%';`);
            sqlLines.push('');
        }
    }
    
    document.getElementById('sql-text').value = sqlLines.join('\\n');
    document.getElementById('sql-output').classList.remove('hidden');
}

function clearManualEntry() {
    ['ve-name','ve-address','ve-capacity','ve-website','ve-parking','ve-access'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('ve-type').value = '';
    document.getElementById('ve-noise').value = '';
    document.getElementById('paste-text').value = '';
}

function copySQL() {
    const ta = document.getElementById('sql-text');
    ta.select();
    document.execCommand('copy');
    status('SQL copied to clipboard!', 'success');
}

function downloadSQL() {
    const sql = document.getElementById('sql-text').value;
    const blob = new Blob([sql], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'venue_updates.sql';
    a.click();
    URL.revokeObjectURL(url);
}

function clearSQL() {
    venueQueue = [];
    document.getElementById('sql-text').value = '-- No venues in queue';
}

// Load saved URLs on page load
document.addEventListener('DOMContentLoaded', loadSavedUrls);
</script>
</body>
</html>
'''


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/saved-urls', methods=['GET'])
def get_saved_urls():
    return jsonify(load_saved_urls())


@app.route('/saved-urls', methods=['POST'])
def add_saved_url():
    data = request.json
    urls = save_url(data.get('url', ''), data.get('name', ''), data.get('playwright', True))
    return jsonify(urls)


@app.route('/saved-urls', methods=['DELETE'])
def remove_saved_url():
    data = request.json
    urls = delete_saved_url(data.get('url', ''))
    return jsonify(urls)



@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    url = data.get('url')
    source_name = data.get('source_name', 'unknown')
    use_playwright = data.get('use_playwright', True)
    future_only = data.get('future_only', True)  # Default to future events only
    ignore_robots = data.get('ignore_robots', False)  # Allow override

    if not url:
        return jsonify({"error": "URL required"}), 400

    # Check robots.txt first
    robots_result = check_robots_txt(url)
    print(f"[robots.txt] {url}: {robots_result['message']}")

    if not robots_result['allowed'] and not ignore_robots:
        return jsonify({
            "error": f"Blocked by robots.txt: {robots_result['message']}",
            "robots_blocked": True,
            "events": [],
            "html_size": 0,
            "methods": []
        }), 403

    # Auto-save this URL to history
    save_url(url, source_name, use_playwright)

    try:
        # Fetch HTML
        if use_playwright:
            html = asyncio.run(fetch_with_playwright(url))
        else:
            html = asyncio.run(fetch_with_httpx(url))

        methods = []
        events = []

        # PRIORITY 1: Try EventCalendarApp API (Guthrie Green, etc.)
        eca_events, eca_detected = asyncio.run(extract_eventcalendarapp(html, source_name, url, future_only))
        if eca_detected and eca_events:
            events = eca_events
            methods.append(f"EventCalendarApp API ({len(events)})")
            print(f"[EventCalendarApp] SUCCESS: {len(events)} events via direct API")

        # PRIORITY 2: Try Timely API (Starlite Bar, etc.)
        if not events:
            timely_events, timely_detected = asyncio.run(extract_timely(html, source_name, url, future_only))
            if timely_detected and timely_events:
                events = timely_events
                methods.append(f"Timely API ({len(events)})")
                print(f"[Timely] SUCCESS: {len(events)} events via direct API")

        # PRIORITY 3: Try BOK Center API
        if not events:
            bok_events, bok_detected = asyncio.run(extract_bok_center(html, source_name, url, future_only))
            if bok_detected and bok_events:
                events = bok_events
                methods.append(f"BOK Center API ({len(events)})")
                print(f"[BOK Center] SUCCESS: {len(events)} events via API")

        # PRIORITY 4: Try Expo Square (Saffire) API
        if not events:
            expo_events, expo_detected = asyncio.run(extract_expo_square_events(html, source_name, url, future_only))
            if expo_detected and expo_events:
                events = expo_events
                methods.append(f"Expo Square API ({len(events)})")
                print(f"[Expo Square] SUCCESS: {len(events)} events via API")

        # PRIORITY 5: Try Eventbrite API
        if not events:
            eb_events, eb_detected = asyncio.run(extract_eventbrite_api_events(html, source_name, url, future_only))
            if eb_detected and eb_events:
                events = eb_events
                methods.append(f"Eventbrite API ({len(events)})")
                print(f"[Eventbrite] SUCCESS: {len(events)} events via API")

        # PRIORITY 6: Try Simpleview CMS API (VisitTulsa, etc.)
        if not events:
            sv_events, sv_detected = asyncio.run(extract_simpleview_events(html, source_name, url, future_only))
            if sv_detected and sv_events:
                events = sv_events
                methods.append(f"Simpleview API ({len(events)})")
                print(f"[Simpleview] SUCCESS: {len(events)} events via API")

        # FALLBACK: HTML-based extraction
        if not events:
            events = extract_events_universal(html, url, source_name)

            # Get extraction methods used
            if events and '_extraction_methods' in events[0]:
                methods = events[0]['_extraction_methods']
                # Remove internal metadata from events
                for e in events:
                    e.pop('_extraction_methods', None)

        # Save HTML for reference
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-]', '_', source_name)
        filename = f"{safe_name}_{timestamp}.html"
        (OUTPUT_DIR / filename).write_text(html, encoding='utf-8')

        return jsonify({
            "events": events,
            "html_size": len(html),
            "filename": filename,
            "methods": methods
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/save', methods=['POST'])
def save():
    data = request.json
    events = data.get('events', [])
    source = data.get('source', 'unknown')

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-]', '_', source)
    filename = f"{safe_name}_{timestamp}.json"

    (OUTPUT_DIR / filename).write_text(json.dumps(events, indent=2), encoding='utf-8')

    return jsonify({"filename": filename, "count": len(events)})


def transform_event_for_backend(event: dict) -> dict:
    """
    Transform scraped event to match Rust backend's CreateEvent schema.

    Backend schema:
    - title: String (required)
    - source_url: String (required) - MUST be the actual event page URL
    - start_time: DateTime<Utc> (required) - ISO format
    - end_time: Option<DateTime<Utc>>
    - source_name: Option<String>
    - venue: Option<String>
    - venue_address: Option<String>
    - location: Option<String> - city/area like "Tulsa", "Downtown"
    - description: Option<String>
    - image_url: Option<String>
    - categories: Option<Vec<String>>
    - outdoor: Option<bool>
    - family_friendly: Option<bool>
    - price_min/price_max: Option<f64>
    """
    from dateutil import parser as date_parser
    from datetime import timezone, datetime, timedelta

    # Start with required fields
    transformed = {
        'title': event.get('title', 'Untitled Event'),
    }

    # source_url - prefer the actual event detail page
    source_url = (
            event.get('source_url') or
            event.get('detail_url') or
            event.get('url') or
            event.get('tickets_url') or
            ''
    )
    transformed['source_url'] = source_url

    # Parse start_time from various possible fields
    date_str = (
            event.get('start_time') or
            event.get('startDate') or
            event.get('date') or
            event.get('start_date') or
            ''
    )
    if date_str:
        try:
            # Try to parse the date string
            parsed_date = date_parser.parse(str(date_str), fuzzy=True)
            # Ensure it has timezone (assume Central Time if none)
            if parsed_date.tzinfo is None:
                # Use UTC for consistency
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            transformed['start_time'] = parsed_date.isoformat()
        except:
            # Fallback: use current time + 1 day if unparseable
            fallback = datetime.now(timezone.utc) + timedelta(days=1)
            transformed['start_time'] = fallback.isoformat()
            print(f"[DB] Warning: Could not parse start date '{date_str}', using fallback")
    else:
        # No date provided - use tomorrow as fallback
        fallback = datetime.now(timezone.utc) + timedelta(days=1)
        transformed['start_time'] = fallback.isoformat()

    # Parse end_time if available
    end_str = (
            event.get('end_time') or
            event.get('endDate') or
            event.get('end_date') or
            ''
    )
    if end_str:
        try:
            parsed_end = date_parser.parse(str(end_str), fuzzy=True)
            if parsed_end.tzinfo is None:
                parsed_end = parsed_end.replace(tzinfo=timezone.utc)
            transformed['end_time'] = parsed_end.isoformat()
        except:
            pass  # Skip if unparseable

    # Map source_name
    source_name = event.get('source_name') or event.get('source') or ''
    if source_name:
        transformed['source_name'] = source_name

    # Venue and address
    if event.get('venue'):
        transformed['venue'] = event['venue']
    if event.get('venue_address'):
        transformed['venue_address'] = event['venue_address']

    # Location (city/area, separate from venue_address)
    if event.get('location'):
        loc = event['location']
        # If it's coordinates, skip (those should go elsewhere)
        if isinstance(loc, str) and ',' in loc and loc.replace(',', '').replace('.', '').replace('-', '').isdigit():
            pass  # Skip coordinate strings
        else:
            transformed['location'] = loc
    elif event.get('city'):
        transformed['location'] = event['city']

    # Description
    if event.get('description'):
        desc = event['description']
        # Clean up and truncate
        if isinstance(desc, str):
            desc = desc.strip()[:2000]  # Limit to 2000 chars
            transformed['description'] = desc

    # Image URL
    if event.get('image_url'):
        transformed['image_url'] = event['image_url']

    # Handle price - support both combined 'price' and separate min/max
    price_min = None
    price_max = None

    if event.get('price_min') is not None:
        try:
            price_min = float(event['price_min'])
        except (ValueError, TypeError):
            pass
    if event.get('price_max') is not None:
        try:
            price_max = float(event['price_max'])
        except (ValueError, TypeError):
            pass

    # Parse combined 'price' field
    if price_min is None and event.get('price'):
        price_str = str(event['price']).replace('$', '').replace(',', '').strip()
        if '-' in price_str:
            # Range like "15-25"
            parts = price_str.split('-')
            try:
                price_min = float(parts[0].strip())
                price_max = float(parts[1].strip())
            except:
                pass
        elif price_str.lower() in ['free', '0', '0.00']:
            price_min = 0.0
            price_max = 0.0
        else:
            try:
                price_min = float(price_str)
            except:
                pass

    # Handle is_free flag
    if event.get('is_free') == True:
        price_min = 0.0
        price_max = 0.0

    if price_min is not None:
        transformed['price_min'] = price_min
    if price_max is not None:
        transformed['price_max'] = price_max

    # Categories - convert string to list if needed
    if event.get('categories'):
        cats = event['categories']
        if isinstance(cats, str):
            transformed['categories'] = [cats]
        elif isinstance(cats, list):
            # Filter out empty strings
            transformed['categories'] = [c for c in cats if c]

    # Boolean flags
    if event.get('outdoor') is not None:
        transformed['outdoor'] = bool(event['outdoor'])
    else:
        transformed['outdoor'] = False

    if event.get('family_friendly') is not None:
        transformed['family_friendly'] = bool(event['family_friendly'])
    else:
        transformed['family_friendly'] = False

    return transformed


@app.route('/to-database', methods=['POST'])
def to_database():
    """Send events to database via Rust backend (concurrent)."""
    import concurrent.futures

    data = request.json
    events = data.get('events', [])

    if not events:
        return jsonify({"saved": 0, "total": 0})

    print(f"[DB] Sending {len(events)} events to backend...")

    # Collect unique venues from events (with website from API)
    venues_to_save = {}
    for event in events:
        venue_name = event.get('venue', '').strip()
        if venue_name and venue_name.lower() not in ['tba', 'tbd', 'online', 'online event', 'virtual', '']:
            venue_key = venue_name.lower()
            if venue_key not in venues_to_save:
                venues_to_save[venue_key] = {
                    'name': venue_name,
                    'address': event.get('venue_address', ''),
                    'city': 'Tulsa',
                    '_venue_website': event.get('_venue_website', ''),
                }
            # If this event has a website but the stored one doesn't, update it
            elif not venues_to_save[venue_key].get('_venue_website') and event.get('_venue_website'):
                venues_to_save[venue_key]['_venue_website'] = event.get('_venue_website')

    # Register venues with websites from API
    venues_with_websites = 0
    if venues_to_save:
        print(f"[DB] Registering {len(venues_to_save)} venues...")
        for venue_key, venue_data in venues_to_save.items():
            # Get website from API data
            website = venue_data.pop('_venue_website', '')
            if website:
                venue_data['website'] = website
                venues_with_websites += 1
                print(f"[DB] Venue '{venue_data['name']}' has website: {website}")

            # Send to backend
            try:
                httpx.post(f"{BACKEND_URL}/api/venues", json=venue_data, timeout=3)
            except:
                pass  # Best effort

        print(f"[DB] Found websites for {venues_with_websites}/{len(venues_to_save)} venues")

    def post_event(event):
        try:
            # Transform to backend schema
            transformed = transform_event_for_backend(event)
            resp = httpx.post(f"{BACKEND_URL}/api/events", json=transformed, timeout=5)
            if resp.status_code not in [200, 201]:
                print(f"[DB] Rejected: {resp.status_code} - {resp.text[:100]}")
            return resp.status_code in [200, 201]
        except Exception as e:
            print(f"[DB] Error: {e}")
            return False

    # Send 10 requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(post_event, events))

    saved = sum(results)
    print(f"[DB] Complete: {saved}/{len(events)} saved")

    return jsonify({
        "saved": saved,
        "total": len(events),
        "venues_registered": len(venues_to_save),
        "venues_with_websites": venues_with_websites
    })


@app.route('/upload-all-to-database', methods=['POST'])
def upload_all_to_database():
    """Read all saved JSON files and send events to database concurrently."""
    import concurrent.futures

    total_events = 0
    total_saved = 0
    files_processed = 0
    errors = []

    # Get all JSON files (excluding special files)
    json_files = sorted(OUTPUT_DIR.glob("*.json"), reverse=True)
    skip_files = {'venues.json', 'saved_urls.json'}

    # Collect all events from all files
    all_events = []
    for f in json_files:
        if f.name in skip_files:
            continue
        try:
            events = json.loads(f.read_text())
            if isinstance(events, list) and len(events) > 0:
                files_processed += 1
                all_events.extend(events)
        except Exception as e:
            errors.append(f"{f.name}: {str(e)}")

    total_events = len(all_events)
    print(f"[Upload] {total_events} events from {files_processed} files")

    def post_event(event):
        try:
            # Transform to backend schema
            transformed = transform_event_for_backend(event)
            resp = httpx.post(f"{BACKEND_URL}/api/events", json=transformed, timeout=5)
            return resp.status_code in [200, 201]
        except:
            return False

    # Send 10 requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(post_event, all_events))

    total_saved = sum(results)
    print(f"[Upload] Complete: {total_saved}/{total_events} saved")

    return jsonify({
        "files_processed": files_processed,
        "total_events": total_events,
        "saved": total_saved,
        "errors": errors
    })


@app.route('/clear-files', methods=['POST'])
def clear_files():
    """Delete all saved JSON files."""
    deleted = 0
    for f in OUTPUT_DIR.glob("*.json"):
        if f.name == 'venues.json':
            continue
        try:
            f.unlink()
            deleted += 1
        except:
            pass

    # Also delete HTML files
    for f in OUTPUT_DIR.glob("*.html"):
        try:
            f.unlink()
            deleted += 1
        except:
            pass

    return jsonify({"success": True, "deleted": deleted})


@app.route('/files')
def list_files():
    files = []
    for f in sorted(OUTPUT_DIR.glob("*.json"), reverse=True):
        files.append({"name": f.name, "size": f"{f.stat().st_size/1024:.1f}KB"})
    return jsonify({"files": files})


@app.route('/download/<filename>')
def download(filename):
    path = OUTPUT_DIR / filename
    if path.exists():
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Not found"}), 404


@app.route('/venues-missing-urls')
def venues_missing_urls():
    """Fetch venues from backend that are missing website URLs."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/venues/missing", timeout=10)
        if resp.status_code == 200:
            venues = resp.json()
            # Return just the names for easy copy/paste
            names = [v.get('name', '') for v in venues if v.get('name')]
            return jsonify({
                "count": len(names),
                "venues": names
            })
        else:
            return jsonify({"error": f"Backend returned {resp.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# VENUE MANAGER API
# ============================================================================

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")


@app.route('/api/venues/incomplete', methods=['GET'])
def get_incomplete_venues():
    """Fetch venues that are missing key data fields."""
    try:
        # Fetch all venues from backend
        resp = httpx.get(f"{BACKEND_URL}/api/venues", timeout=10)
        venues = resp.json() if resp.status_code == 200 else []

        # Filter to venues missing data
        incomplete = []
        for v in venues:
            missing = []
            if not v.get('address'):
                missing.append('address')
            if not v.get('capacity'):
                missing.append('capacity')
            if not v.get('venue_type'):
                missing.append('type')
            if not v.get('parking_info'):
                missing.append('parking')
            if not v.get('website'):
                missing.append('website')

            if missing:
                incomplete.append({
                    'id': v.get('id'),
                    'name': v.get('name'),
                    'address': v.get('address', ''),
                    'website': v.get('website', ''),
                    'missing': missing,
                    'missing_count': len(missing),
                })

        # Sort by most missing first
        incomplete.sort(key=lambda x: -x['missing_count'])

        return jsonify({
            'total': len(venues),
            'incomplete': len(incomplete),
            'venues': incomplete
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/venues/lookup', methods=['POST'])
def lookup_venue():
    """Look up venue details from Google Places API."""
    data = request.json
    venue_name = data.get('name', '')
    city = data.get('city', 'Tulsa, OK')

    if not venue_name:
        return jsonify({'error': 'Venue name required'}), 400

    if not GOOGLE_PLACES_API_KEY:
        return jsonify({'error': 'Google Places API key not configured. Add GOOGLE_PLACES_API_KEY to .env'}), 500

    try:
        result = asyncio.run(lookup_venue_google_places(venue_name, city))

        if result.get('types'):
            result['inferred_type'] = infer_venue_type_from_google(result['types'], venue_name)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


async def lookup_venue_google_places(venue_name: str, city: str = "Tulsa, OK") -> dict:
    """
    Look up venue details from Google Places API.
    """
    result = {
        "address": "",
        "website": "",
        "phone": "",
        "place_id": "",
        "types": [],
        "rating": None,
        "wheelchair_accessible": None,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Step 1: Text Search to find the place
            search_query = f"{venue_name} {city}"
            search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            search_resp = await client.get(search_url, params={
                "query": search_query,
                "key": GOOGLE_PLACES_API_KEY,
            })
            search_data = search_resp.json()

            if search_data.get("status") != "OK" or not search_data.get("results"):
                return {"error": f"Place not found: {venue_name}"}

            place = search_data["results"][0]
            result["place_id"] = place.get("place_id", "")
            result["address"] = place.get("formatted_address", "")
            result["types"] = place.get("types", [])
            result["rating"] = place.get("rating")

            # Step 2: Get detailed info (website, phone, accessibility)
            if result["place_id"]:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_resp = await client.get(details_url, params={
                    "place_id": result["place_id"],
                    "fields": "website,formatted_phone_number,wheelchair_accessible_entrance",
                    "key": GOOGLE_PLACES_API_KEY,
                })
                details_data = details_resp.json()

                if details_data.get("status") == "OK" and details_data.get("result"):
                    details = details_data["result"]
                    result["website"] = details.get("website", "")
                    result["phone"] = details.get("formatted_phone_number", "")
                    result["wheelchair_accessible"] = details.get("wheelchair_accessible_entrance")

            return result

    except Exception as e:
        return {"error": str(e)}


def infer_venue_type_from_google(types: list, name: str) -> str:
    """Infer venue type from Google Places types."""
    type_mapping = {
        "bar": "Bar/Club",
        "night_club": "Bar/Club",
        "restaurant": "Restaurant",
        "cafe": "Coffee Shop",
        "museum": "Museum",
        "art_gallery": "Gallery",
        "movie_theater": "Theater",
        "performing_arts_theater": "Theater",
        "stadium": "Arena",
        "church": "Church",
        "park": "Park",
        "library": "Library",
        "university": "University",
        "school": "University",
        "casino": "Casino",
        "lodging": "Hotel",
        "bowling_alley": "Entertainment",
        "amusement_park": "Entertainment",
        "zoo": "Zoo/Aquarium",
        "aquarium": "Zoo/Aquarium",
    }

    for place_type in types:
        if place_type in type_mapping:
            return type_mapping[place_type]

    # Fallback: infer from name
    name_lower = name.lower()
    if "museum" in name_lower:
        return "Museum"
    elif "theater" in name_lower or "theatre" in name_lower:
        return "Theater"
    elif "bar" in name_lower or "pub" in name_lower:
        return "Bar/Club"
    elif "church" in name_lower:
        return "Church"
    elif "park" in name_lower:
        return "Park"
    elif "ballroom" in name_lower or "center" in name_lower:
        return "Concert Hall"
    elif "brewery" in name_lower or "brewing" in name_lower:
        return "Brewery"
    elif "coffee" in name_lower or "cafe" in name_lower:
        return "Coffee Shop"

    return "Venue"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("=" * 50)
    print("  Locate918 Universal Scraper")
    print("  Smart extraction - No LLM required")
    print("  ✓ Respects robots.txt")
    print("=" * 50)
    print(f"  Output: {OUTPUT_DIR.absolute()}")
    print("=" * 50)
    print("  http://localhost:5000")
    print("=" * 50)

    app.run(debug=True, port=5000)