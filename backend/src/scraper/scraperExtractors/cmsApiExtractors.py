"""
Locate918 Scraper - CMS & Platform API Extractors
===================================================
Extractors for CMS platforms and JSON APIs:
  - Expo Square (Saffire CMS)
  - Eventbrite API
  - Simpleview CMS (VisitTulsa)
  - SiteWrench CMS (Discovery Lab, Gathering Place)
  - RecDesk (Tulsa Parks)
  - TicketLeap (Belafonte)
  - Circle Cinema (detail-page showtime scraper)
  - LibNet (Tulsa City-County Library)
  - Philbrook Museum (WP Tessitura AJAX)
  - Tulsa PAC (Ticketmaster Account Manager)
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
# EXPO SQUARE (SAFFIRE CMS)
# ============================================================================

async def extract_expo_square_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    if 'exposquare.com' not in url.lower():
        return [], False

    print(f"[Expo Square] Detected Expo Square URL, using Saffire API...")
    events = []
    seen_event_ids = set()

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

            days_url = 'https://www.exposquare.com/services/eventsservice.asmx/GetEventDays'
            days_payload = {
                'day': '', 'startDate': '', 'endDate': '',
                'categoryID': 0, 'currentUserItems': 'false',
                'tagID': 0, 'keywords': '%25%25', 'isFeatured': 'false',
                'fanPicks': 'false', 'myPicks': 'false', 'pastEvents': 'false',
                'allEvents': 'false', 'memberEvents': 'false', 'memberOnly': 'false',
                'showCategoryExceptionID': 0, 'isolatedSchedule': 0,
                'customFieldFilters': [], 'searchInDescription': True
            }

            print(f"[Expo Square] Fetching event dates...")
            days_response = await client.post(days_url, json=days_payload, headers=headers)
            if days_response.status_code != 200:
                print(f"[Expo Square] GetEventDays failed: {days_response.status_code}")
                return [], False

            all_dates = days_response.json().get('d', [])
            today = datetime.now()
            max_date = today + timedelta(days=365)

            future_dates = []
            for ds in all_dates:
                try:
                    dt = datetime.strptime(ds, '%m/%d/%Y')
                    if today <= dt <= max_date:
                        future_dates.append(ds)
                except:
                    continue

            print(f"[Expo Square] Found {len(future_dates)} future event dates (from {len(all_dates)} total)")

            batch_size = 30
            details_url = 'https://www.exposquare.com/services/eventsservice.asmx/GetEventDaysByList'

            for i in range(0, len(future_dates), batch_size):
                batch = future_dates[i:i+batch_size]
                details_payload = {
                    'dates': ','.join(batch), 'day': '', 'categoryID': 0, 'tagID': 0,
                    'keywords': '%25%25', 'isFeatured': 'false', 'fanPicks': 'false',
                    'pastEvents': 'false', 'allEvents': 'false', 'memberEvents': 'false',
                    'memberOnly': 'false', 'showCategoryExceptionID': 0, 'isolatedSchedule': 0,
                    'customFieldFilters': [], 'searchInDescription': True
                }

                details_response = await client.post(details_url, json=details_payload, headers=headers)
                if details_response.status_code != 200:
                    continue

                days = details_response.json().get('d', {}).get('Days', [])
                for day in days:
                    unique_events = day.get('Unique', [])
                    if not unique_events:
                        times = day.get('Times', [])
                        if times:
                            unique_events = times[0].get('Unique', [])

                    for evt in unique_events:
                        try:
                            event_id = evt.get('EventID')
                            if event_id in seen_event_ids:
                                continue
                            seen_event_ids.add(event_id)

                            title = evt.get('Name', '')
                            if not title:
                                continue

                            date_range = evt.get('EventDateRangeString', '')
                            date_str = day.get('DateString', '')

                            end_date_str = None
                            if date_range and '-' in date_range:
                                try:
                                    parts = date_range.split('-')
                                    if len(parts) == 2:
                                        from dateutil import parser as date_parser
                                        end_date_str = str(date_parser.parse(parts[1].strip(), fuzzy=True).date())
                                except:
                                    pass

                            image_url = evt.get('ImageOrVideoThumbnailWithPath', '')
                            if 'no_img_available' in image_url:
                                image_url = ''

                            description = evt.get('ShortDescription', '') or evt.get('LongDescription', '') or ''
                            if not description and date_range:
                                description = date_range

                            locations = evt.get('Locations', [])
                            venue = 'Expo Square'
                            if locations and isinstance(locations, list) and len(locations) > 0:
                                loc = locations[0]
                                if isinstance(loc, dict):
                                    venue = loc.get('Name', 'Expo Square') or 'Expo Square'

                            categories = []
                            for cat in (evt.get('CategoryMaps', []) or []):
                                if isinstance(cat, dict) and cat.get('CategoryName'):
                                    categories.append(cat['CategoryName'])

                            events.append({
                                'title': title,
                                'start_time': date_str,
                                'end_time': end_date_str,
                                'venue': venue,
                                'venue_address': '4145 E 21st St, Tulsa, OK 74114',
                                'location': 'Tulsa',
                                'description': description[:500] if description else '',
                                'source_url': evt.get('DetailURL', ''),
                                'image_url': image_url,
                                'source_name': source_name or 'Expo Square',
                                'categories': categories,
                                'outdoor': False,
                                'family_friendly': False,
                            })
                        except Exception as e:
                            print(f"[Expo Square] Error parsing event: {e}")
                            continue

                await asyncio.sleep(0.2)

            print(f"[Expo Square] Successfully extracted {len(events)} unique events")
            return events, True

    except Exception as e:
        print(f"[Expo Square] Error: {e}")
        import traceback
        traceback.print_exc()
        return [], False


# ============================================================================
# EVENTBRITE API
# ============================================================================

EVENTBRITE_PLACES = {
    'tulsa': '101714291',
    'oklahoma-city': '101714211',
    'broken-arrow': '101712989',
}


async def extract_eventbrite_api_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    if 'eventbrite.com' not in url.lower():
        return [], False

    print(f"[Eventbrite API] Detected Eventbrite URL, using API...")
    place_id = EVENTBRITE_PLACES['tulsa']
    for city, pid in EVENTBRITE_PLACES.items():
        if city in url.lower():
            place_id = pid
            break

    events = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Referer': 'https://www.eventbrite.com/',
                'Origin': 'https://www.eventbrite.com',
            }

            print(f"[Eventbrite API] Fetching events for place ID {place_id}...")
            response = await client.post(
                'https://www.eventbrite.com/home/api/search/',
                json={'placeId': place_id, 'tab': 'all'},
                headers=headers
            )

            if response.status_code != 200:
                print(f"[Eventbrite API] API returned status {response.status_code}")
                return [], False

            raw_events = response.json().get('events', [])
            print(f"[Eventbrite API] Got {len(raw_events)} events")

            for evt in raw_events:
                try:
                    title = evt.get('name', '')
                    if not title:
                        continue

                    start_date = evt.get('start_date', '')
                    start_time = evt.get('start_time', '00:00:00')
                    date_str = f"{start_date}T{start_time}" if start_date else ''

                    venue_data = evt.get('primary_venue', {}) or {}
                    venue_name = venue_data.get('name', 'TBA')
                    address_data = venue_data.get('address', {}) or {}
                    parts = []
                    for k in ['address_1', 'city', 'region', 'postal_code']:
                        if address_data.get(k):
                            parts.append(address_data[k])
                    venue_address = ', '.join(parts)

                    ticket_info = evt.get('ticket_availability', {}) or {}
                    is_free = ticket_info.get('is_free', False)
                    price_min = price_max = None
                    if is_free:
                        price_min = price_max = 0
                    else:
                        for key, target in [('minimum_ticket_price', 'price_min'), ('maximum_ticket_price', 'price_max')]:
                            p = ticket_info.get(key, {})
                            if p:
                                try:
                                    val = float(p.get('major_value', 0))
                                    if target == 'price_min':
                                        price_min = val
                                    else:
                                        price_max = val
                                except (ValueError, TypeError):
                                    pass

                    image_url = (evt.get('image', {}) or {}).get('url', '')
                    event_url = evt.get('url', '')
                    if not event_url and evt.get('id'):
                        event_url = f"https://www.eventbrite.com/e/{evt['id']}"

                    if evt.get('is_online_event'):
                        venue_name = 'Online Event'

                    end_date = evt.get('end_date', '')
                    end_time = evt.get('end_time', '')
                    end_datetime = f"{end_date}T{end_time}" if end_date and end_time else (end_date or '')

                    events.append({
                        'title': title,
                        'start_time': date_str,
                        'end_time': end_datetime or None,
                        'venue': venue_name,
                        'venue_address': venue_address,
                        'location': address_data.get('city', 'Tulsa'),
                        'description': (evt.get('summary', '') or '')[:500],
                        'source_url': event_url,
                        'image_url': image_url,
                        'price_min': price_min,
                        'price_max': price_max,
                        'is_free': is_free,
                        'source_name': source_name or 'Eventbrite',
                        'categories': [],
                        'outdoor': False,
                        'family_friendly': False,
                    })
                except Exception as e:
                    print(f"[Eventbrite API] Error parsing event: {e}")

            print(f"[Eventbrite API] Successfully extracted {len(events)} events")
            return events, True

    except Exception as e:
        print(f"[Eventbrite API] Error: {e}")
        return [], False


# ============================================================================
# SIMPLEVIEW CMS (VisitTulsa)
# ============================================================================

KNOWN_SIMPLEVIEW_SITES = {
    'www.visittulsa.com': 'Visit Tulsa',
    'visittulsa.com': 'Visit Tulsa',
}


async def extract_simpleview_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain not in KNOWN_SIMPLEVIEW_SITES:
            if 'simpleview' not in html.lower() and 'plugins_events' not in html.lower():
                return [], False
    except:
        return [], False

    print(f"[Simpleview] Detected Simpleview CMS site: {domain}")
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    try:
        events = await _fetch_simpleview_events(base_url, source_name, future_only)
        return events, True
    except Exception as e:
        print(f"[Simpleview] Error fetching events: {e}")
        return [], True


async def _fetch_simpleview_events(base_url: str, source_name: str, future_only: bool = True) -> list:
    events = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        token_url = f"{base_url}/plugins/core/get_simple_token/"
        print(f"[Simpleview] Fetching token...")
        try:
            token_resp = await client.get(token_url)
            token = token_resp.text.strip()
            if not token or len(token) > 100:
                return []
            print(f"[Simpleview] Got token: {token[:20]}...")
        except Exception as e:
            print(f"[Simpleview] Failed to get token: {e}")
            return []

        from datetime import timezone as _tz
        import time as _time
        utc_offset_seconds = -_time.timezone if not _time.daylight else -_time.altzone
        local_tz = timezone(timedelta(seconds=utc_offset_seconds))
        now_local = datetime.now(local_tz)
        midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_utc = midnight_local.astimezone(timezone.utc)

        # Paginate in 30-day windows matching what the browser sends
        all_events_collected = []
        window_start = midnight_utc
        total_days = 365
        days_fetched = 0

        batch_size = 100
        seen_ids = set()

        while days_fetched < total_days:
            window_end = window_start + timedelta(days=30)
            start_date = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            end_date = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            skip = 0
            window_fetched = 0
            window_total = 0

            while True:
                query = {
                    "filter": {
                        "active": True,
                        "$and": [{"categories.catId": {"$in": [
                            "4","7","12","19","53","22","24","36",
                            "26","18","32","54","35","37","41","49","21","55","44","45"
                        ]}}],
                        "date_range": {
                            "start": {"$date": start_date},
                            "end": {"$date": end_date}
                        }
                    },
                    "options": {
                        "limit": batch_size, "skip": skip, "count": True,
                        "castDocs": False,
                        "fields": {
                            "_id": 1, "location": 1, "date": 1, "startDate": 1, "endDate": 1,
                            "recurrence": 1, "recurType": 1, "latitude": 1, "longitude": 1,
                            "media_raw": 1, "recid": 1, "title": 1, "url": 1, "description": 1,
                            "categories": 1, "listing.primary_category": 1, "listing.title": 1,
                            "listing.url": 1, "address": 1,
                        },
                        "hooks": [],
                        "sort": {"date": 1, "rank": 1, "title_sort": 1}
                    }
                }

                json_str = json.dumps(query, separators=(',', ':'))
                api_url = f"{base_url}/includes/rest_v2/plugins_events_events_by_date/find/?json={json_str}&token={token}"

                print(f"[Simpleview] Fetching events (skip={skip})...")
                try:
                    resp = await client.get(api_url)
                    data = resp.json()
                except Exception as e:
                    print(f"[Simpleview] Request/parse error: {e}. Status: {resp.status_code if resp else 'N/A'}. Raw: {resp.text[:300] if resp else 'N/A'}")
                    break  # break inner, outer will advance window

                docs = []
                total_count = 0

                if isinstance(data, dict):
                    if 'docs' in data and isinstance(data['docs'], dict):
                        inner = data['docs']
                        docs = inner.get('docs', [])
                        total_count = inner.get('count', 0)
                    else:
                        docs = data.get('docs', [])
                        total_count = data.get('count', 0)
                    if not docs:
                        docs = data.get('results', []) or data.get('items', [])
                elif isinstance(data, list):
                    docs = data
                    total_count = len(data)

                if not docs:
                    print(f"[Simpleview] Empty docs. HTTP {resp.status_code}. Raw response: {str(data)[:500]}")
                    break

                if window_total == 0:
                    window_total = total_count
                print(f"[Simpleview] Got {len(docs)} events (window total: {window_total})")

                for doc in docs:
                    try:
                        if not isinstance(doc, dict):
                            continue
                        title = doc.get('title', '')
                        if not title:
                            continue

                        # Deduplicate across windows by _id
                        doc_id = str(doc.get('_id', '') or doc.get('recid', ''))
                        if doc_id and doc_id in seen_ids:
                            continue
                        if doc_id:
                            seen_ids.add(doc_id)

                        date_str = ''
                        if doc.get('startDate'):
                            sd = doc['startDate']
                            date_str = sd['$date'] if isinstance(sd, dict) and '$date' in sd else sd
                        else:
                            date_str = doc.get('date', '')

                        # Find external URL
                        event_url = ''
                        for key in ['ticketUrl', 'ticket_url', 'externalUrl', 'external_url',
                                    'registrationUrl', 'registration_url', 'eventUrl', 'event_url',
                                    'websiteUrl', 'website_url', 'link']:
                            v = doc.get(key)
                            if v:
                                event_url = v
                                break

                        listing = doc.get('listing')
                        if not event_url and listing and isinstance(listing, dict):
                            for key in ['ticketUrl', 'externalUrl', 'websiteUrl', 'website', 'web']:
                                v = listing.get(key)
                                if v:
                                    event_url = v
                                    break

                        if event_url:
                            if not event_url.startswith('http'):
                                if event_url.startswith('www.') or '.' in event_url:
                                    event_url = 'https://' + event_url
                        else:
                            event_url = doc.get('url', '')
                            if event_url and not event_url.startswith('http'):
                                event_url = base_url + event_url

                        venue = ''
                        loc = doc.get('location', '')
                        if loc and isinstance(loc, str):
                            venue = loc
                        if not venue and listing and isinstance(listing, dict):
                            venue = listing.get('title', '')

                        image_url = ''
                        media_raw = doc.get('media_raw')
                        if media_raw and isinstance(media_raw, list) and len(media_raw) > 0:
                            m = media_raw[0]
                            image_url = m.get('mediaurl', '') or m.get('url', '') if isinstance(m, dict) else (m if isinstance(m, str) else '')

                        description = doc.get('description', '')
                        if isinstance(description, str):
                            description = re.sub(r'<[^>]+>', '', description)[:500]
                        else:
                            description = ''

                        categories = []
                        for cat in (doc.get('categories') or []):
                            if isinstance(cat, dict) and cat.get('catName'):
                                categories.append(cat['catName'])
                            elif isinstance(cat, str):
                                categories.append(cat)

                        address = doc.get('address', '')
                        if not isinstance(address, str):
                            address = ''

                        venue_website = ''
                        if listing and isinstance(listing, dict):
                            for key in ['website', 'websiteUrl', 'web', 'url_website', 'externalUrl']:
                                v = listing.get(key)
                                if v:
                                    venue_website = v
                                    break
                            if venue_website and not venue_website.startswith('http'):
                                if venue_website.startswith('www.') or '.' in venue_website:
                                    venue_website = 'https://' + venue_website

                        events.append({
                            'title': title,
                            'start_time': date_str,
                            'end_time': doc.get('endDate'),
                            'source_url': event_url or f"{base_url}/events/",
                            'source_name': source_name,
                            'venue': venue or source_name,
                            'venue_address': address,
                            'location': 'Tulsa',
                            'description': description,
                            'image_url': image_url,
                            'categories': categories,
                            'outdoor': False,
                            'family_friendly': False,
                            '_venue_website': venue_website,
                        })
                    except Exception as e:
                        continue

                window_fetched += len(docs)
                skip += batch_size
                if window_total > 0 and window_fetched >= window_total:
                    break
                if len(docs) < batch_size:
                    break
                await asyncio.sleep(0.3)

            # Advance to next 30-day window
            window_start = window_end
            days_fetched += 30
            await asyncio.sleep(0.3)

        print(f"[Simpleview] Total events fetched: {len(events)}")

    return events


# ============================================================================
# SITEWRENCH CMS
# ============================================================================

async def extract_sitewrench_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple:
    is_sitewrench = (
            'sitewrench' in html.lower() or
            'swCalendarV2' in html or
            'CalendarListEvent' in html or
            'event-card__info__header' in html or
            'calendar-listings' in html or
            ('cal-' in html and 'pageSize' in html)
    )
    if not is_sitewrench:
        return [], False

    print(f"[SiteWrench] Detected SiteWrench CMS on {url}")

    # Support both classic token= pattern and newer apiToken: pattern (Gathering Place)
    token_match = (
            re.search(r"apiToken\s*:\s*['\"]([a-f0-9]{30,50})['\"]", html) or
            re.search(r"token[=:]\s*['\"]?([a-f0-9]{30,50})", html)
    )
    siteid_match = (
            re.search(r"siteId\s*:\s*(\d+)", html) or
            re.search(r"siteId[=:]\s*['\"]?(\d+)", html, re.IGNORECASE)
    )
    pagepart_match = (
            re.search(r"pagePartId\s*:\s*(\d+)", html) or
            re.search(r'calendars/(\d+)/', html) or
            re.search(r'cal-(\d{4,8})-', html) or
            re.search(r'PagePartId["\s:]+(\d+)', html)
    )

    if not (token_match and siteid_match and pagepart_match):
        print(f"[SiteWrench] Could not find API config")
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('.event-card')
        if cards:
            print(f"[SiteWrench] Falling back to rendered HTML: {len(cards)} cards")
            events = []
            parsed_base = urlparse(url)
            site_base = f"{parsed_base.scheme}://{parsed_base.netloc}"
            for card in cards:
                h3 = card.select_one('h3')
                if not h3:
                    continue
                title = h3.get_text(strip=True)
                if not title or title.lower() == 'read more':
                    continue
                date_p = card.select_one('.event-card__info__header p')
                date_str = date_p.get_text(strip=True) if date_p else ''
                link_el = card.select_one('a.event-card__link')
                link = urljoin(site_base, link_el.get('href', '')) if link_el else ''
                events.append({'title': title, 'date': date_str, 'source_url': link, 'source': source_name, 'venue': source_name})
            return events, True
        return [], True

    token = token_match.group(1)
    site_id = siteid_match.group(1)
    page_part_id = pagepart_match.group(1)

    print(f"[SiteWrench] Config: pagePartId={page_part_id}, siteId={site_id}")
    try:
        events = await _fetch_sitewrench_events(page_part_id, token, site_id, source_name, url, future_only)
        return events, True
    except Exception as e:
        print(f"[SiteWrench] Error: {e}")
        return [], True


async def _fetch_sitewrench_events(page_part_id, token, site_id, source_name, base_url, future_only=True):
    today = datetime.now()
    start = today.strftime('%Y-%m-%d')
    end = (today + timedelta(days=365)).strftime('%Y-%m-%d')
    cutoff = today.replace(hour=0, minute=0, second=0, microsecond=0)

    events = []
    page = 1

    parsed_base = urlparse(base_url)
    site_base = f"{parsed_base.scheme}://{parsed_base.netloc}"

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        while True:
            api_url = (
                f"https://api.sitewrench.com/pageparts/calendars/{page_part_id}/render"
                f"?token={token}&siteid={site_id}&start={start}&end={end}"
                f"&sortBy=startDate&page={page}&pageSize=20&days=365"
            )
            resp = await client.get(api_url)
            resp.raise_for_status()
            data = resp.json()

            content_html = data.get('Content', '')
            if not content_html:
                break

            soup = BeautifulSoup(content_html, 'html.parser')

            # ── Detect template: classic .event-card vs newer .CalendarListEvent ──
            cards = soup.select('.CalendarListEvent')
            template = 'new'
            if not cards:
                cards = soup.select('.event-card')
                template = 'classic'
            if not cards:
                break

            print(f"[SiteWrench] Page {page}: {len(cards)} cards (template={template})")

            for card in cards:
                if template == 'new':
                    # ── New CalendarListEvent template (e.g. Gathering Place) ──
                    title_el = card.select_one('.CalendarListEvent__title')
                    title = title_el.get_text(strip=True) if title_el else ''
                    if not title:
                        continue

                    dt_el = card.select_one('.CalendarListEvent__date_time')
                    dt_raw = dt_el.get_text(strip=True) if dt_el else ''
                    # Format: "March 21, 2026 @ 12:00 PM - 5:00 PM" or "March 22, 2026"
                    start_dt, end_dt = _sitewrench_parse_datetime(dt_raw)
                    if not start_dt:
                        continue

                    if future_only and start_dt < cutoff:
                        continue

                    loc_el = card.select_one('.CalendarListEvent__location')
                    location = loc_el.get_text(separator=' ', strip=True) if loc_el else ''
                    location = re.sub(r'\s+', ' ', location).strip()

                    img_el = card.select_one('.EventFeaturedImage')
                    img_src = ''
                    if img_el:
                        src = img_el.get('src', '')
                        img_src = urljoin(site_base, src) if src else ''

                    link_el = card.select_one('a[href]')
                    link = urljoin(site_base, link_el['href']) if link_el else base_url

                    events.append({
                        'title':           title,
                        'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                        'end_time':        end_dt.strftime('%Y-%m-%dT%H:%M:%S') if end_dt else '',
                        'venue':           location or source_name,
                        'venue_address':   '2650 S John Williams Way E, Tulsa, OK 74114',
                        'description':     '',
                        'source_url':      link,
                        'image_url':       img_src,
                        'source_name':     source_name,
                        'categories':      _sitewrench_categories(title, location),
                        'outdoor':         True,
                        'family_friendly': True,
                    })

                else:
                    # ── Classic event-card template (Discovery Lab etc.) ──
                    h3 = card.select_one('h3')
                    if not h3:
                        continue
                    title = h3.get_text(strip=True)
                    if not title or title.lower() == 'read more':
                        continue
                    date_p = card.select_one('.event-card__info__header p')
                    date_str = date_p.get_text(strip=True) if date_p else ''
                    link_el = card.select_one('a.event-card__link')
                    link = urljoin(site_base, link_el.get('href', '')) if link_el else ''
                    events.append({
                        'title': title, 'date': date_str,
                        'source_url': link, 'source': source_name, 'venue': source_name
                    })

            # Pagination: parse total from CalendarListSummary, fall back to next-arrow detection
            summary_el = soup.select_one('.CalendarListSummary')
            total_match = re.search(r'of\s+(\d+)\s+Events', summary_el.get_text() if summary_el else '')
            if total_match:
                total = int(total_match.group(1))
                page_size = len(cards)
                fetched_so_far = (page - 1) * 20 + page_size
                if fetched_so_far >= total:
                    break
            else:
                # Fallback: look for next page link
                has_next = bool(
                    soup.select_one('.CalendarListPager__arrow:last-child a') or
                    soup.select_one('.next-prev-nav__item--next a') or
                    (soup.select_one('.CalendarListPager__arrow') and
                     page < len(soup.select('.CalendarListPager__item')))
                )
                if not has_next:
                    break
            page += 1
            if page > 25:
                break
            await asyncio.sleep(0.3)

    print(f"[SiteWrench] Total: {len(events)} events")
    return events


def _sitewrench_categories(title: str, location: str) -> list[str]:
    """Infer categories from Gathering Place / SiteWrench event title and location."""
    t = (title + ' ' + location).lower()
    if any(w in t for w in ['dog', 'pet']):
        return ['Pets', 'Outdoor', 'Community']
    if any(w in t for w in ['fitness', 'yoga', 'run', 'walk', 'sport', 'swat', 'volleyball', 'basketball']):
        return ['Sports', 'Fitness', 'Outdoor']
    if any(w in t for w in ['music', 'concert', 'band', 'jazz', 'blues', 'perform', 'social hour', 'sunset social']):
        return ['Music', 'Entertainment', 'Community']
    if any(w in t for w in ['global gathering', 'cultural', 'heritage', 'international', 'japan', 'ireland', 'africa']):
        return ['Cultural', 'Community', 'Family']
    if any(w in t for w in ['exploration station', 'education', 'science', 'nature', 'math', 'discovery', 'library', 'grow']):
        return ['Education', 'Family', 'Community']
    if any(w in t for w in ['sakura', 'cherry blossom', 'spring break', 'festival', 'celebration']):
        return ['Festival', 'Community', 'Family']
    if any(w in t for w in ['tiny tulsa', 'kids', 'youth', 'child', 'family']):
        return ['Family', 'Education', 'Community']
    if any(w in t for w in ['art', 'exhibit', 'paint', 'draw', 'craft']):
        return ['Arts & Culture', 'Community', 'Family']
    return ['Community', 'Parks & Recreation', 'Family']


def _sitewrench_parse_datetime(dt_raw: str) -> tuple:
    """
    Parse SiteWrench CalendarListEvent date/time string.

    Handles:
      "March 22, 2026"                        → (date_only, None)
      "March 21, 2026 @ 12:00 PM - 5:00 PM"  → (start_dt, end_dt same day)
      "April 1, 2026 - June 30, 2026"         → (start_dt, end_dt multi-day)
    """
    from dateutil import parser as _dp
    dt_raw = dt_raw.strip()
    if not dt_raw:
        return None, None

    try:
        if '@' in dt_raw:
            # "March 21, 2026 @ 12:00 PM - 5:00 PM"
            date_part, time_part = dt_raw.split('@', 1)
            base_date = _dp.parse(date_part.strip())
            time_part = time_part.strip()

            if '-' in time_part:
                start_time_str, end_time_str = time_part.rsplit('-', 1)
                start_t = _dp.parse(start_time_str.strip())
                end_t   = _dp.parse(end_time_str.strip())
                start_dt = base_date.replace(hour=start_t.hour, minute=start_t.minute, second=0)
                end_dt   = base_date.replace(hour=end_t.hour,   minute=end_t.minute,   second=0)
                return start_dt, end_dt
            else:
                start_t = _dp.parse(time_part.strip())
                start_dt = base_date.replace(hour=start_t.hour, minute=start_t.minute, second=0)
                return start_dt, None

        elif ' - ' in dt_raw:
            # "April 1, 2026 - June 30, 2026" multi-day range
            parts = dt_raw.split(' - ', 1)
            start_dt = _dp.parse(parts[0].strip())
            end_dt   = _dp.parse(parts[1].strip())
            return start_dt, end_dt

        else:
            # "March 22, 2026" simple date
            return _dp.parse(dt_raw), None

    except Exception:
        return None, None


# ============================================================================
# RECDESK (Tulsa Parks)
# ============================================================================

async def extract_recdesk_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from RecDesk calendar API (used by Tulsa Parks & Rec).
    Detects recdesk.com in URL, parses captured API data from Playwright.
    Deduplicates 700+ schedule entries to ~100 unique events by EventId.
    """
    if 'recdesk.com' not in url.lower():
        return [], False

    print(f"[RecDesk] Detected RecDesk calendar site")

    events = []
    seen_event_ids = set()

    # Parse captured API data injected by Playwright
    soup = BeautifulSoup(html, 'html.parser')
    api_scripts = soup.select('script[type="recdesk-api-data"]')

    for script in api_scripts:
        try:
            raw_text = script.get_text()
            data = json.loads(raw_text)

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Debug: show what keys the API actually returns
                print(f"[RecDesk] API response keys: {list(data.keys())[:10]}")

                # ASP.NET often wraps response in "d" which may be a JSON string
                if 'd' in data and isinstance(data['d'], str):
                    try:
                        inner = json.loads(data['d'])
                        if isinstance(inner, list):
                            items = inner
                        elif isinstance(inner, dict):
                            data = inner  # unwrap and continue searching
                            print(f"[RecDesk] Unwrapped 'd' string, inner keys: {list(data.keys())[:10]}")
                    except:
                        pass

                # Try all known RecDesk/ASP.NET wrapper keys
                if not items:
                    for key in ['CalendarItems', 'd', 'Data', 'Result', 'value',
                                'items', 'events', 'Items', 'Events', 'results']:
                        candidate = data.get(key)
                        if isinstance(candidate, list) and len(candidate) > 0:
                            items = candidate
                            print(f"[RecDesk] Found {len(items)} items under key '{key}'")
                            break

                # If still empty, check if any value is a large list
                if not items:
                    for key, val in data.items():
                        if isinstance(val, list) and len(val) > 5:
                            items = val
                            print(f"[RecDesk] Found {len(items)} items under fallback key '{key}'")
                            break

            print(f"[RecDesk] Parsing {len(items)} calendar items")

            # Debug: show first item's keys
            if items and isinstance(items[0], dict):
                print(f"[RecDesk] First item keys: {list(items[0].keys())[:15]}")

            for item in items:
                # Case-insensitive key lookup helper
                def get_ci(d, *keys):
                    """Get first matching key, case-insensitive."""
                    lower_map = {k.lower(): k for k in d.keys()}
                    for k in keys:
                        real_key = lower_map.get(k.lower())
                        if real_key and d.get(real_key):
                            return d[real_key]
                    return None

                event_id = get_ci(item, 'EventId', 'eventId', 'ID', 'id', 'EventID', 'ItemId')
                if event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)

                title = (get_ci(item, 'EventName', 'Title', 'name', 'Name',
                                'Summary', 'summary', 'Subject', 'subject') or '').strip()
                if not title:
                    continue

                # Skip junk entries starting with ! or #
                if title.startswith('!') or title.startswith('#'):
                    continue

                start = get_ci(item, 'StartDate', 'start', 'Start', 'startDate',
                               'EventDate', 'eventDate', 'Date') or ''
                end = get_ci(item, 'EndDate', 'end', 'End', 'endDate') or ''

                date_str = ''
                if start:
                    try:
                        dt = datetime.fromisoformat(str(start).replace('Z', '').split('+')[0])
                        date_str = dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')
                    except:
                        date_str = str(start)

                location = (get_ci(item, 'LocationName', 'Location', 'location',
                                   'FacilityName', 'Facility', 'Room') or source_name)

                description = get_ci(item, 'Description', 'description', 'Notes',
                                     'EventDescription', 'Body') or ''
                if description:
                    description = re.sub(r'<[^>]+>', ' ', description)
                    description = re.sub(r'\s+', ' ', description).strip()[:200]

                # Handle "Multiple Dates and Times" gracefully
                if 'multiple dates' in date_str.lower():
                    date_str = start if start else ''

                events.append({
                    'title': title,
                    'date': date_str,
                    'end_date': end,
                    'venue': location,
                    'description': description,
                    'source_url': url,
                    'source': source_name,
                })

        except Exception as e:
            print(f"[RecDesk] Error parsing API data: {e}")

    print(f"[RecDesk] Extracted {len(events)} unique events from {len(seen_event_ids)} IDs")
    return events, True


# ============================================================================
# TICKETLEAP
# ============================================================================

async def extract_ticketleap_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extract events from TicketLeap React SPA pages (e.g., Belafonte).
    Strategy 1: "Get Tickets" buttons -> walk up DOM to card container
    Strategy 2: Direct /tickets/ links as fallback
    Parses ordinal dates ("Mar 13th, 2026") with suffix stripping.
    """
    if 'ticketleap.com' not in url.lower():
        return [], False

    print(f"[TicketLeap] Detected TicketLeap site")

    soup = BeautifulSoup(html, 'html.parser')
    events = []
    seen = set()

    # Strategy 1: Find "Get Tickets" buttons and walk up to event cards
    ticket_buttons = soup.select('a[href*="/tickets/"], button')
    for btn in ticket_buttons:
        btn_text = btn.get_text(strip=True).lower()
        if 'ticket' not in btn_text and 'buy' not in btn_text:
            continue

        # Walk up to find event card container
        container = btn
        for _ in range(6):
            parent = container.parent
            if not parent or parent.name in ['body', 'html']:
                break
            container = parent
            # Stop if container has a heading - likely the event card
            if container.select_one('h1, h2, h3, h4'):
                break

        title_el = container.select_one('h1, h2, h3, h4')
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or title in seen:
            continue
        seen.add(title)

        # Extract date - look for ordinal dates like "Mar 13th, 2026"
        container_text = container.get_text(' ', strip=True)
        date_str = ''

        # Strip ordinal suffixes for parsing
        clean_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', container_text)
        date_str = extract_date_from_text(clean_text) or ''
        time_str = extract_time_from_text(container_text)
        if time_str:
            date_str = f"{date_str} @ {time_str}" if date_str else time_str

        # Extract price from "Starts at $XX.XX" pattern
        price_match = re.search(r'[Ss]tarts?\s+at\s+\$?([\d.]+)', container_text)
        price = price_match.group(1) if price_match else ''

        # Get ticket link
        ticket_link = container.select_one('a[href*="/tickets/"]')
        ticket_url = ''
        if ticket_link:
            href = ticket_link.get('href', '')
            ticket_url = href if href.startswith('http') else urljoin(url, href)

        events.append({
            'title': title,
            'date': date_str,
            'source_url': ticket_url or url,
            'tickets_url': ticket_url,
            'source': source_name,
            'venue': source_name,
            'price': price,
        })

    # Strategy 2 fallback: Direct /tickets/ links
    if not events:
        for link in soup.select('a[href*="/tickets/"]'):
            href = link.get('href', '')
            title = link.get_text(strip=True)

            if not title or len(title) < 3 or title in seen:
                continue
            if title.lower() in ['get tickets', 'buy tickets', 'tickets']:
                continue
            seen.add(title)

            full_url = href if href.startswith('http') else urljoin(url, href)
            events.append({
                'title': title,
                'date': '',
                'source_url': full_url,
                'tickets_url': full_url,
                'source': source_name,
                'venue': source_name,
            })

    print(f"[TicketLeap] Extracted {len(events)} events")
    return events, True


# ============================================================================
# CIRCLE CINEMA — async, detail-page scraper
# ============================================================================
# Architecture:
#   1. Parse homepage HTML for all film cards (title, info_url, ticket_url,
#      image_url, description, rating, runtime, release_date)
#   2. For each film, fetch its /movies-events/<slug> detail page
#   3. Parse the SHOWTIMES section: "Day M/D: time1, time2"
#   4. Emit one NormalizedEvent per showtime (future only, capped at 14 days
#      out for regular films with many showtimes)
#
# Showtime format on detail pages:
#   "Thu 3/19: 1:00p, 5:00p"
#   "Fri 3/20: 1:20p, 3:20p, 5:20p"
#   "Sat 3/21: 3:00p"
#   "Thu 4/23: 5pm preshow in lobby\n6:30pm films"  ← skip preshow, use film time
# ============================================================================

# Regex for one showtime line: "Day M/D: time, time, time"
_CC_SHOWTIME_LINE_RE = re.compile(
    r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+(\d{1,2}/\d{1,2}):\s*(.+)',
    re.IGNORECASE,
)

# Matches individual time tokens: "1:00p", "5:00pm", "6:30pm", "7pm"
_CC_TIME_TOKEN_RE = re.compile(
    r'\b(\d{1,2}(?::\d{2})?)\s*(am|pm|p|a)\b',
    re.IGNORECASE,
)

# Lines to skip (preshow / reception / doors)
_CC_SKIP_KEYWORDS = ('preshow', 'pre-show', 'reception', 'lobby', 'doors', 'open')


def _cc_parse_time_token(token: str) -> tuple | None:
    """Parse '1:00p' / '6:30pm' / '7pm' → (hour24, minute)."""
    m = _CC_TIME_TOKEN_RE.match(token.strip())
    if not m:
        return None
    time_part = m.group(1)
    meridiem = m.group(2).lower()
    if ':' in time_part:
        h, mn = int(time_part.split(':')[0]), int(time_part.split(':')[1])
    else:
        h, mn = int(time_part), 0
    if meridiem in ('pm', 'p') and h < 12:
        h += 12
    elif meridiem in ('am', 'a') and h == 12:
        h = 0
    return h, mn


def _cc_parse_showtimes_text(showtimes_text: str, year: int) -> list:
    """
    Parse the SHOWTIMES block text from a Circle Cinema detail page.
    Returns list of datetime objects (future only relative to now).

    Handles:
      "Thu 3/19: 1:00p, 5:00p"
      "Thu 4/23: 5pm preshow in lobby\n6:30pm films"  → picks 6:30pm
    """
    now = datetime.now()
    results = []

    # Split into lines; a new showtime line starts with a day name
    lines = re.split(r'\n|\r|(?=(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+\d)', showtimes_text)

    for line in lines:
        line = line.strip()
        day_match = _CC_SHOWTIME_LINE_RE.match(line)
        if not day_match:
            continue

        date_str = day_match.group(1)   # e.g. "3/19"
        times_str = day_match.group(2)  # e.g. "1:00p, 5:00p"

        # Parse M/D into a date
        try:
            month, day = int(date_str.split('/')[0]), int(date_str.split('/')[1])
            # If month is earlier than current month, it's next year
            dt_date = datetime(year, month, day).date()
            if dt_date < now.date():
                continue
        except (ValueError, IndexError):
            continue

        # Handle multi-line time entries (e.g. preshow + film)
        # Collect all time tokens, skipping lines that contain skip keywords
        time_tokens = []
        sub_lines = re.split(r'[,\n]', times_str)
        for sub in sub_lines:
            sub_lower = sub.lower()
            # If this sub-line has a skip keyword, skip it
            if any(kw in sub_lower for kw in _CC_SKIP_KEYWORDS):
                continue
            for token_match in _CC_TIME_TOKEN_RE.finditer(sub):
                full_token = token_match.group(0)
                parsed = _cc_parse_time_token(full_token)
                if parsed:
                    time_tokens.append(parsed)

        # If ALL sub-lines were skipped (e.g. only preshow listed), try taking last time
        if not time_tokens:
            for token_match in _CC_TIME_TOKEN_RE.finditer(times_str):
                full_token = token_match.group(0)
                parsed = _cc_parse_time_token(full_token)
                if parsed:
                    time_tokens.append(parsed)
            # Use only the last one (most likely the main film after preshow)
            if time_tokens:
                time_tokens = [time_tokens[-1]]

        for h, mn in time_tokens:
            try:
                dt = datetime(year, month, day, h, mn)
                if dt > now:
                    results.append(dt)
            except ValueError:
                continue

    return results


def _cc_extract_card_meta(h6_title_elem, soup_root) -> dict:
    """
    Extract metadata for one Circle Cinema film card by walking UP from the
    title h6 until we find a container whose text includes a date, then
    scanning that container with regex.
    """
    result = {
        'release_date': '', 'rating': '', 'runtime': '', 'genre': '',
        'description': '', 'ticket_url': '', 'info_url': '', 'image_url': '',
    }

    # Walk up to find card container (has a date in its text)
    container = h6_title_elem.parent
    card = container
    for _ in range(8):
        if container is None:
            break
        text = container.get_text(' ', strip=True)
        if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}', text):
            card = container
            break
        container = getattr(container, 'parent', None)

    card_text = card.get_text(' ', strip=True) if card else ''

    # Release date — M/D/YY or "Mar 21, 2026"
    dm = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', card_text)
    if dm:
        result['release_date'] = dm.group(1)
    else:
        dm2 = re.search(
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+\d{4})',
            card_text, re.IGNORECASE
        )
        if dm2:
            result['release_date'] = dm2.group(1)

    # Rating
    rm = re.search(r'RATING\s+([A-Za-z0-9 +\-]+?)(?:\s+(?:GENRE|RUN TIME|RELEASE|$))', card_text)
    if rm:
        val = rm.group(1).strip()
        if val and val.lower() not in ('​', '', 'genre'):
            result['rating'] = val

    # Runtime
    rtm = re.search(r'(\d+\s*h(?:r|rs|ours?)?\s*\d*\s*m(?:in)?|\d+\s*m(?:in)?)', card_text, re.IGNORECASE)
    if rtm:
        result['runtime'] = rtm.group(1).strip()

    # Genre
    gm = re.search(r'GENRE\s+([^\n\r]+?)(?:\s+(?:RUN TIME|RELEASE|RATING|TICKETS|INFO|$))', card_text)
    if gm:
        g = gm.group(1).strip()
        if g and g not in ('​', ''):
            result['genre'] = g

    # Description — first paragraph with real content
    title_text = h6_title_elem.get_text(strip=True)
    for p in (card.find_all('p') if card else []):
        t = p.get_text(strip=True)
        if t and t != title_text and len(t) > 20 and t not in ('​', ''):
            result['description'] = t[:300]
            break

    # Ticket / info links and image
    title_words = {w for w in re.split(r'[^a-z0-9]+', title_text.lower()) if len(w) > 2}
    info_candidates = []
    for link in (card.find_all('a', href=True) if card else []):
        href = link['href']
        if 'easy-ware-ticketing.com' in href:
            result['ticket_url'] = result['ticket_url'] or href
        elif '/movies-events/' in href:
            from urllib.parse import unquote
            full = href if href.startswith('http') else urljoin('https://www.circlecinema.org', href)
            slug_words = set(re.split(r'[^a-z0-9]+', unquote(full).lower()))
            overlap = len(title_words & slug_words)
            info_candidates.append((overlap, full))
    if info_candidates:
        info_candidates.sort(key=lambda x: -x[0])
        result['info_url'] = info_candidates[0][1]

    # Fallback: construct info_url from title if DOM scan missed it
    # Pattern: lowercase title, spaces→hyphens, special chars URL-encoded
    if not result['info_url']:
        from urllib.parse import quote
        slug = quote(h6_title_elem.get_text(strip=True).lower().replace(' ', '-'), safe='-')
        result['info_url'] = f'https://www.circlecinema.org/movies-events/{slug}'

    for img in (card.find_all('img', src=True) if card else []):
        if 'wixstatic.com' in img['src']:
            result['image_url'] = img['src']
            break

    return result


def _cc_parse_homepage_cards(soup, base_url: str) -> list:
    """
    Parse the Circle Cinema homepage for all film cards.
    Titles are in <h3> (Now Showing) and <h4> (Special Screenings, Coming Soon).
    <h6> tags are labels (RELEASE DATE, RATING, RUN TIME) — NOT titles.
    Returns list of dicts: {title, info_url, ticket_url, image_url,
                             description, rating, runtime, release_date}
    """
    cards = []
    seen_titles = set()

    SKIP_TITLES = {
        'NOW SHOWING', 'FEATURE FILMS NOW SHOWING', 'SPECIAL SCREENINGS',
        'COMING SOON', 'FEATURE FILMS COMING SOON', 'COMING ATTRACTIONS',
        'CONTACT US', 'FOLLOW US', 'SIGN UP FOR NEWS & UPDATES',
        'NEWSLETTER', 'FILM SCHEDULE', 'RENTALS', 'WHO WE ARE', 'WHAT WE DO',
        'GET INVOLVED', 'FILM FESTIVALS', 'TICKET HUB', 'MEMBERSHIP',
        'GIFT CARDS', 'DONATE', 'BACK TO ALL FILMS', 'NEXT FILM',
        'RELEASE DATE', 'RATING', 'GENRE', 'RUN TIME', 'TICKETS', 'INFO',
        'PRIVACY POLICY', 'TERMS & CONDITIONS', 'FOLLOW US:',
        'SIGN UP FOR NEWS AND UPDATES', 'SUBSCRIBE',
    }
    LABEL_TEXTS = {'release date', 'rating', 'genre', 'run time', 'tickets', 'info'}

    # Titles are h3 (Now Showing) and h4 (Special Screenings / Coming Soon)
    # h6 tags are LABELS, not titles
    for title_el in soup.find_all(['h3', 'h4']):
        title = title_el.get_text(strip=True).strip('\u201c\u201d"')
        if not title or len(title) < 4:
            continue
        if title.upper() in SKIP_TITLES:
            continue
        if title.lower().rstrip(':') in LABEL_TEXTS:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)

        # Walk UP from the title element to find the card container
        # that contains h6 metadata (RELEASE DATE, RATING, RUN TIME).
        # Wix nests deeply, so we go up to 12 levels.
        container = title_el.parent
        card_container = container
        for _ in range(12):
            if not container or container.name in ['body', 'html']:
                break
            if container.find('h6'):
                card_container = container
                break
            container = getattr(container, 'parent', None)
        container = card_container

        # Extract h6 label/value pairs (RELEASE DATE → value, RATING → value, etc.)
        h6_tags = container.find_all('h6') if container else []

        release_date = rating = runtime = ''
        for i, h6 in enumerate(h6_tags):
            txt = h6.get_text(strip=True).upper().rstrip(':')
            val = h6_tags[i + 1].get_text(strip=True) if i + 1 < len(h6_tags) else ''
            val = val.strip('\u200b').strip()
            if not val or val.upper() in ('RELEASE DATE', 'RATING', 'RUN TIME', 'GENRE', 'N/A', ''):
                continue
            if txt == 'RELEASE DATE' and not release_date:
                release_date = val
            elif txt == 'RATING' and not rating:
                rating = val
            elif 'RUN TIME' in txt and not runtime:
                runtime = val

        # Description — first <p> with meaningful content
        description = ''
        if container:
            for p in container.find_all('p'):
                t = p.get_text(strip=True)
                if t and len(t) > 20 and t != title:
                    description = t[:300]
                    break

        # Links — ticket (eventsByMovie) and info (/movies-events/ or /coming-soon/)
        ticket_url = info_url = ''
        if container:
            for a in container.find_all('a', href=True):
                href = a['href']
                if 'easy-ware-ticketing.com/eventsByMovie' in href and not ticket_url:
                    ticket_url = href
                elif ('/movies-events/' in href or '/coming-soon/' in href or '/event-details/' in href) and not info_url:
                    info_url = href if href.startswith('http') else f'https://www.circlecinema.org{href}'

        if not info_url:
            from urllib.parse import quote
            slug = quote(title.lower().replace(' ', '-'), safe='-')
            info_url = f'https://www.circlecinema.org/movies-events/{slug}'

        # Image
        image_url = ''
        if container:
            for img in container.find_all('img', src=True):
                src = img.get('src', '')
                if src and src.startswith('http'):
                    image_url = src
                    break

        cards.append({
            'title':        title,
            'info_url':     info_url,
            'ticket_url':   ticket_url,
            'image_url':    image_url,
            'description':  description,
            'rating':       rating,
            'runtime':      runtime,
            'release_date': release_date,
        })

    return cards
async def _cc_fetch_detail_page(info_url: str) -> str:
    """Fetch a Circle Cinema film detail page. Returns page text or ''."""
    if not info_url or not info_url.startswith('http'):
        return ''
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(info_url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        print(f"[CircleCinema] Error fetching {info_url}: {e}")
    return ''


def _cc_extract_showtimes_from_page(page_text: str, year: int) -> list:
    """
    Extract showtime datetimes from a detail page's plain text.
    Looks for the SHOWTIMES block and parses it.
    """
    # Find the SHOWTIMES block
    idx = page_text.upper().find('SHOWTIMES')
    if idx == -1:
        return []

    # Grab text from SHOWTIMES to RELEASE DATE (end of showtimes block)
    block_start = idx + len('SHOWTIMES')
    block_end_markers = ['RELEASE DATE', 'RATING', 'RUN TIME', 'BACK TO ALL']
    block_end = len(page_text)
    for marker in block_end_markers:
        pos = page_text.upper().find(marker, block_start)
        if pos != -1 and pos < block_end:
            block_end = pos

    showtimes_block = page_text[block_start:block_end]
    return _cc_parse_showtimes_text(showtimes_block, year)


async def extract_circle_cinema_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Async Circle Cinema extractor. Fetches individual film pages for real showtimes.
    Returns (events, was_detected).
    """
    if 'circlecinema' not in url.lower():
        if 'circlecinema.easy-ware-ticketing.com' not in html or 'wixstatic.com' not in html:
            return [], False

    print(f"[CircleCinema] Detected Circle Cinema, parsing homepage cards...")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    cards = _cc_parse_homepage_cards(soup, url or 'https://www.circlecinema.org')
    print(f"[CircleCinema] Found {len(cards)} film cards on homepage")

    if not cards:
        return [], True

    now = datetime.now()
    year = now.year
    events = []

    # Fetch detail pages concurrently (max 5 at a time)
    semaphore = asyncio.Semaphore(5)

    async def fetch_card(card):
        async with semaphore:
            detail_text = await _cc_fetch_detail_page(card['info_url'])
            return card, detail_text

    results = await asyncio.gather(*[fetch_card(c) for c in cards])

    for card, detail_text in results:
        title        = card['title']
        info_url     = card['info_url']
        ticket_url   = card['ticket_url']
        image_url    = card['image_url']
        rating       = card['rating']
        runtime      = card['runtime']
        description  = card['description']

        # Build description with metadata
        meta_parts = []
        if rating and rating not in ('\u200b', ''):
            meta_parts.append(f"Rated {rating}")
        if runtime and runtime not in ('\u200b', ''):
            meta_parts.append(runtime)
        full_desc = (
            f"{description} ({' | '.join(meta_parts)})"
            if description and meta_parts
            else description or ' | '.join(meta_parts) or 'Showing at Circle Cinema.'
        )

        source_url = info_url or ticket_url or url or 'https://www.circlecinema.org'

        if detail_text:
            showtimes = _cc_extract_showtimes_from_page(detail_text, year)

            if showtimes:
                # One card per film — next upcoming showtime
                dt = showtimes[0]
                print(f"  [CircleCinema] {title}: next showtime {dt.strftime('%m/%d %I:%M%p')}")
                event = {
                    'title': title,
                    'description': full_desc,
                    'start_time': dt.strftime('%Y-%m-%dT%H:%M:%S'),
                    'time_estimated': False,
                    'source_url': source_url,
                    'venue': 'Circle Cinema',
                    'venue_address': '10 S. Lewis Ave, Tulsa, OK 74104',
                    'image_url': image_url,
                    'categories': ['Film', 'Arts'],
                }
                if ticket_url:
                    event['ticket_url'] = ticket_url
                events.append(event)
                continue

        # No detail page or no showtimes found — fall back to release date, time_estimated
        release_date = card.get('release_date', '')
        start_time = None
        if release_date:
            # Parse M/D/YY or "Mar 21, 2026"
            m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})$', release_date.strip())
            if m:
                mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if yr < 100: yr += 2000
                try:
                    start_time = datetime(yr, mo, dy, 0, 0).strftime('%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    pass
            if not start_time:
                for fmt in ('%b %d, %Y', '%B %d, %Y', '%b %d %Y'):
                    try:
                        start_time = datetime.strptime(release_date.strip(), fmt).strftime('%Y-%m-%dT%H:%M:%S')
                        break
                    except ValueError:
                        continue

        if start_time and future_only:
            try:
                if datetime.fromisoformat(start_time) < now.replace(hour=0, minute=0, second=0, microsecond=0):
                    print(f"  [CircleCinema] {title}: past, skipping")
                    continue
            except Exception:
                pass

        print(f"  [CircleCinema] {title}: no detail showtimes, time_estimated=True ({release_date})")
        events.append({
            'title': title,
            'description': full_desc,
            'start_time': start_time or '',
            'time_estimated': True,
            'source_url': source_url,
            'venue': 'Circle Cinema',
            'venue_address': '10 S. Lewis Ave, Tulsa, OK 74104',
            'image_url': image_url,
            'categories': ['Film', 'Arts'],
        })
        if ticket_url:
            events[-1]['ticket_url'] = ticket_url

    print(f"[CircleCinema] Total: {len(events)} events")
    return events, True


# ============================================================================
# TULSA CITY-COUNTY LIBRARY (LibNet CMS)
# ============================================================================

async def extract_libnet_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extractor for Tulsa City-County Library (LibNet CMS).
    Hits clean JSON API directly — the fetched HTML is ignored entirely.
    Detection: any URL containing tulsalibrary.org or tccl.libnet.info.

    API endpoint:
        GET https://events.tulsalibrary.org/eeventcaldata
            ?event_type=0
            &req={"private":false,"date":"YYYY-MM-DD","days":7,...}

    Returns a dict with numeric string keys; values are full event objects.
    Scrapes 7 days from today — designed for a weekly scrape cadence.
    Virtual-only events are skipped.
    All 918-area branches (Bixby, Broken Arrow, Owasso, Collinsville,
    Glenpool, etc.) are included via the single API call.
    """
    if 'tulsalibrary.org' not in url.lower() and 'tccl.libnet.info' not in url.lower():
        return [], False

    print(f"[LibNet] Detected Tulsa City-County Library — using LibNet JSON API...")

    today = datetime.now(timezone.utc).date()
    api_url = (
        "https://events.tulsalibrary.org/eeventcaldata"
        f"?event_type=0"
        f'&req={{"private":false,"date":"{today.isoformat()}","days":7,"locations":[],"ages":[],"types":[]}}'
    )

    events = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                print(f"[LibNet] API returned {resp.status_code}")
                return [], True  # detected but failed

            data = resp.json()
            # API returns a dict with numeric string keys — flatten to list
            raw_events = list(data.values()) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            print(f"[LibNet] API returned {len(raw_events)} raw events")

            for item in raw_events:
                if not isinstance(item, dict):
                    continue

                title = (item.get('title') or '').strip()
                if not title:
                    continue

                # Skip virtual-only locations
                location = item.get('location') or ''
                library  = item.get('library') or ''
                if 'virtual' in location.lower() or 'virtual' in library.lower():
                    continue

                # Timestamps — prefer raw fields, fall back to event_start/end
                start_time = item.get('raw_start_time') or item.get('event_start') or ''
                end_time   = item.get('raw_end_time')   or item.get('event_end')   or ''

                # Derive end_date string (YYYY-MM-DD) from end_time for FutureFilter
                end_date = ''
                if end_time:
                    try:
                        from dateutil import parser as _dp
                        end_date = str(_dp.parse(str(end_time)).date())
                    except Exception:
                        end_date = ''

                # Build canonical event URL from id field
                event_id  = item.get('id') or item.get('event_id') or ''
                event_url = (
                    f"https://tccl.libnet.info/event/{event_id}"
                    if event_id
                    else (item.get('url') or '')
                )

                description = (item.get('description') or '')[:500]
                venue_name  = library or location or 'Tulsa City-County Library'

                events.append({
                    'title':       title,
                    'start_time':  str(start_time),
                    'end_time':    str(end_time) if end_time else '',
                    'end_date':    end_date,
                    'venue':       venue_name,
                    'location':    location,
                    'description': description,
                    'source_url':  event_url,
                    'source_name': source_name or 'Tulsa City-County Library',
                    'categories':  [],
                    'outdoor':     False,
                    'family_friendly': True,
                })

        print(f"[LibNet] Extracted {len(events)} events (Virtual locations skipped)")
        return events, True

    except Exception as e:
        print(f"[LibNet] Error: {e}")
        import traceback
        traceback.print_exc()
        return [], True  # detected but errored


# ============================================================================
# PHILBROOK MUSEUM OF ART (Custom WP Tessitura Events Manager plugin)
# ============================================================================

async def extract_philbrook_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extractor for Philbrook Museum of Art calendar.
    philbrook.org uses a custom WordPress plugin (wp-tessitura-events-manager)
    that renders events via infinite-scroll AJAX calls to wp-admin/admin-ajax.php.

    Strategy:
      1. Parse 'phil_loadmore_params' JSON from an inline <script> tag in the
         Playwright-fetched HTML — this contains the serialised WP query and
         the total number of pages.
      2. POST to admin-ajax.php with action='paginate_calendar_events' for each
         page (0 … max_page-1), collecting the HTML fragments returned.
      3. Parse every .event-item from those fragments:
           - .event-title  → title
           - .event-month  → month abbreviation ("Mar")
           - .number       → day-of-month string ("20")
           - .event-time   → "Friday, 10:00am"
           - <a href>      → detail URL, which encodes YYYY-MM-DD in its slug
           - <img src>     → image
      4. Build start_time as "YYYY-MM-DD HH:MM" using the year from the URL slug
         so we never have to guess the year.

    Returns (events, detected).
    """
    if 'philbrook.org' not in url.lower():
        return [], False

    print(f"[Philbrook] Detected Philbrook Museum calendar, extracting via admin-ajax...")

    # ── 1. Extract phil_loadmore_params from inline <script> ──
    params_match = re.search(
        r'var\s+phil_loadmore_params\s*=\s*(\{.*?\});\s*(?:/\*|//|<)',
        html, re.DOTALL
    )
    if not params_match:
        # Fallback: broader search
        params_match = re.search(r'var\s+phil_loadmore_params\s*=\s*(\{[^<]+\})', html)

    if not params_match:
        print(f"[Philbrook] Could not find phil_loadmore_params in page HTML")
        return [], True

    try:
        raw_params = params_match.group(1)
        # Unescape forward slashes that WP json_encode adds
        raw_params = raw_params.replace('\\/', '/')
        params = json.loads(raw_params)
    except Exception as e:
        print(f"[Philbrook] Failed to parse phil_loadmore_params: {e}")
        return [], True

    ajax_url  = params.get('ajaxurl', 'https://www.philbrook.org/wp-admin/admin-ajax.php')
    query     = params.get('posts', '')
    max_page  = int(params.get('max_page', 1))
    print(f"[Philbrook] max_page={max_page}, ajaxurl={ajax_url}")

    if not query:
        print(f"[Philbrook] Empty WP query in phil_loadmore_params")
        return [], True

    # ── 2. Paginate through all pages ──
    all_html_fragments = []
    headers = {
        'User-Agent':   'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.philbrook.org/calendar/',
        'Origin':  'https://www.philbrook.org',
    }

    async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
        for page in range(max_page):
            try:
                resp = await client.post(
                    ajax_url,
                    data={
                        'action':  'paginate_calendar_events',
                        'query':   query,
                        'page':    page,
                        'keyword': '',
                        'date':    'all',
                        'style':   'grid',
                    }
                )
                if resp.status_code == 200 and resp.text.strip():
                    all_html_fragments.append(resp.text)
                    print(f"[Philbrook] Page {page}: {len(resp.text)} bytes")
                else:
                    print(f"[Philbrook] Page {page}: HTTP {resp.status_code} or empty — stopping")
                    break
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"[Philbrook] Error fetching page {page}: {e}")
                break

    if not all_html_fragments:
        print(f"[Philbrook] No HTML fragments returned from AJAX")
        return [], True

    # ── 3. Parse every .event-item from all fragments ──
    events = []
    seen = set()
    now = datetime.now()

    for fragment in all_html_fragments:
        soup = BeautifulSoup(fragment, 'html.parser')
        items = soup.select('.event-item')

        for item in items:
            try:
                # Title
                title_el = item.select_one('.event-title')
                title = title_el.get_text(strip=True) if title_el else item.get_text(' ', strip=True)[:80]
                if not title:
                    continue

                # Detail URL — the outer <a> wraps the whole card
                link_el = item.select_one('a[href]')
                detail_url = link_el['href'] if link_el else ''

                # Dedup by URL
                if detail_url and detail_url in seen:
                    continue
                seen.add(detail_url)

                # ── Date from URL slug (most reliable) ──
                # slug pattern: /calendar/some-event-name-2026-03-20/
                slug_date_match = re.search(r'(\d{4}-\d{2}-\d{2})(?:[^0-9]|$)', detail_url)
                if slug_date_match:
                    date_str = slug_date_match.group(1)  # "2026-03-20"
                else:
                    # Fallback: reconstruct from .event-month + .number + current year
                    month_el = item.select_one('.event-month')
                    day_el   = item.select_one('.number')
                    month_txt = month_el.get_text(strip=True) if month_el else ''
                    day_txt   = day_el.get_text(strip=True)   if day_el   else ''
                    if month_txt and day_txt:
                        try:
                            from dateutil import parser as _dp
                            parsed = _dp.parse(f"{month_txt} {day_txt} {now.year}", fuzzy=True)
                            date_str = parsed.strftime('%Y-%m-%d')
                        except Exception:
                            date_str = ''
                    else:
                        date_str = ''

                # ── Time from .event-time ──
                # format: "Friday, 10:00am"  or  "Saturday, 10:00am – 5:00pm"
                time_el   = item.select_one('.event-time')
                time_txt  = time_el.get_text(strip=True) if time_el else ''
                start_time_str = ''
                end_time_str   = ''

                if date_str and time_txt:
                    # Strip leading weekday ("Friday, ")
                    time_body = re.sub(r'^[A-Za-z]+,\s*', '', time_txt)
                    # Split on " – " or " - " for end time
                    time_parts = re.split(r'\s*[–-]\s*', time_body, maxsplit=1)
                    time_start = time_parts[0].strip()
                    time_end   = time_parts[1].strip() if len(time_parts) > 1 else ''
                    try:
                        from dateutil import parser as _dp
                        start_dt = _dp.parse(f"{date_str} {time_start}", fuzzy=True)
                        start_time_str = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
                    except Exception:
                        start_time_str = date_str  # date only
                    if time_end:
                        try:
                            from dateutil import parser as _dp
                            end_dt = _dp.parse(f"{date_str} {time_end}", fuzzy=True)
                            end_time_str = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                        except Exception:
                            end_time_str = ''
                elif date_str:
                    start_time_str = date_str

                # Future filter
                if future_only and start_time_str:
                    try:
                        from dateutil import parser as _dp
                        event_dt = _dp.parse(start_time_str, fuzzy=True).replace(tzinfo=None)
                        cutoff   = now.replace(hour=0, minute=0, second=0, microsecond=0)
                        if event_dt < cutoff:
                            continue
                    except Exception:
                        pass

                # Image
                img_el    = item.select_one('img[src]')
                image_url = img_el['src'] if img_el else ''

                events.append({
                    'title':        title,
                    'start_time':   start_time_str,
                    'end_time':     end_time_str,
                    'venue':        'Philbrook Museum of Art',
                    'venue_address': '2727 S Rockford Rd, Tulsa, OK 74114',
                    'description':  '',
                    'source_url':   detail_url,
                    'image_url':    image_url,
                    'source_name':  source_name or 'Philbrook Museum of Art',
                    'categories':   ['Arts', 'Museum'],
                    'outdoor':      False,
                    'family_friendly': False,
                })

            except Exception as e:
                print(f"[Philbrook] Error parsing event item: {e}")
                continue

    print(f"[Philbrook] Extracted {len(events)} events across {len(all_html_fragments)} pages")
    return events, True

# ============================================================================
# TULSA PAC (Ticketmaster Account Manager — am.ticketmaster.com/tulsapac)
# ============================================================================

# Category mapping from TM majorCategory/minorCategory → friendly tags
_TPAC_CATEGORY_MAP = {
    'ARTS':                'Arts',
    'THEATRE (DRAMA)':     'Theatre',
    'THEATRE (MUSICAL)':   'Theatre',
    'CLASSICAL/SYMPHONIC': 'Classical',
    'JAZZ':                'Jazz',
    'ROCK/POP':            'Concert',
    'COUNTRY':             'Concert',
    'R&B':                 'Concert',
    'FAMILY':              'Family',
    'DANCE':               'Dance',
    'OPERA':               'Opera',
    'COMEDY':              'Comedy',
    'SPOKEN WORD':         'Spoken Word',
}


async def extract_tulsapac_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple[list, bool]:
    """
    Extractor for Tulsa Performing Arts Center (am.ticketmaster.com/tulsapac).

    Uses three public, CORS-open JSON APIs — no browser rendering required.
    This is the authoritative data path: Ticketmaster's bot protection blocks
    Playwright from rendering the React SPA, but the underlying APIs behind
    that SPA accept any request. Browser is never touched.

    Pipeline:
      1) GET  /api/v1/members/events/buy         → ~199 catalog items
      2) GET  /api/admin/v2/events (paginated)   → ~311 detail records w/ dates
      3) GET  /api/admin/v2/venues                → 12 halls for name lookup
      4) Filter catalog to public events         → ~133 performances
      5) Join detail by `code`, enrich w/ venue → output events

    Filter (from public-page visibility logic):
      - efsFlag == "1"
      - type    == "single_event"
      - buyFilter != "0"

    URL guard accepts either am.ticketmaster.com/tulsapac or tulsapac.com —
    the marketing site has no real events but the user may configure either.
    The html argument is ignored entirely.
    """
    url_l = url.lower()
    if 'am.ticketmaster.com/tulsapac' not in url_l and 'tulsapac.com' not in url_l:
        return [], False

    print("[TulsaPAC] Detected — fetching via public JSON APIs (no browser required)")

    base = 'https://am.ticketmaster.com/tulsapac'
    # Neutral browser UA. TM's APIs accept anything but the bot-protection
    # layer on the SPA reads UA, so we play nice here too just in case.
    req_headers = {
        'Accept':          'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'User-Agent':      (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/131.0.0.0 Safari/537.36'
        ),
        'Referer':         f'{base}/buy',
        'Origin':          'https://am.ticketmaster.com',
    }

    async with httpx.AsyncClient(headers=req_headers, timeout=30, follow_redirects=True) as client:

        # ── 1. Catalog: /api/v1/members/events/buy ──
        buy_items: list = []
        try:
            br = await client.get(f'{base}/api/v1/members/events/buy')
            if br.status_code == 200:
                raw = br.json()
                # API returns an indexed object {"0": {...}, "1": {...}} — values() gives us the list.
                if isinstance(raw, dict):
                    buy_items = [v for v in raw.values() if isinstance(v, dict)]
                elif isinstance(raw, list):
                    buy_items = [v for v in raw if isinstance(v, dict)]
                print(f"[TulsaPAC] members/events/buy: {len(buy_items)} catalog items")
            else:
                print(f"[TulsaPAC] members/events/buy returned {br.status_code}")
        except Exception as e:
            print(f"[TulsaPAC] members/events/buy fetch error: {e}")

        # ── 2. Detail + dates: /api/admin/v2/events (paginated) ──
        # Build two indexes because different API versions key the events
        # dict either by integer id OR by performance code. We want both.
        detail_by_code: dict = {}
        detail_by_id:   dict = {}
        for page_num in range(6):  # safety cap; live data is 2 pages
            try:
                params = {'_format': 'json', 'epoch': 'upcoming'}
                if page_num > 0:
                    params['page'] = page_num
                er = await client.get(f'{base}/api/admin/v2/events', params=params)
                if er.status_code != 200:
                    print(f"[TulsaPAC] admin/v2/events page {page_num} → {er.status_code}")
                    break

                edata       = er.json()
                page_events = edata.get('events', {}) or {}
                page_meta   = edata.get('page', {}) or {}
                total_pages = int(page_meta.get('totalPages', 1))

                if isinstance(page_events, dict):
                    for key, ev in page_events.items():
                        if not isinstance(ev, dict):
                            continue
                        code = ev.get('code')
                        if code:
                            detail_by_code[code] = ev
                        # The key itself may also be the code — store that mapping too
                        detail_by_code.setdefault(key, ev)
                        ev_id = ev.get('id')
                        if ev_id is not None:
                            detail_by_id[str(ev_id)] = ev
                elif isinstance(page_events, list):
                    for ev in page_events:
                        if not isinstance(ev, dict):
                            continue
                        code = ev.get('code')
                        if code:
                            detail_by_code[code] = ev
                        ev_id = ev.get('id')
                        if ev_id is not None:
                            detail_by_id[str(ev_id)] = ev

                print(f"[TulsaPAC] admin/v2/events page {page_num}: {len(page_events)} records "
                      f"(cumulative: {len(detail_by_code)} by code, {len(detail_by_id)} by id)")

                if page_num >= total_pages - 1:
                    break
                await asyncio.sleep(0.25)
            except Exception as e:
                print(f"[TulsaPAC] admin/v2/events page {page_num} fetch error: {e}")
                break

        # ── 3. Venue lookup: /api/admin/v2/venues ──
        venue_map: dict = {}
        try:
            vr = await client.get(f'{base}/api/admin/v2/venues', params={'_format': 'json'})
            if vr.status_code == 200:
                vraw = vr.json()
                if isinstance(vraw, dict):
                    for key, v in vraw.items():
                        if not isinstance(v, dict):
                            continue
                        addr   = v.get('address', {}) or {}
                        street = addr.get('streetAddress', {}) or {}
                        line1  = street.get('line1') or ''
                        city   = addr.get('city', 'Tulsa')
                        state  = addr.get('stateCode', 'OK')
                        zcode  = addr.get('postalCode', '') or ''
                        venue_id = str(v.get('id', key))
                        venue_map[venue_id] = {
                            'name':    v.get('name', 'Tulsa PAC'),
                            'address': f"{line1}, {city}, {state} {zcode}".strip(', '),
                            'lat':     (v.get('geoLocation') or {}).get('latitude'),
                            'lng':     (v.get('geoLocation') or {}).get('longitude'),
                        }
                print(f"[TulsaPAC] venues: {len(venue_map)} halls")
        except Exception as e:
            print(f"[TulsaPAC] venues fetch error: {e}")

    # ── 4. Filter + enrich ──
    if not buy_items:
        print("[TulsaPAC] No catalog items — nothing to emit")
        return [], True

    try:
        from dateutil import parser as _dp
        from datetime import timedelta as _td
    except ImportError:
        _dp = None
        _td = None

    cutoff  = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events: list = []
    skipped_filter   = 0
    skipped_nodate   = 0
    skipped_past     = 0
    skipped_cancel   = 0

    for item in buy_items:
        # Public-visibility filter (per Chrome-Claude recon)
        if str(item.get('efsFlag', '')) != '1':
            skipped_filter += 1
            continue
        if item.get('type') != 'single_event':
            skipped_filter += 1
            continue
        if str(item.get('buyFilter', '')) == '0':
            skipped_filter += 1
            continue

        # Join key: "code" is the authoritative field; some API versions use "name"
        code = item.get('code') or item.get('name') or ''
        if not code:
            skipped_nodate += 1
            continue

        detail = detail_by_code.get(code) or {}
        if not detail:
            # Secondary join — try eventId
            ev_id = item.get('eventId')
            if ev_id:
                detail = detail_by_id.get(str(ev_id)) or {}

        date_info = (detail.get('date') or {}) if isinstance(detail, dict) else {}
        dt_str    = date_info.get('datetime') or ''
        date_only = date_info.get('date') or ''
        duration  = date_info.get('duration')

        if not dt_str and not date_only:
            skipped_nodate += 1
            continue

        # Parse datetime
        try:
            if _dp is None:
                raise RuntimeError('dateutil unavailable')
            ev_dt = _dp.parse(dt_str or date_only, fuzzy=True).replace(tzinfo=None)
        except Exception:
            skipped_nodate += 1
            continue

        if detail.get('isCancelled'):
            skipped_cancel += 1
            continue

        if future_only and ev_dt < cutoff:
            skipped_past += 1
            continue

        # Title
        title = (item.get('inetName') or detail.get('name') or '').strip()
        if not title:
            continue
        lower_t = title.lower()
        if 'gift cert' in lower_t or title in ('Gift Certificates', 'Shuttle'):
            continue

        # Venue (Archtics venue IDs in detail.venue.id are the simple 1-12 variety
        # in the admin API, which matches venue_map keys).
        venue_id   = None
        if isinstance(detail.get('venue'), dict):
            venue_id = detail['venue'].get('id')
        venue_obj     = venue_map.get(str(venue_id), {}) if venue_id is not None else {}
        venue_name    = venue_obj.get('name', 'Tulsa Performing Arts Center')
        venue_address = venue_obj.get('address', '110 E 2nd St, Tulsa, OK 74103')
        lat = venue_obj.get('lat')
        lng = venue_obj.get('lng')

        # End time from duration (minutes)
        end_time_str = ''
        if duration and _td is not None:
            try:
                end_time_str = (ev_dt + _td(minutes=int(duration))).strftime('%Y-%m-%dT%H:%M:%S')
            except Exception:
                pass

        # Categories
        major = (detail.get('majorCategory') or '').strip()
        minor = (detail.get('minorCategory') or '').strip()
        cats: list = []
        for key in [major] + minor.split('/'):
            key = key.strip()
            mapped = _TPAC_CATEGORY_MAP.get(key)
            if mapped and mapped not in cats:
                cats.append(mapped)
        if not cats:
            cats = ['Arts', 'Performance']

        # Image — prefer admin detail imagesLinks, fall back to member catalog image
        imgs      = detail.get('imagesLinks') or {}
        image_url = imgs.get('desktop') or imgs.get('mobile') or item.get('image') or ''

        # Event URL: /event/{id} for the detail page; falls back to /buy root
        event_id_out = detail.get('id') or item.get('eventId')
        event_url    = f"{base}/event/{event_id_out}" if event_id_out else f"{base}/buy"

        # Description from members catalog — strip HTML
        description = (item.get('description') or '').strip()
        if description:
            description = re.sub(r'<[^>]+>', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()
            if len(description) > 300:
                description = description[:297] + '…'

        ev_dict = {
            'title':           title,
            'start_time':      dt_str or date_only,
            'end_time':        end_time_str,
            'venue':           venue_name,
            'venue_address':   venue_address,
            'description':     description,
            'source_url':      event_url,
            'image_url':       image_url,
            'source_name':     source_name or 'Tulsa PAC',
            'categories':      cats,
            'outdoor':         False,
            'family_friendly': 'FAMILY' in major.upper() or 'FAMILY' in minor.upper(),
        }
        if lat and lng:
            ev_dict['latitude']  = lat
            ev_dict['longitude'] = lng

        events.append(ev_dict)

    events.sort(key=lambda e: e.get('start_time') or '9999')

    print(
        f"[TulsaPAC] {len(buy_items)} catalog → {len(events)} emitted "
        f"(skipped: {skipped_filter} non-public, {skipped_nodate} no-date, "
        f"{skipped_past} past, {skipped_cancel} cancelled)"
    )
    return events, True


# ============================================================================