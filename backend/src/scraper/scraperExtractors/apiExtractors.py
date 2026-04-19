"""
Locate918 Scraper - Direct API Extractors
==========================================
Extractors for venues that expose direct JSON APIs:
  - EventCalendarApp (Guthrie Green, Fly Loft, LowDown)
  - Timely (Starlite Bar)
  - BOK Center (custom AJAX API)

FIX: BOK Center multi-day events (e.g., "Mar 6-7") now preserved correctly.
"""

import re
import json
import asyncio
from datetime import datetime, timezone as _tz
import pytz
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

_CENTRAL = pytz.timezone("America/Chicago")

from scraperUtils import (
    HEADERS,
    COMBINED_DATE_PATTERN,
    COMBINED_TIME_PATTERN,
    extract_date_from_text,
    extract_time_from_text,
    text_has_date,
)


# ============================================================================
# EVENTCALENDARAPP
# ============================================================================

KNOWN_EVENTCALENDARAPP_VENUES = {
    'guthriegreen.com': {'id': '11692', 'widgetUuid': 'dcafff1d-f2a8-4799-9a6b-a5ad3e3a6ff2'},
    'www.guthriegreen.com': {'id': '11692', 'widgetUuid': 'dcafff1d-f2a8-4799-9a6b-a5ad3e3a6ff2'},
}


def detect_eventcalendarapp(html: str, url: str = '') -> dict | None:
    if url:
        try:
            domain = urlparse(url).netloc.lower()
            if domain in KNOWN_EVENTCALENDARAPP_VENUES:
                print(f"[EventCalendarApp] Known venue: {domain}")
                return KNOWN_EVENTCALENDARAPP_VENUES[domain]
        except:
            pass

    patterns = [
        re.compile(r'eventcalendarapp\.com[^"\']*[?&]id=(\d+)[^"\']*widgetUuid=([a-f0-9-]+)', re.IGNORECASE),
        re.compile(r'eventcalendarapp\.com[^"\']*widgetUuid=([a-f0-9-]+)[^"\']*[?&]id=(\d+)', re.IGNORECASE),
        re.compile(r'api\.eventcalendarapp\.com/events\?id=(\d+)[^"\']*widgetUuid=([a-f0-9-]+)', re.IGNORECASE),
    ]

    for i, pattern in enumerate(patterns):
        match = pattern.search(html)
        if match:
            if i == 1:
                return {'id': match.group(2), 'widgetUuid': match.group(1)}
            return {'id': match.group(1), 'widgetUuid': match.group(2)}

    id_only = re.compile(r'eventcalendarapp\.com[^"\']*[?&]id=(\d+)', re.IGNORECASE)
    match = id_only.search(html)
    if match:
        uuid_match = re.search(r'widgetUuid[=:]["\']?([a-f0-9-]{36})', html, re.IGNORECASE)
        return {'id': match.group(1), 'widgetUuid': uuid_match.group(1) if uuid_match else None}

    return None


async def fetch_eventcalendarapp_api(calendar_id: str, widget_uuid: str = None, max_pages: int = 50) -> list:
    """
    Fetch events from EventCalendarApp API.

    The API stores events oldest-first. Passing inAdminPanel=true causes the
    API to return the *current* page (events around today) instead of page 1
    (which may be years in the past). We use this to find the start page, then
    paginate forward to the last page to capture all upcoming events.
    """
    all_events = []

    base_url = f"https://api.eventcalendarapp.com/events?id={calendar_id}"
    if widget_uuid:
        base_url += f"&widgetUuid={widget_uuid}"

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        # Step 1: hit inAdminPanel=true to get the current page number
        try:
            resp = await client.get(base_url + "&inAdminPanel=true")
            resp.raise_for_status()
            data = resp.json()
            start_page = data.get('pages', {}).get('current', 1)
            total_pages = data.get('pages', {}).get('total', 1)
            # Collect events from this response too
            all_events.extend(data.get('events', []))
            print(f"[EventCalendarApp] Starting at page {start_page} of {total_pages}")
        except Exception as e:
            print(f"[EventCalendarApp] Failed to get start page: {e}")
            start_page = 1
            total_pages = max_pages

        # Step 2: paginate forward from start_page+1 to end
        page = start_page + 1
        pages_fetched = 1
        while page <= total_pages and pages_fetched < max_pages:
            try:
                resp = await client.get(base_url + f"&page={page}")
                resp.raise_for_status()
                data = resp.json()
                events = data.get('events', [])
                if not events:
                    break
                all_events.extend(events)
                page += 1
                pages_fetched += 1
            except Exception as e:
                print(f"EventCalendarApp API error page {page}: {e}")
                break

    return all_events


def parse_eventcalendarapp_events(raw_events: list, source_name: str, future_only: bool = True) -> list:
    events = []
    seen = set()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for raw in raw_events:
        title = raw.get('summary', '').strip()
        if not title:
            continue
        start = raw.get('timezoneStart', '')
        end = raw.get('timezoneEnd', '')

        if future_only and start:
            try:
                start_dt = _timely_to_local(start)
                if start_dt and start_dt < today:
                    continue
            except:
                pass

        date_str = ''
        date_key = start[:10] if start else ''
        if start:
            try:
                dt = datetime.fromisoformat(start.replace('Z', '').split('+')[0])
                date_key = dt.strftime('%Y-%m-%d')
                date_str = dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')
                if end:
                    end_dt = datetime.fromisoformat(end.replace('Z', '').split('+')[0])
                    if dt.date() == end_dt.date():
                        date_str += f" - {end_dt.strftime('%I:%M %p').lstrip('0')}"
            except:
                date_str = start

        dedup_key = f"{title.lower()[:60]}|{date_key}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        location = raw.get('location', {})
        venue = location.get('description', '') if isinstance(location, dict) else ''
        if not venue:
            venue = source_name

        desc = raw.get('shortDescription', '') or raw.get('description', '')
        if desc:
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()[:200]

        events.append({
            'title': title,
            'date': date_str,
            'end_date': end,
            'venue': venue,
            'description': desc,
            'source_url': raw.get('url', ''),
            'tickets_url': raw.get('ticketsLink', ''),
            'image_url': raw.get('image', '') or raw.get('thumbnail', ''),
            'source': source_name,
            'featured': raw.get('featured', False),
        })

    return events


async def extract_eventcalendarapp(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    params = detect_eventcalendarapp(html, url)
    if not params:
        return [], False

    print(f"[EventCalendarApp] Detected calendar ID: {params['id']}")
    raw_events = await fetch_eventcalendarapp_api(params['id'], params.get('widgetUuid'))
    print(f"[EventCalendarApp] Fetched {len(raw_events)} total events from API")
    events = parse_eventcalendarapp_events(raw_events, source_name, future_only)
    if future_only:
        print(f"[EventCalendarApp] {len(events)} upcoming events after date filter")
    return events, True


# ============================================================================
# TIMELY
# ============================================================================

KNOWN_TIMELY_VENUES = {
    'thestarlitebar.com': {'id': '54755961'},
    'www.thestarlitebar.com': {'id': '54755961'},
}


def detect_timely(html: str, url: str = '') -> dict | None:
    if url:
        try:
            domain = urlparse(url).netloc.lower()
            if domain in KNOWN_TIMELY_VENUES:
                print(f"[Timely] Known venue: {domain}")
                return KNOWN_TIMELY_VENUES[domain]
        except:
            pass

    for pattern in [
        re.compile(r'data-calendar-id[=:]["\']?(\d+)', re.IGNORECASE),
        re.compile(r'events\.timely\.fun/(?:api/calendars/)?(\d+)', re.IGNORECASE),
        re.compile(r'timelyapp\.time\.ly/[^/]*/calendars/(\d+)', re.IGNORECASE),
    ]:
        match = pattern.search(html)
        if match:
            return {'id': match.group(1)}

    return None


async def fetch_timely_api(calendar_id: str, referer_url: str = '', max_pages: int = 10) -> list:
    import time
    all_events = []
    page = 1
    start_timestamp = int(time.time())

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
                items = data.get('data', {}).get('items', [])
                if not items:
                    break
                for item in items:
                    all_events.extend(item.get('events', []))
                total = data.get('data', {}).get('total', 0)
                if len(all_events) >= total:
                    break
                page += 1
            except Exception as e:
                print(f"Timely API error page {page}: {e}")
                break

    return all_events


def _timely_to_local(dt_str: str) -> datetime | None:
    """
    Parse an arbitrary datetime string to a naive datetime (TZ stripped).
    Used by the EventCalendarApp future-filter for same-day comparisons.
    """
    if not dt_str:
        return None
    try:
        from dateutil import parser as _dp
        return _dp.parse(str(dt_str).strip()).replace(tzinfo=None)
    except Exception:
        return None


def _timely_to_central_iso(raw: dict, field_local: str, field_utc: str) -> str:
    """
    Build a correct ISO-8601 string in America/Chicago time from a Timely event.

    Uses `start_utc_datetime` (or `end_utc_datetime`) as the source of truth
    because it's unambiguous, then converts to Central with the proper
    DST-aware offset via zoneinfo. Falls back to the local field only if the
    UTC field is missing, and in that case trusts it as already-Central.

    This fixes the one-day-off bug that happened when Timely's `start_datetime`
    was assumed to be local but actually arrived as UTC — the old code would
    re-label a UTC value with a -05:00 offset and shift the day forward.
    """
    utc_str = raw.get(field_utc) or ''
    if utc_str:
        try:
            from dateutil import parser as _dp
            dt = _dp.parse(str(utc_str).strip())
            # Naive "utc" field → treat as UTC; aware → respect it
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)
            return dt.astimezone(_CENTRAL).isoformat()
        except Exception:
            pass

    # Fallback: no UTC field, trust the local field and attach Central offset
    local_str = raw.get(field_local) or ''
    if not local_str:
        return ''
    try:
        from dateutil import parser as _dp
        dt = _dp.parse(str(local_str).strip())
        if dt.tzinfo is None:
            # pytz requires .localize() to attach a tz correctly — using
            # .replace(tzinfo=...) with pytz gives the wrong "LMT" offset.
            dt = _CENTRAL.localize(dt)
        else:
            dt = dt.astimezone(_CENTRAL)
        return dt.isoformat()
    except Exception:
        return str(local_str)


def parse_timely_events(raw_events: list, source_name: str, future_only: bool = True) -> list:
    events = []
    seen = set()
    now_utc = datetime.now(_tz.utc)

    for raw in raw_events:
        title = raw.get('title', '').strip()
        if not title or title in seen:
            continue
        seen.add(title)

        # Diagnostic: log the raw fields so we can verify Timely's format.
        # Remove once the day-shift regression is confirmed fixed.
        print(
            f"[TimelyDebug] title={title!r} "
            f"start_datetime={raw.get('start_datetime')!r} "
            f"start_utc_datetime={raw.get('start_utc_datetime')!r}",
            flush=True,
        )

        # Future filter — compare UTC to UTC so we don't care about local offsets.
        if future_only:
            try:
                from dateutil import parser as _dp2
                utc_str = raw.get('start_utc_datetime') or raw.get('start_datetime') or ''
                if utc_str:
                    dt_utc = _dp2.parse(str(utc_str).strip())
                    if dt_utc.tzinfo is None:
                        dt_utc = dt_utc.replace(tzinfo=_tz.utc)
                    if dt_utc < now_utc:
                        continue
            except Exception:
                pass

        # Build ISO strings in Central time from the UTC source of truth.
        # zoneinfo handles DST boundaries correctly (previous code hard-coded
        # -05:00 for all of March–November, which is wrong in early March and
        # late November — and, more importantly, it re-labeled a UTC value as
        # local when the "CONFIRMED" comment turned out to be wrong, shifting
        # the displayed day forward by one.)
        date_str = _timely_to_central_iso(raw, 'start_datetime', 'start_utc_datetime')
        end_str  = _timely_to_central_iso(raw, 'end_datetime',   'end_utc_datetime')

        venue_data = raw.get('venue', {})
        venue = venue_data.get('name', '') if isinstance(venue_data, dict) else ''
        if not venue:
            venue = source_name

        desc = raw.get('description', '') or raw.get('excerpt', '')
        if desc:
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()[:200]

        image = raw.get('featured_image', {})
        image_url = image.get('url', '') if isinstance(image, dict) else (image if isinstance(image, str) else '')

        events.append({
            'title': title,
            'date': date_str,
            'end_date': end_str,
            'venue': venue,
            'description': desc,
            'source_url': raw.get('url', '') or raw.get('canonical_url', ''),
            'tickets_url': raw.get('ticket_url', '') or raw.get('custom_ticket_url', ''),
            'image_url': image_url,
            'source': source_name,
        })

    return events


def clean_timely_title(title: str) -> str:
    if not title or len(title) < 20:
        return title
    matches = list(re.finditer(r'[a-z][A-Z]', title))
    if matches:
        potential_title = title[:matches[0].start() + 1]
        if len(potential_title) >= 10 or potential_title.count(' ') >= 2:
            return potential_title.strip()
    words = title.split()
    if len(words) >= 2:
        seen_words = {}
        for i, word in enumerate(words):
            wl = word.lower()
            if wl in seen_words and i > 1:
                return ' '.join(words[:seen_words[wl]]).strip()
            seen_words[wl] = i
    if len(title) > 50 and title.count(' ') < 5:
        if ' - ' in title:
            parts = title.split(' - ')
            if len(parts[0]) >= 10:
                return parts[0].strip()
        truncated = title[:50]
        last_space = truncated.rfind(' ')
        if last_space > 20:
            return truncated[:last_space].strip()
    return title


def extract_timely_from_html(soup, base_url: str, source_name: str) -> list:
    events = []
    seen = set()

    containers = []
    for sel in ['.timely-event', '[data-event-id]', '.timely-calendar .event',
                '.tc-event', '.timely-agenda-event', '.agenda-event']:
        containers.extend(soup.select(sel))

    if not containers:
        # Only run the loose fallback if the page actually looks like a Timely
        # widget. Without this guard, [class*="event-list"] matches SeatEngine's
        # .event-list-item and every href*="event" on the page gets treated as
        # an event, producing false positives (e.g. "Click Showtime & Buy").
        has_timely_marker = bool(
            soup.select_one('[class*="timely-"], [class*="tc-event"], [data-timely], [data-calendar-id]')
        )
        if has_timely_marker:
            for group in soup.select('[class*="agenda"], [class*="event-list"]'):
                containers.extend(group.select('a[href*="event"], div[class*="event"], li'))

    for container in containers:
        title_el = (
                container.select_one('.timely-title, .event-title, [class*="title"]:not([class*="subtitle"])') or
                container.select_one('h1, h2, h3, h4')
        )
        if not title_el:
            link_el = container.select_one('a[href]')
            if link_el:
                title_el = link_el
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if title and len(title) > 30:
            mid = len(title) // 2
            if title[:mid].strip() == title[mid:].strip():
                title = title[:mid].strip()

        if not title or len(title) < 3 or title in seen:
            continue
        skip_words = ['read full', 'more', 'view all', 'click here', 'get a timely', 'powered by', 'buy tickets']
        if any(s in title.lower() for s in skip_words):
            continue
        if len(title) > 50 and title.count(' ') < 3:
            continue

        title = clean_timely_title(title)
        if not title or len(title) < 3:
            continue
        seen.add(title)

        date_el = container.select_one('.timely-date, .event-date, time, [class*="date"]:not([class*="update"])')
        date_str = ''
        if date_el:
            date_str = date_el.get('datetime', '')
            if not date_str:
                dt_text = date_el.get_text(strip=True)
                dm = extract_date_from_text(dt_text)
                tm = extract_time_from_text(dt_text)
                if dm:
                    date_str = f"{dm} @ {tm}" if tm else dm
                elif tm:
                    date_str = tm

        if not date_str:
            ct = container.get_text(' ', strip=True)
            date_str = extract_date_from_text(ct) or ''
            ts = extract_time_from_text(ct)
            if ts:
                date_str = f"{date_str} @ {ts}" if date_str else ts

        link = ''
        le = container if container.name == 'a' else container.select_one('a[href]')
        if le:
            href = le.get('href', '')
            if href and not href.startswith('#') and 'javascript:' not in href:
                link = urljoin(base_url, href)

        events.append({
            'title': title, 'date': date_str, 'source_url': link,
            'source': source_name, 'venue': source_name,
        })

    return events


async def extract_timely(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    params = detect_timely(html, url)
    if not params:
        return [], False

    print(f"[Timely] Detected calendar ID: {params['id']}", flush=True)
    raw_events = await fetch_timely_api(params['id'], referer_url=url)

    if raw_events:
        print(f"[Timely] Fetched {len(raw_events)} total events from API", flush=True)
        events = parse_timely_events(raw_events, source_name, future_only)
        if future_only:
            print(f"[Timely] {len(events)} upcoming events after date filter", flush=True)
        return events, True

    # HTML fallback: re-enabled because fetchers.py now sets Playwright's
    # timezone_id to America/Chicago. The widget renders in Central, so the
    # dates extracted from the DOM are correct.
    print(f"[Timely] API returned 0 events, trying HTML extraction...", flush=True)
    soup = BeautifulSoup(html, 'html.parser')
    events = extract_timely_from_html(soup, url, source_name)
    print(f"[Timely] Found {len(events)} events from HTML", flush=True)
    return events, True


# ============================================================================
# BOK CENTER
# ============================================================================

KNOWN_BOK_VENUES = {
    'bokcenter.com': True,
    'www.bokcenter.com': True,
}


async def fetch_bok_center_events(max_pages: int = 20) -> list:
    all_events = []
    offset = 0
    per_page = 6

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        while offset < max_pages * per_page:
            url = f"https://www.bokcenter.com/events/events_ajax/{offset}?category=0&venue=0&team=0&exclude=&per_page={per_page}&came_from_page=event-list-page"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                raw_text = resp.text
                try:
                    html = json.loads(raw_text)
                except:
                    html = raw_text

                if not html or len(html.strip()) < 50:
                    break

                soup = BeautifulSoup(html, 'html.parser')
                titles = soup.select('h3 a')
                if not titles:
                    titles = soup.select('a[href*="/events/detail/"]')
                if not titles:
                    break

                for title_link in titles:
                    title = title_link.get_text(strip=True)
                    href = title_link.get('href', '')
                    if not title or not href or '/events/detail/' not in href:
                        continue

                    container = title_link.parent
                    date_str = ''
                    for _ in range(8):
                        if container is None:
                            break
                        spans = container.find_all('span', recursive=True)
                        span_texts = [s.get_text(strip=True) for s in spans]
                        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                        if any(m in ' '.join(span_texts) for m in months):
                            date_str = re.sub(r'\s+', ' ', ' '.join(span_texts)).strip()
                            break
                        container = container.parent

                    full_url = href if href.startswith('http') else f"https://www.bokcenter.com{href}"
                    all_events.append({'title': title, 'date': date_str, 'source_url': full_url})

                offset += per_page
            except Exception as e:
                print(f"BOK Center API error at offset {offset}: {e}")
                break

    return all_events


def _parse_bok_multi_day_date(date_str: str) -> tuple:
    """FIX: Parse multi-day date strings like 'Mar 6-7'. Returns (start, end)."""
    multi_day = re.search(
        r'([A-Za-z]+)\s+(\d{1,2})\s*[-\u2013]\s*(\d{1,2})(?:,?\s*(\d{4}))?',
        date_str
    )
    if multi_day:
        month = multi_day.group(1)
        start_day = multi_day.group(2)
        end_day = multi_day.group(3)
        year = multi_day.group(4) or str(datetime.now().year)
        return f"{month} {start_day}, {year}", f"{month} {end_day}, {year}"
    return date_str, ''


async def extract_bok_center(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    try:
        domain = urlparse(url).netloc.lower()
        if domain not in KNOWN_BOK_VENUES:
            return [], False
    except:
        return [], False

    print(f"[BOK Center] Detected BOK Center site")
    raw_events = await fetch_bok_center_events()
    print(f"[BOK Center] Fetched {len(raw_events)} events from API")

    seen = set()
    events = []
    for event in raw_events:
        url_key = event.get('source_url', '')
        if url_key in seen:
            continue
        seen.add(url_key)

        date_str = event.get('date', '')
        if date_str:
            date_str = re.sub(r'\s+', ' ', date_str).strip()

            year_match = re.search(r'\d{4}', date_str)
            if year_match:
                date_str = date_str[:year_match.end()]

            # Deduplicate repeated day/month names
            for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                if date_str.count(day) >= 2:
                    first_idx = date_str.find(day)
                    second_idx = date_str.find(day, first_idx + 1)
                    if second_idx > first_idx:
                        date_str = date_str[second_idx:]
                    break

            for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'June', 'July']:
                if date_str.count(month) >= 2:
                    first_idx = date_str.find(month)
                    second_idx = date_str.find(month, first_idx + 1)
                    if second_idx > first_idx:
                        date_str = date_str[second_idx:]
                    break

            date_str = re.sub(r',(\S)', r', \1', date_str)
            date_str = re.sub(r'([A-Za-z])(\d)', r'\1 \2', date_str)
            date_str = re.sub(r'\s+', ' ', date_str).strip()
            date_str = re.sub(r'\s*On Sale.*$', '', date_str, flags=re.IGNORECASE)

            # FIX: Parse multi-day dates and preserve end date
            start_date, end_date = _parse_bok_multi_day_date(date_str)
            event['date'] = date_str.strip()
            if end_date:
                event['end_date'] = end_date

        event['source'] = source_name
        event['venue'] = 'BOK Center'
        events.append(event)

    return events, True