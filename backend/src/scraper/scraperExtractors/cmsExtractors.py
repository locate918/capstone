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

        now = datetime.now(timezone.utc)
        start_date = now.strftime("%Y-%m-%dT06:00:00.000Z") if future_only else "2020-01-01T06:00:00.000Z"
        end_date = (now + timedelta(days=365)).strftime("%Y-%m-%dT06:00:00.000Z")

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

            json_str = json.dumps(query)
            api_url = f"{base_url}/includes/rest_v2/plugins_events_events_by_date/find/?json={quote(json_str)}&token={token}"

            print(f"[Simpleview] Fetching events (skip={skip})...")
            try:
                resp = await client.get(api_url)
                data = resp.json()
            except:
                break

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
                break

            print(f"[Simpleview] Got {len(docs)} events (total: {total_count})")

            for doc in docs:
                try:
                    if not isinstance(doc, dict):
                        continue
                    title = doc.get('title', '')
                    if not title:
                        continue

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

            total_fetched += len(docs)
            skip += batch_size
            if total_count > 0 and total_fetched >= total_count:
                break
            if len(docs) < batch_size:
                break
            await asyncio.sleep(0.3)

        print(f"[Simpleview] Total events fetched: {len(events)}")

    return events


# ============================================================================
# SITEWRENCH CMS
# ============================================================================

async def extract_sitewrench_events(html: str, source_name: str, url: str = '', future_only: bool = True) -> tuple:
    is_sitewrench = (
            'sitewrench' in html.lower() or
            'event-card__info__header' in html or
            'calendar-listings' in html or
            ('cal-' in html and 'pageSize' in html)
    )
    if not is_sitewrench:
        return [], False

    print(f"[SiteWrench] Detected SiteWrench CMS on {url}")

    token_match = re.search(r'token[=:]\s*["\']?([a-f0-9]{30,50})', html)
    siteid_match = re.search(r'siteId[=:]\s*["\']?(\d+)', html, re.IGNORECASE)
    pagepart_match = (
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

    events = []
    page = 1

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
            cards = soup.select('.event-card')
            if not cards:
                break

            print(f"[SiteWrench] Page {page}: {len(cards)} event cards")

            parsed_base = urlparse(base_url)
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

            if not soup.select_one('.next-prev-nav__item--next a'):
                break
            page += 1
            if page > 10:
                break
            await asyncio.sleep(0.3)

    print(f"[SiteWrench] Total: {len(events)} events")
    return events


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
                items = data.get('CalendarItems', data.get('items', data.get('events', [])))

            print(f"[RecDesk] Parsing {len(items)} calendar items")

            for item in items:
                event_id = item.get('EventId') or item.get('eventId') or item.get('ID')
                if event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)

                title = (item.get('EventName') or item.get('Title') or item.get('name') or '').strip()
                if not title:
                    continue

                # Skip junk entries starting with ! or #
                if title.startswith('!') or title.startswith('#'):
                    continue

                start = item.get('StartDate') or item.get('start') or ''
                end = item.get('EndDate') or item.get('end') or ''

                date_str = ''
                if start:
                    try:
                        dt = datetime.fromisoformat(start.replace('Z', '').split('+')[0])
                        date_str = dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')
                    except:
                        date_str = start

                location = (item.get('LocationName') or item.get('Location') or
                            item.get('location') or source_name)

                description = item.get('Description') or item.get('description') or ''
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