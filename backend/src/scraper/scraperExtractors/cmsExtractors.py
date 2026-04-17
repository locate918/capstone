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
    }
    LABEL_TEXTS = {'release date', 'rating', 'genre', 'run time', 'tickets', 'info'}

    # Titles are h3 (Now Showing) and h4 (Special Screenings / Coming Soon)
    title_elems = soup.find_all(['h3', 'h4'])

    for title_el in title_elems:
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

        # Walk up to find card container
        container = title_el
        for _ in range(6):
            parent = container.parent
            if not parent or parent.name in ['body', 'html']:
                break
            # Stop when we have a container with multiple children (the card div)
            if len(list(parent.children)) > 3:
                container = parent
                break
            container = parent

        card_text = container.get_text(' ', strip=True) if container else ''

        # Release date — from h6 siblings after a "RELEASE DATE" label
        release_date = ''
        h6_tags = container.find_all('h6') if container else []
        for i, h6 in enumerate(h6_tags):
            if 'release date' in h6.get_text(strip=True).lower():
                # Next h6 sibling has the date value
                if i + 1 < len(h6_tags):
                    val = h6_tags[i + 1].get_text(strip=True)
                    if val and val not in ('\u200b', '', 'N/A'):
                        release_date = val
                break

        # Rating
        rating = ''
        for i, h6 in enumerate(h6_tags):
            if h6.get_text(strip=True).upper() == 'RATING':
                if i + 1 < len(h6_tags):
                    val = h6_tags[i + 1].get_text(strip=True)
                    if val and val not in ('\u200b', '', 'N/A', 'N/A '):
                        rating = val
                break

        # Runtime
        runtime = ''
        for i, h6 in enumerate(h6_tags):
            if 'run time' in h6.get_text(strip=True).lower():
                if i + 1 < len(h6_tags):
                    val = h6_tags[i + 1].get_text(strip=True)
                    if val and val not in ('\u200b', ''):
                        runtime = val
                break

        # Description — first <p> in the card with real content
        description = ''
        if container:
            for p in container.find_all('p'):
                t = p.get_text(strip=True)
                if t and len(t) > 20 and t != title:
                    description = t[:300]
                    break

        # Ticket URL — easy-ware eventsByMovie link
        ticket_url = ''
        info_url = ''
        if container:
            for a in container.find_all('a', href=True):
                href = a['href']
                if 'easy-ware-ticketing.com/eventsByMovie' in href:
                    ticket_url = ticket_url or href
                elif '/movies-events/' in href or '/coming-soon/' in href or '/event-details/' in href:
                    full = href if href.startswith('http') else f'https://www.circlecinema.org{href}'
                    info_url = info_url or full

        # Fallback info_url from title slug
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
        if 'wixstatic.com' not in html and 'circlecinema' not in html.lower():
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
    Extractor for Tulsa Performing Arts Center (Tulsa PAC).
    Uses the public Ticketmaster Account Manager JSON API — no auth, no Playwright.

    Endpoints:
      GET https://am.ticketmaster.com/tulsapac/api/admin/v2/venues?_format=json
          -> dict of venue_id -> {name, address, geoLocation}

      GET https://am.ticketmaster.com/tulsapac/api/admin/v2/events?_format=json&epoch=upcoming&page=0
      GET https://am.ticketmaster.com/tulsapac/api/admin/v2/events?_format=json&epoch=upcoming&page=1
          -> {events: {id: {...}}, page: {size, totalElements, totalPages, number}}

    The API returns individual *performances* (305 total), not productions.
    We deduplicate by show name, keeping the earliest upcoming performance per
    production — so a 6-night run of "Juliet and Her Romeo" becomes one event
    with the first night's date.

    Event URL: https://am.ticketmaster.com/tulsapac/event/{id}
    """
    if 'am.ticketmaster.com/tulsapac' not in url.lower():
        return [], False

    print(f"[TulsaPAC] Detected Tulsa PAC — using Ticketmaster AM JSON API...")

    base = 'https://am.ticketmaster.com/tulsapac'
    req_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept':     'application/json',
        'Referer':    f'{base}/buy',
        'Origin':     'https://am.ticketmaster.com',
    }

    async with httpx.AsyncClient(headers=req_headers, timeout=30, follow_redirects=True) as client:

        # ── 1. Fetch venue lookup table ──
        venue_map = {}
        try:
            vresp = await client.get(f'{base}/api/admin/v2/venues?_format=json')
            if vresp.status_code == 200:
                for vid, v in vresp.json().items():
                    addr   = v.get('address', {})
                    street = addr.get('streetAddress', {}) or {}
                    line1  = street.get('line1') or ''
                    city   = addr.get('city', 'Tulsa')
                    state  = addr.get('stateCode', 'OK')
                    zcode  = addr.get('postalCode', '')
                    venue_map[int(vid)] = {
                        'name':    v.get('name', 'Tulsa PAC'),
                        'address': f"{line1}, {city}, {state} {zcode}".strip(', '),
                        'lat':     (v.get('geoLocation') or {}).get('latitude'),
                        'lng':     (v.get('geoLocation') or {}).get('longitude'),
                    }
            print(f"[TulsaPAC] Loaded {len(venue_map)} venues")
        except Exception as e:
            print(f"[TulsaPAC] Venue fetch error: {e}")

        # ── 2. Fetch all event pages ──
        all_performances = {}

        for page_num in range(10):  # safety cap — currently 2 pages
            try:
                eresp = await client.get(
                    f'{base}/api/admin/v2/events',
                    params={'_format': 'json', 'epoch': 'upcoming', 'page': page_num}
                )
                if eresp.status_code != 200:
                    print(f"[TulsaPAC] Events page {page_num} returned {eresp.status_code}")
                    break

                data        = eresp.json()
                raw_events  = data.get('events', {})
                page_meta   = data.get('page', {})
                total_pages = int(page_meta.get('totalPages', 1))

                if isinstance(raw_events, dict):
                    all_performances.update(raw_events)
                elif isinstance(raw_events, list):
                    for ev in raw_events:
                        all_performances[str(ev['id'])] = ev

                print(f"[TulsaPAC] Page {page_num}: {len(raw_events)} perfs (total so far: {len(all_performances)})")

                if page_num >= total_pages - 1:
                    break
                await asyncio.sleep(0.3)

            except Exception as e:
                print(f"[TulsaPAC] Error fetching page {page_num}: {e}")
                break

    if not all_performances:
        print(f"[TulsaPAC] No performances returned from API")
        return [], True

    # ── 3. Deduplicate — one event per unique show name, earliest date ──
    now    = datetime.now()
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

    groups: dict = {}
    for perf in all_performances.values():
        if not isinstance(perf, dict):
            continue
        if perf.get('isCancelled'):
            continue
        name = (perf.get('name') or '').strip()
        if not name:
            continue
        if name in ('Gift Certificates', 'Shuttle') or 'gift cert' in name.lower():
            continue
        groups.setdefault(name, []).append(perf)

    events = []
    for name, perfs in groups.items():
        # Sort performances ascending by date
        perfs.sort(key=lambda p: ((p.get('date') or {}).get('date') or '9999-99-99'))
        earliest = perfs[0]

        date_block = earliest.get('date') or {}
        dt_str     = date_block.get('datetime') or date_block.get('date') or ''
        date_only  = date_block.get('date') or ''
        duration   = date_block.get('duration')  # minutes

        # Future filter
        if future_only and (dt_str or date_only):
            try:
                from dateutil import parser as _dp
                ev_dt = _dp.parse(dt_str or date_only, fuzzy=True).replace(tzinfo=None)
                if ev_dt < cutoff:
                    continue
            except Exception:
                pass

        # Compute end_time from duration
        end_time_str = ''
        if dt_str and duration:
            try:
                from dateutil import parser as _dp
                from datetime import timedelta as _td
                start_dt = _dp.parse(dt_str, fuzzy=True).replace(tzinfo=None)
                end_time_str = (start_dt + _td(minutes=int(duration))).strftime('%Y-%m-%dT%H:%M:%S')
            except Exception:
                pass

        # Venue
        venue_id      = (earliest.get('venue') or {}).get('id')
        venue_obj     = venue_map.get(venue_id, {})
        venue_name    = venue_obj.get('name', 'Tulsa Performing Arts Center')
        venue_address = venue_obj.get('address', '110 East 2nd Street, Tulsa, OK 74103')
        lat = venue_obj.get('lat')
        lng = venue_obj.get('lng')

        # Categories
        major = (earliest.get('majorCategory') or '').strip()
        minor = (earliest.get('minorCategory') or '').strip()
        cats  = []
        for key in [major] + minor.split('/'):
            key = key.strip()
            mapped = _TPAC_CATEGORY_MAP.get(key)
            if mapped and mapped not in cats:
                cats.append(mapped)
        if not cats:
            cats = ['Arts', 'Performance']

        # Image
        imgs      = earliest.get('imagesLinks') or {}
        image_url = imgs.get('desktop') or imgs.get('mobile') or ''

        # Event URL
        event_id  = earliest.get('id')
        event_url = f'{base}/event/{event_id}' if event_id else f'{base}/buy'

        # Description: note multi-performance runs
        perf_count  = len(perfs)
        description = f"{perf_count} performance{'s' if perf_count > 1 else ''}" if perf_count > 1 else ''

        ev_dict = {
            'title':          name,
            'start_time':     dt_str or date_only,
            'end_time':       end_time_str,
            'venue':          venue_name,
            'venue_address':  venue_address,
            'description':    description,
            'source_url':     event_url,
            'image_url':      image_url,
            'source_name':    source_name or 'Tulsa PAC',
            'categories':     cats,
            'outdoor':        False,
            'family_friendly': 'FAMILY' in major.upper() or 'FAMILY' in minor.upper(),
        }
        if lat and lng:
            ev_dict['latitude']  = lat
            ev_dict['longitude'] = lng

        events.append(ev_dict)

    events.sort(key=lambda e: e.get('start_time') or '9999')

    print(f"[TulsaPAC] {len(all_performances)} performances -> {len(events)} unique productions")
    return events, True


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
# BRICKTOWN COMEDY CLUB — SeatEngine Platform
# ============================================================================
# Site:    https://bricktowntulsa.com/events
# Method:  httpx — fully server-rendered HTML (SeatEngine CMS, no public API)
# Structure:
#   Each event card: .event-list-item
#     Title:       .el-header a (text)
#     Event URL:   .el-header a[href]  → absolute URL
#     Date range:  .el-date-range      (e.g. "March 22" or "March 27 - March 28")
#     Label:       .event-label        ("Special Event" / "Free Show" / absent)
#     Image:       .el-image img[src]
#     Single show: h6 text             → "Sun Mar 22 2026, 6:00 PM"
#     Multi-show:  .event-times-group  → h6.event-date + a.event-btn-inline per time
#
#   Multi-day headliners (e.g. "Ms. Pat — Fri Mar 27 + Sat Mar 28") emit ONE
#   event per calendar day using the earliest showtime for that day.
#
# Venue:   Bricktown Comedy Club / 5982 S Yale Ave, Tulsa, OK 74135
# Note:    "Bricktown Comedy Club" is the brand name; physically in south Tulsa.
# ============================================================================

_BCC_BASE_URL    = 'https://bricktowntulsa.com'
_BCC_SOURCE_URL  = 'https://bricktowntulsa.com/events'
_BCC_VENUE       = 'Bricktown Comedy Club'
_BCC_ADDR        = '5982 S Yale Ave, Tulsa, OK 74135'

# Datetime formats emitted by SeatEngine's h6 element
_BCC_DT_FORMATS = [
    '%a %b %d %Y, %I:%M %p',   # "Sun Mar 22 2026, 6:00 PM"
    '%a %b %d %Y,  %I:%M %p',  # double-space variant
    '%a, %b %d, %Y %I:%M %p',  # "Fri, Mar 27, 2026 7:00 PM"
    '%a, %b %d, %Y  %I:%M %p', # double-space variant
]

# Formats for the per-day header inside multi-show panels
_BCC_DAY_FORMATS = [
    '%a, %b %d, %Y',  # "Fri, Mar 27, 2026"
    '%a %b %d %Y',    # "Fri Mar 27 2026"
]

# Time-only formats from a.event-btn-inline
_BCC_TIME_FORMATS = [
    '%I:%M %p',   # "7:00 PM"
    ' %I:%M %p',  # leading-space variant
]


def _bcc_parse_dt(text: str) -> datetime | None:
    """Parse SeatEngine full datetime string → naive local datetime."""
    text = text.strip()
    # Collapse multiple spaces to one
    text = re.sub(r'  +', ' ', text)
    for fmt in _BCC_DT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _bcc_parse_day(text: str) -> datetime | None:
    """Parse a day-header string from a multi-show panel → naive date."""
    text = re.sub(r'  +', ' ', text.strip())
    for fmt in _BCC_DAY_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _bcc_parse_time(text: str) -> tuple[int, int] | None:
    """Parse a show-time button text → (hour24, minute)."""
    text = text.strip()
    for fmt in _BCC_TIME_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.hour, dt.minute
        except ValueError:
            pass
    return None


def _bcc_categories(title: str, label: str) -> list[str]:
    cats = ['Comedy', 'Live Entertainment']
    tl = title.lower()
    ll = label.lower()
    if 'open mic' in tl:
        cats.append('Open Mic')
    if 'drag' in tl or 'bingo' in tl:
        cats.append('Drag Show')
    if 'magic' in tl or 'magician' in tl:
        cats.append('Magic Show')
    if 'improv' in tl:
        cats.append('Improv')
    if 'free' in ll:
        cats.append('Free Event')
    return cats


async def extract_bricktown_comedy_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from Bricktown Comedy Club (bricktowntulsa.com).

    The site runs on the SeatEngine ticketing platform.  All event data is
    server-rendered HTML — no public API is exposed.  One event is emitted
    per calendar day for multi-day headliners (using the earliest showtime).
    """
    if 'bricktowntulsa.com' not in url.lower():
        return [], False

    print(f"[BricktownComedy] Detected Bricktown Comedy Club, scraping SeatEngine HTML...")

    # ── Fetch fresh HTML if caller didn't provide it ──────────────────────────
    if not html or 'event-list-item' not in html:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_BCC_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[BricktownComedy] Fetch error: {exc}")
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.event-list-item')
    print(f"[BricktownComedy] Found {len(cards)} event cards")

    today     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events    = []
    seen_keys = set()

    for card in cards:
        # ── Basic card fields ─────────────────────────────────────────────────
        a_tag  = card.select_one('.el-header a')
        if not a_tag:
            continue
        title     = a_tag.get_text(strip=True)
        event_url = _BCC_BASE_URL + a_tag.get('href', '')
        label     = card.select_one('.event-label')
        label_txt = label.get_text(strip=True) if label else ''
        img_tag   = card.select_one('.el-image img')
        image_url = img_tag['src'] if img_tag and img_tag.get('src') else ''

        # ── Determine show datetimes ──────────────────────────────────────────
        show_datetimes: list[datetime] = []  # one entry per distinct day (earliest time)

        time_groups = card.select('.event-times-group')

        if time_groups:
            # Multi-show card: each group = one calendar day
            for group in time_groups:
                day_h6  = group.select_one('h6.event-date') or group.select_one('h6')
                day_dt  = _bcc_parse_day(day_h6.get_text()) if day_h6 else None

                time_links = group.select('a.event-btn-inline')
                first_hm: tuple[int, int] | None = None
                for link in time_links:
                    hm = _bcc_parse_time(link.get_text())
                    if hm is not None:
                        if first_hm is None or (hm[0] * 60 + hm[1]) < (first_hm[0] * 60 + first_hm[1]):
                            first_hm = hm

                if day_dt and first_hm:
                    show_datetimes.append(day_dt.replace(hour=first_hm[0], minute=first_hm[1], second=0))
                elif day_dt:
                    show_datetimes.append(day_dt)

        else:
            # Single-show card: parse from the h6 element
            h6 = card.select_one('h6')
            if h6:
                dt = _bcc_parse_dt(h6.get_text())
                if dt:
                    show_datetimes.append(dt)

        if not show_datetimes:
            print(f"[BricktownComedy] Skipping (no parseable datetime): {title}")
            continue

        # ── Emit one event per day ────────────────────────────────────────────
        for start_dt in show_datetimes:
            if future_only and start_dt.date() < today.date():
                continue

            dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # For multi-day headliners, suffix the title with the weekday
            display_title = title
            if len(show_datetimes) > 1:
                display_title = f"{title} – {start_dt.strftime('%a %b %-d')}"

            events.append({
                'title':           display_title,
                'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time':        '',
                'venue':           _BCC_VENUE,
                'venue_address':   _BCC_ADDR,
                'description':     (
                        f"{title} performing live at Bricktown Comedy Club, Tulsa."
                        + (f" ({label_txt})" if label_txt else '')
                ),
                'source_url':      event_url,
                'image_url':       image_url,
                'source_name':     source_name or _BCC_VENUE,
                'categories':      _bcc_categories(title, label_txt),
                'outdoor':         False,
                'family_friendly': None,
            })
            print(f"[BricktownComedy] Added: {display_title} on {start_dt.strftime('%Y-%m-%d %H:%M')}")

    print(f"[BricktownComedy] Total events: {len(events)}")
    return events, True

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
    cards = soup.select('.rhpSingleEvent.rhp-event__single-event--list')
    print(f"[RHPEvents/{venue_name}] Found {len(cards)} event cards")

    today      = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    work_year  = today.year
    prev_month = 0
    events     = []
    seen_keys  = set()

    for card in cards:
        title_el   = card.select_one('.rhp-event__title--list')
        date_el    = card.select_one('.singleEventDate')
        time_el    = card.select_one('.rhp-event__time-text--list')
        tagline_el = card.select_one('.rhp-event__tagline--list')
        age_el     = card.select_one('.rhp-event__age-restriction--list')
        a_tag      = card.select_one('a[href]')
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
# Method:  httpx — static WP/Elementor page, ~4-5 upcoming events at a time
# Structure:
#   Elementor splits date components into separate text nodes, e.g.:
#     "Wednesday" / "Mar 25, 2026" / "Songwriter's Round..." / "GET TICKETS"
#   Strategy: collect all text nodes, join consecutive short lines that form
#   a date together, then parse DATE→TITLE→DESC blocks.
#   Carney Fest (early May) is a hardcoded computed event pointing to
#   carneyfest.com — it's linked from the nav but not the main events section.
# Venue:   The Church Studio / 304 S Trenton Ave, Tulsa, OK 74120
# ============================================================================

_CS_SOURCE_URL   = 'https://www.thechurchstudio.com/events/'
_CS_VENUE        = 'The Church Studio'
_CS_ADDR         = '304 S Trenton Ave, Tulsa, OK 74120'
_CS_CARNEY_URL   = 'https://carneyfest.com'

_CS_MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}

_CS_DOW_RE = re.compile(
    r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$',
    re.IGNORECASE
)

_CS_MONTH_DAY_YEAR_RE = re.compile(
    r'^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'[\s,.]+(\d{1,2}(?:\s*&\s*\d{1,2})?),?\s*(\d{4})?$',
    re.IGNORECASE
)

# Also match "APRIL 7, 2026" or "JULY 20" directly
_CS_FULL_DATE_RE = re.compile(
    r'^(?:(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+)?'
    r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'[\s,.]+(\d{1,2}(?:\s*&\s*\d{1,2})?),?\s*(\d{4})?$',
    re.IGNORECASE
)

_CS_SKIP_RE = re.compile(
    r'^(GET TICKETS|THE CHURCH STUDIO PRESENTS|PAST EVENTS|DONATE|SHOP|'
    r'MEDIA|SUPPORT|ABOUT|VISIT|LOUNGE|CONTACT|TOURS|MEMBERSHIP|TUNES @ NOON)$',
    re.IGNORECASE
)


def _cs_try_parse_date(line: str, default_year: int) -> datetime | None:
    """Try to parse a single line as a date. Returns None if it isn't one."""
    line = re.sub(r'\s+', ' ', line.strip())
    m = _CS_FULL_DATE_RE.match(line)
    if not m:
        return None
    month_str = m.group(2).lower()[:3]
    month_num = _CS_MONTH_MAP.get(month_str)
    if not month_num:
        return None
    day_part = re.split(r'[\s&]', m.group(3).strip())[0]
    try:
        day = int(day_part)
    except ValueError:
        return None
    year = int(m.group(4)) if m.group(4) else default_year
    try:
        return datetime(year, month_num, day)
    except ValueError:
        return None


async def extract_church_studio_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple[list, bool]:
    """
    Extract events from The Church Studio (thechurchstudio.com/events/).

    Elementor splits date text nodes across multiple lines (e.g. "Wednesday" on
    one line, "Mar 25, 2026" on the next). We collect all non-empty text lines,
    join adjacent DOW + month-day-year fragments, then parse DATE→TITLE→DESC
    blocks. Carney Fest is added as a computed event pointing to carneyfest.com.
    """
    if 'thechurchstudio.com' not in url.lower():
        return [], False

    print(f"[ChurchStudio] Detected The Church Studio events page...")

    if not html or 'thechurchstudio' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_CS_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[ChurchStudio] Fetch error: {exc}")
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Collect ticket links (strip nav first) ────────────────────────────────
    for el in soup.select('nav, header, .header, .fl-page-nav, #fl-page-nav'):
        el.decompose()

    ticket_links: list[str] = []
    seen_tl: set = set()
    for a in soup.select('a[href*="universe.com"], a[href*="etix.com"], a[href*="eventbrite.com"]'):
        href = a.get('href', '')
        if href.startswith('http') and href not in seen_tl:
            seen_tl.add(href)
            ticket_links.append(href)

    # ── Build flat list of text lines from page ───────────────────────────────
    raw_lines = [
        l.strip()
        for l in soup.get_text(separator='\n').splitlines()
        if l.strip()
    ]

    # Trim to upcoming section (between EVENTS header and PAST EVENTS)
    # Use the LAST occurrence of bare "EVENTS" — the first hit is usually the nav link.
    events_idx = -1
    for i, l in enumerate(raw_lines):
        if l.upper() == 'EVENTS':
            events_idx = i
    if events_idx >= 0:
        raw_lines = raw_lines[events_idx + 1:]

    try:
        past_idx  = next(i for i, l in enumerate(raw_lines) if 'PAST EVENTS' in l.upper())
        raw_lines = raw_lines[:past_idx]
    except StopIteration:
        pass

    # ── Join split DOW + "Month Day, Year" pairs ──────────────────────────────
    joined: list[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        # If this line is just a day-of-week and next line is month+day
        if _CS_DOW_RE.match(line) and i + 1 < len(raw_lines):
            next_line = raw_lines[i + 1]
            if _CS_MONTH_DAY_YEAR_RE.match(next_line):
                joined.append(f"{line} {next_line}")
                i += 2
                continue
        joined.append(line)
        i += 1

    # ── Parse DATE → TITLE → DESC blocks ─────────────────────────────────────
    events: list[dict] = []
    seen_keys: set     = set()
    link_idx           = 0

    i = 0
    while i < len(joined):
        line     = joined[i]
        start_dt = _cs_try_parse_date(line, today.year)

        if start_dt:
            title = ''
            desc  = ''
            for j in range(i + 1, min(i + 8, len(joined))):
                candidate = joined[j]
                if _CS_SKIP_RE.match(candidate):
                    continue
                if _cs_try_parse_date(candidate, today.year):
                    break
                if not title and len(candidate) > 4:
                    # Title-case to fix ALL-CAPS headings
                    title = candidate if candidate != candidate.upper() else candidate.title()
                    for k in range(j + 1, min(j + 5, len(joined))):
                        d = joined[k]
                        if not _CS_SKIP_RE.match(d) and not _cs_try_parse_date(d, today.year) and len(d) > 15:
                            desc = d[:250]
                            break
                    break

            if title and (not future_only or start_dt.date() >= today.date()):
                dedup_key = f"{title.lower()[:60]}|{start_dt.strftime('%Y-%m-%d')}"
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    ev_url = ticket_links[link_idx] if link_idx < len(ticket_links) else _CS_SOURCE_URL
                    link_idx += 1
                    events.append({
                        'title':           title,
                        'start_time':      start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                        'end_time':        '',
                        'venue':           _CS_VENUE,
                        'venue_address':   _CS_ADDR,
                        'description':     desc or title,
                        'source_url':      ev_url,
                        'image_url':       '',
                        'source_name':     source_name or _CS_VENUE,
                        'categories':      ['Live Music', 'Live Entertainment', 'Arts & Culture'],
                        'outdoor':         False,
                        'family_friendly': None,
                    })
                    print(f"[ChurchStudio] Added: {title} on {start_dt.strftime('%Y-%m-%d')}")

        i += 1

    print(f"[ChurchStudio] Total events: {len(events)}")
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
# Method:  httpx -- WP/Elementor static HTML
# Structure (text-node order after '2026 Exhibition Calendar'):
#   'January 2-17'          <- date range line
#   '24 Hours of Wonder'    <- title (may appear twice due to Elementor)
#   '24 Hours of Wonder'    <- duplicate -- skip
#   'description text...'  <- description
#   'Contours of Time'      <- second exhibition shares same date range
#   'February 6-March 14'   <- next date range
#   ...
# Date ranges: 'Month D-D', 'Month D-Month D' (start/end)
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

# Matches: 'January 2-17', 'February 6-March 14', 'April 3-May 23', 'August 7-22'
_LA_DATE_RANGE_RE = re.compile(
    r'^(january|february|march|april|may|june|july|august|september|october|november|december)'
    r'\s+(\d{1,2})'
    r'(?:\s*-\s*(?:(january|february|march|april|may|june|july|august|september|october|november|december)\s+)?(\d{1,2}))?'
    r'$',
    re.IGNORECASE
)

# Skip these footer/nav text nodes
_LA_SKIP_TEXTS = {
    'donate', 'quick links', 'contact us', 'who we are', 'opportunities',
    'calendar', 'exhibitions & programming', 'special programs & events',
    'rental', 'weekly newsletter', 'plan your visit by reviewing our amazing exhibition lineup for this year.',
}


def _la_parse_date_range(line: str, year: int) -> tuple:
    m = _LA_DATE_RANGE_RE.match(line.strip())
    if not m:
        return None, None
    start_month = _LA_MONTH_MAP.get(m.group(1).lower())
    start_day   = int(m.group(2))
    if m.group(4):  # has end day
        end_month = _LA_MONTH_MAP.get(m.group(3).lower()) if m.group(3) else start_month
        end_day   = int(m.group(4))
    else:
        end_month = start_month
        end_day   = start_day
    try:
        start_dt = datetime(year, start_month, start_day)
        end_dt   = datetime(year, end_month, end_day)
        if end_dt < start_dt:  # cross-year range
            end_dt = datetime(year + 1, end_month, end_day)
        return start_dt, end_dt
    except (ValueError, TypeError):
        return None, None


async def extract_living_arts_events(
        html: str, source_name: str, url: str = '', future_only: bool = True
) -> tuple:
    """
    Extract exhibitions from Living Arts of Tulsa (livingarts.org/exhibitions/).
    Walks text nodes after the current year section header, pairing each
    date-range line with the title(s) that follow it.
    """
    if 'livingarts.org' not in url.lower():
        return [], False

    print(f'[LivingArts] Detected Living Arts exhibitions page...')

    if not html or 'livingarts' not in html.lower():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(_LA_SOURCE_URL, headers=HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f'[LivingArts] Fetch error: {exc}')
            return [], False

    soup  = BeautifulSoup(html, 'html.parser')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Find the current year section heading (e.g. '2026 Exhibition Calendar')
    target_year = today.year
    year_h2 = None
    for h2 in soup.find_all('h2'):
        if str(target_year) in h2.get_text():
            year_h2 = h2
            break
    if not year_h2:
        # Fallback: try next year
        for h2 in soup.find_all('h2'):
            if str(target_year + 1) in h2.get_text():
                year_h2 = h2
                target_year += 1
                break
    if not year_h2:
        print(f'[LivingArts] Could not find year section')
        return [], False

    # Use get_text() on the full page and slice between year marker and DONATE
    # This is more reliable than find_all_next() on deeply nested Elementor divs.
    full_text = soup.get_text(separator='\n')
    year_marker = f'{target_year} Exhibition Calendar'
    year_idx = full_text.find(year_marker)
    if year_idx == -1:
        print(f'[LivingArts] Year marker not found in text')
        return [], False
    section_text = full_text[year_idx + len(year_marker):]
    # Stop at DONATE or Quick Links (footer)
    for stop in ['DONATE', 'Quick Links', 'Made By Symmetric']:
        idx = section_text.find(stop)
        if idx != -1:
            section_text = section_text[:idx]
            break

    raw_nodes = [l.strip() for l in section_text.splitlines() if l.strip()]

    # De-duplicate consecutive identical lines (Elementor renders titles twice)
    deduped = []
    for t in raw_nodes:
        if deduped and deduped[-1] == t:
            continue
        deduped.append(t)

    print(f'[LivingArts] {len(deduped)} lines in {target_year} section')

    # Walk lines: state machine — date range sets context, next short lines are titles
    # No h4 whitelist needed — we just rely on line length and position.
    events      = []
    seen_keys   = set()
    curr_start  = None
    curr_end    = None

    # Titles are short; descriptions are long. Max title length chosen to fit
    # the longest real title ('Dia de los Muertos Arts Festival & Exhibition' = 45 chars)
    # while excluding leading-description fragments.
    TITLE_MAX_LEN = 50
    TITLE_MIN_LEN = 4

    SKIP_LINES = {
        'plan your visit by reviewing our amazing exhibition lineup for this year.',
        'donate', 'quick links', 'contact us', 'who we are', 'opportunities',
        'calendar', 'exhibitions & programming', 'special programs & events',
        'rental', 'weekly newsletter', 'art market', 'art market.',
        'read more', 'check out the online catalogue here!',
        'check out the catalogue!', 'buy tickets to the fundraising gala here!',
        'sign up', 'accordion #1',
    }
    # Also skip lines starting with sentence-fragments (description continuations)
    SKIP_STARTS = ('by ', 'as a ', 'as an ', 'it ', 'through ', 'this ', 'in ', 'the ')

    i = 0
    while i < len(deduped):
        line = deduped[i]

        # Check if it's a date range
        start_dt, end_dt = _la_parse_date_range(line, target_year)
        if start_dt:
            curr_start = start_dt
            curr_end   = end_dt
            i += 1
            continue

        # Skip junk lines
        if line.lower() in SKIP_LINES or len(line) < TITLE_MIN_LEN:
            i += 1
            continue

        # Must have a date context to emit an event
        if not curr_start:
            i += 1
            continue

        # If line is short enough to be a title, emit it as an event
        if (len(line) <= TITLE_MAX_LEN
                and not line.lower().startswith(SKIP_STARTS)):
            title = line

            # Grab description: next non-title, non-date line longer than 40 chars
            desc = ''
            for j in range(i + 1, min(i + 5, len(deduped))):
                d = deduped[j]
                if _la_parse_date_range(d, target_year)[0]:
                    break
                if len(d) > 40 and d.lower() not in SKIP_LINES:
                    desc = d[:250]
                    break

            if future_only and (curr_end or curr_start).date() < today.date():
                i += 1
                continue

            dedup_key = f"{title.lower()[:60]}|{curr_start.strftime('%Y-%m-%d')}"
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                events.append({
                    'title':           title,
                    'start_time':      curr_start.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end_time':        curr_end.strftime('%Y-%m-%dT%H:%M:%S') if curr_end and curr_end != curr_start else '',
                    'venue':           _LA_VENUE,
                    'venue_address':   _LA_ADDR,
                    'description':     desc or title,
                    'source_url':      _LA_SOURCE_URL,
                    'image_url':       '',
                    'source_name':     source_name or _LA_VENUE,
                    'categories':      ['Arts & Culture', 'Exhibition', 'Community'],
                    'outdoor':         False,
                    'family_friendly': True,
                })
                print(f"[LivingArts] Added: {title} ({curr_start.strftime('%Y-%m-%d')} - {(curr_end or curr_start).strftime('%Y-%m-%d')})")

        i += 1

    print(f'[LivingArts] Total exhibitions: {len(events)}')
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