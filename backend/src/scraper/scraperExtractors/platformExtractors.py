"""
Locate918 Scraper - DOM-based Platform Extractors
===================================================
Extractors that parse rendered HTML from ticketing/event platforms:
  - Tribe (WordPress Events Calendar)
  - Eventbrite embeds
  - Stubwire (with date-title fix)
  - Dice.fm, Bandsintown, Songkick, Ticketmaster, AXS, Etix, See Tickets
  - Schema.org/JSON-LD
  - TNEW/Tessitura (Tulsa Opera, Gilcrease)
  - Google Calendar (embedded iframes)
  - Squarespace Events (TSO, Living Arts, LowDown)

FIX: Stubwire date-title bug - detects when link text is just a date
     and finds the real title from nearby headings.
"""

import re
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from scraperUtils import (
    HEADERS,
    COMBINED_DATE_PATTERN,
    COMBINED_TIME_PATTERN,
    extract_date_from_text,
    extract_time_from_text,
    text_has_date,
)


# ============================================================================
# SCHEMA.ORG / JSON-LD
# ============================================================================

def extract_schema_org(soup, base_url, source_name):
    events = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string)
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


# ============================================================================
# WORDPRESS EVENTS CALENDAR (TRIBE)
# ============================================================================

def extract_tribe_events(soup, base_url, source_name):
    events = []
    selectors = [
        '.tribe-events-calendar-list__event',
        '.tribe-events-calendar-list__event-row',
        '.tribe_events', '.type-tribe_events', '.tribe-event-featured',
        'article.tribe-events-calendar-list__event',
    ]

    containers = []
    for sel in selectors:
        containers.extend(soup.select(sel))
    if not containers:
        for lst in soup.select('.tribe-events-calendar-list'):
            for child in lst.find_all(['article', 'div', 'li'], recursive=False):
                containers.append(child)

    # Deduplicate
    seen_ids = set()
    unique = []
    for c in containers:
        cid = id(c)
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique.append(c)
    containers = unique

    junk_titles = {
        'events', 'calendar', 'google calendar', 'icalendar', 'ical', 'ical export',
        'outlook 365', 'outlook live', 'export events', 'subscribe', 'add to calendar',
        'previous events', 'next events', 'today', 'list', 'month', 'day',
        'search', 'find events', 'event views navigation', 'view as',
    }

    seen = set()
    for container in containers:
        title_el = (
                container.select_one('.tribe-events-calendar-list__event-title a') or
                container.select_one('.tribe-events-calendar-list__event-title') or
                container.select_one('.tribe-event-url') or
                container.select_one('h2.tribe-events-list-event-title a') or
                container.select_one('h3 a[href*="/event/"]') or
                container.select_one('h2 a[href*="/event/"]') or
                container.select_one('h3 a') or container.select_one('h2 a')
        )
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or title in seen:
            continue
        if title.lower().strip() in junk_titles:
            continue
        if len(title) < 4 and ' ' not in title:
            continue
        seen.add(title)

        link = ''
        if title_el.name == 'a':
            link = title_el.get('href', '')
        else:
            le = title_el.find('a') or container.select_one('a[href*="/event/"]')
            if le:
                link = le.get('href', '')

        date_el = (
                container.select_one('.tribe-events-calendar-list__event-datetime') or
                container.select_one('.tribe-event-date-start') or
                container.select_one('.tribe-events-schedule') or
                container.select_one('.tribe-event-schedule-details') or
                container.select_one('time') or container.select_one('[datetime]')
        )
        date_str = ''
        if date_el:
            date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)
        if not date_str:
            ct = container.get_text(' ', strip=True)
            date_str = extract_date_from_text(ct) or ''
            ts = extract_time_from_text(ct)
            if ts and date_str:
                date_str = f"{date_str} @ {ts}"

        desc_el = container.select_one('.tribe-events-calendar-list__event-description')
        description = desc_el.get_text(strip=True)[:200] if desc_el else ''

        events.append({
            'title': title, 'date': date_str, 'description': description,
            'source_url': urljoin(base_url, link) if link else '',
            'source': source_name, 'venue': source_name,
        })

    return events


# ============================================================================
# EVENTBRITE EMBED
# ============================================================================

def extract_eventbrite_embed(soup, base_url, source_name):
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
        events.append({'title': title, 'date': date_str, 'source_url': link, 'source': source_name})
    return events


# ============================================================================
# STUBWIRE (with date-title fix)
# ============================================================================

def extract_stubwire_events(soup, base_url: str, source_name: str) -> list:
    events = []
    seen = set()

    event_links = soup.select('a[href*="/event/"]')
    for link in event_links:
        href = link.get('href', '')
        title = link.get_text(strip=True)

        if not title or len(title) < 2:
            continue
        if title.lower() in ['buy tickets', 'more info', 'all session tickets', 'read more', 'view all', 'see all events', 'all events']:
            continue
        if '/event/' not in href:
            continue
        if href in seen:
            continue
        seen.add(href)

        # FIX: Detect date-only titles (e.g., "Fri, Mar 20") and find real title
        date_only = re.match(
            r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+'
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}',
            title, re.IGNORECASE
        )
        if date_only:
            # This link's text is just a date - find the real title nearby
            container = link.find_parent(['div', 'article', 'li', 'section'])
            if container:
                # Look for h2/h3 heading link with the same href
                heading_link = container.select_one(f'h2 a[href="{href}"], h3 a[href="{href}"], h2 a[href$="{href.split("/")[-2]}/"], h3 a[href$="{href.split("/")[-2]}/"]')
                if heading_link:
                    real_title = heading_link.get_text(strip=True)
                    if real_title and len(real_title) > 3:
                        title = real_title
                else:
                    # Fallback: any heading in the container
                    heading = container.select_one('h2, h3, h4')
                    if heading:
                        ht = heading.get_text(strip=True)
                        if ht and len(ht) > 3 and not re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', ht):
                            title = ht

        container = link.find_parent(['div', 'article', 'li'])
        date_str = ''
        time_str = ''

        if container:
            container_text = container.get_text(' ', strip=True)
            # FIX: Use shared date/time extractors instead of manual month search.
            date_str = extract_date_from_text(container_text) or ''
            time_str = extract_time_from_text(container_text) or ''

            # FIX: Shrine-style layouts put the date in a SIBLING element above
            # the event card, not inside it.  Structure looks like:
            #   <div class="date">05<br>Mar</div>   ← sibling
            #   <div class="event">[title, time]</div>  ← container
            # Walk backwards through previous siblings to find a date.
            if not date_str:
                sibling = container.find_previous_sibling()
                checked = 0
                while sibling and checked < 5:
                    sib_text = sibling.get_text(' ', strip=True)
                    if sib_text:
                        date_str = extract_date_from_text(sib_text) or ''
                        if date_str:
                            break
                        # Also check for bare "05 Mar" or "12 Apr" split across elements
                        # (day and month might be in separate child elements)
                        day_month = re.match(r'^(\d{1,2})\s+([A-Za-z]{3,})', sib_text)
                        if day_month:
                            date_str = f"{day_month.group(1)} {day_month.group(2)}"
                            break
                    sibling = sibling.find_previous_sibling()
                    checked += 1

            # FIX: Also try parent container if still no date
            if not date_str and container.parent:
                parent_text = container.parent.get_text(' ', strip=True)
                # Only use parent date if we can isolate it near our event
                # Look for "DD Mon" pattern right before the event title in parent text
                title_idx = parent_text.find(title[:20]) if title else -1
                if title_idx > 0:
                    preceding = parent_text[:title_idx]
                    date_str = extract_date_from_text(preceding) or ''

        full_date = date_str
        if time_str:
            full_date = f"{date_str} @ {time_str}" if date_str else time_str

        full_url = href if href.startswith('http') else urljoin(base_url, href)

        image_url = ''
        ticket_url = ''
        if container:
            img = container.select_one('img[src*="stubwire"]')
            if img:
                image_url = img.get('src', '')
            tl = container.select_one('a[href*="stubwire.com"]')
            if tl:
                ticket_url = tl.get('href', '')

        events.append({
            'title': title, 'date': full_date, 'source_url': full_url,
            'tickets_url': ticket_url, 'image_url': image_url,
            'source': source_name, 'venue': source_name,
        })

    return events


# ============================================================================
# DICE.FM, BANDSINTOWN, SONGKICK, TICKETMASTER, AXS, ETIX, SEE TICKETS
# ============================================================================

def _extract_ticket_platform(soup, base_url, source_name, link_selector, url_filter, label):
    """Generic ticket platform extractor."""
    events = []
    seen = set()
    for link in soup.select(link_selector):
        href = link.get('href', '')
        if url_filter and url_filter not in href:
            continue
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets', 'buy now', 'book now']:
            parent = link.find_parent(['div', 'article', 'li'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"], [class*="name"]')
                if heading:
                    title = heading.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        date_str = ''
        parent = link.find_parent(['div', 'article', 'li', 'tr'])
        if parent:
            date_el = parent.select_one('time, [class*="date"], [datetime]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)

        events.append({
            'title': title, 'date': date_str, 'source_url': href,
            'tickets_url': href, 'source': source_name, 'venue': source_name,
        })
    return events


def extract_dice_events(soup, base_url, source_name):
    events = []
    seen = set()
    for link in soup.select('a[href*="dice.fm"], a[href*="link.dice.fm"]'):
        href = link.get('href', '')
        if href in seen:
            continue
        seen.add(href)
        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            parent = link.find_parent(['div', 'article'])
            if parent:
                heading = parent.select_one('h1, h2, h3, h4, [class*="title"]')
                if heading:
                    title = heading.get_text(strip=True)
        if not title or title.lower() in ['buy tickets', 'get tickets', 'book now']:
            continue
        date_str = ''
        parent = link.find_parent(['div', 'article', 'li'])
        if parent:
            date_el = parent.select_one('time, [class*="date"], [datetime]')
            if date_el:
                date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)
        events.append({'title': title, 'date': date_str, 'source_url': href, 'tickets_url': href, 'source': source_name, 'venue': source_name})
    return events


def extract_bandsintown_events(soup, base_url, source_name):
    events = []
    seen = set()
    for link in soup.select('a[href*="bandsintown.com/e/"]'):
        href = link.get('href', '')
        if href in seen:
            continue
        seen.add(href)
        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{1,2}', title)
        event_date = ''
        if date_match:
            event_date = title[date_match.start():].strip()
            title = title[:date_match.start()].strip()
        if not title:
            continue
        if not event_date:
            parent = link.find_parent(['div', 'li', 'tr'])
            if parent:
                de = parent.select_one('time, [class*="date"]')
                if de:
                    event_date = de.get('datetime', '') or de.get_text(strip=True)
        events.append({'title': title, 'date': event_date, 'source_url': href, 'tickets_url': href, 'source': source_name, 'venue': source_name})
    return events


def extract_songkick_events(soup, base_url, source_name):
    return _extract_ticket_platform(soup, base_url, source_name, 'a[href*="songkick.com"]', '/concerts/', 'Songkick') + \
        _extract_ticket_platform(soup, base_url, source_name, 'a[href*="songkick.com"]', '/events/', 'Songkick')


def extract_ticketmaster_events(soup, base_url, source_name):
    return _extract_ticket_platform(soup, base_url, source_name, 'a[href*="ticketmaster.com"], a[href*="livenation.com"]', '/event/', 'Ticketmaster')


def extract_axs_events(soup, base_url, source_name):
    return _extract_ticket_platform(soup, base_url, source_name, 'a[href*="axs.com"]', '/events/', 'AXS')


def extract_seetickets_events(soup, base_url, source_name):
    return _extract_ticket_platform(soup, base_url, source_name, 'a[href*="seetickets.us"], a[href*="seetickets.com"]', None, 'See Tickets')


def extract_etix_events(soup, base_url: str, source_name: str) -> list:
    """Extract events from Etix links/embeds OR Etix venue pages."""
    events = []
    seen = set()
    is_etix_page = 'etix.com' in base_url

    # Try captured API data first
    for script in soup.select('script[type="etix-api-data"]'):
        try:
            api_data = json.loads(script.get_text())
            if isinstance(api_data, list):
                items = api_data
            elif isinstance(api_data, dict):
                # /ticket/api/online/venues/{id} returns {performances: [...]} or
                # {results: [...]} or top-level list under various keys
                items = (api_data.get('performances') or
                         api_data.get('results') or
                         api_data.get('events') or
                         api_data.get('performanceList') or
                         api_data.get('data') or
                         [])
                # Some venue responses nest under a venue object
                if not items and 'venue' in api_data:
                    venue_obj = api_data['venue']
                    if isinstance(venue_obj, dict):
                        items = (venue_obj.get('performances') or
                                 venue_obj.get('events') or [])
            else:
                continue

            for perf in items:
                if isinstance(perf, dict) and 'performance' in perf:
                    perf = perf['performance']
                title = (perf.get('name') or perf.get('title') or
                         perf.get('performanceName') or perf.get('eventName') or '')
                if not title:
                    continue
                date_str = (perf.get('performanceDate') or perf.get('date') or
                            perf.get('startDate') or perf.get('eventDate') or '')
                time_str = (perf.get('performanceTime') or perf.get('time') or
                            perf.get('startTime') or perf.get('eventTime') or '')
                if date_str and time_str:
                    date_str = f"{date_str} {time_str}"
                perf_id = perf.get('performanceID') or perf.get('id') or perf.get('performanceId') or ''
                event_url = f"https://www.etix.com/ticket/p/{perf_id}" if perf_id else base_url
                if event_url not in seen:
                    seen.add(event_url)
                    events.append({
                        'title': title, 'date': date_str, 'source_url': event_url,
                        'tickets_url': event_url, 'source': source_name,
                        'venue': (perf.get('venueName') or perf.get('venue') or source_name),
                        'image_url': perf.get('imageUrl') or perf.get('image') or perf.get('imageURL') or '',
                    })

            if events:
                return events
        except Exception as e:
            print(f"[Etix] Error parsing API data: {e}")

    if is_etix_page:
        for link in soup.select('a[href*="/ticket/p/"]'):
            href = link.get('href', '')
            if href in seen:
                continue
            seen.add(href)
            if href.startswith('/'):
                href = 'https://www.etix.com' + href
            title = link.get_text(strip=True)
            if not title or len(title) < 3 or title.lower() in ['buy tickets', 'get tickets', 'buy', 'tickets']:
                parent = link.find_parent(['div', 'article', 'li', 'section'])
                if parent:
                    heading = parent.select_one('h1, h2, h3, h4, h5, [class*="title"], [class*="Title"]')
                    if heading:
                        title = heading.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            date_str = ''
            parent = link.find_parent(['div', 'article', 'li', 'section'])
            if parent:
                de = parent.select_one('time, [class*="date"], [class*="Date"]')
                if de:
                    date_str = de.get('datetime', '') or de.get_text(strip=True)
            events.append({
                'title': title, 'date': date_str, 'source_url': href,
                'tickets_url': href, 'source': source_name, 'venue': source_name,
            })

    # External etix links from non-etix sites
    for link in soup.select('a[href*="etix.com"]'):
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
            de = parent.select_one('time, [class*="date"]')
            if de:
                date_str = de.get('datetime', '') or de.get_text(strip=True)
        events.append({
            'title': title, 'date': date_str, 'source_url': href,
            'tickets_url': href, 'source': source_name, 'venue': source_name,
        })

    return events


# ============================================================================
# TNEW / TESSITURA (Tulsa Opera, Gilcrease)
# ============================================================================

def extract_tnew_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from TNEW/Tessitura API data captured by Playwright.
    Strips HTML from titles and descriptions.
    """
    events = []
    seen = set()

    for script in soup.select('script[type="tnew-api-data"]'):
        try:
            data = json.loads(script.get_text())
            items = data if isinstance(data, list) else data.get('productions', data.get('seasons', []))

            print(f"[TNEW] Parsing {len(items)} production items")

            for item in items:
                title = item.get('productionTitle', '') or item.get('title', '') or item.get('name', '')
                # Strip HTML from title
                title = re.sub(r'<[^>]+>', ' ', title)
                title = re.sub(r'\s+', ' ', title).strip()

                if not title or title in seen:
                    continue
                seen.add(title)

                # Get dates from performances array
                performances = item.get('performances', [])
                date_str = ''
                if performances:
                    first_perf = performances[0]
                    perf_date = first_perf.get('performanceDate', '') or first_perf.get('date', '')
                    perf_time = first_perf.get('performanceTime', '') or first_perf.get('time', '')
                    if perf_date:
                        try:
                            dt = datetime.fromisoformat(perf_date.replace('Z', '').split('+')[0])
                            date_str = dt.strftime('%b %d, %Y')
                            if perf_time:
                                date_str += f" @ {perf_time}"
                        except:
                            date_str = perf_date

                description = item.get('description', '') or item.get('shortDescription', '') or ''
                if description:
                    description = re.sub(r'<[^>]+>', ' ', description)
                    description = re.sub(r'\s+', ' ', description).strip()[:200]

                event_url = item.get('url', '') or item.get('webLink', '') or ''
                if event_url and not event_url.startswith('http'):
                    event_url = urljoin(base_url, event_url)

                image_url = item.get('imageUrl', '') or item.get('image', '') or ''

                events.append({
                    'title': title,
                    'date': date_str,
                    'description': description,
                    'source_url': event_url or base_url,
                    'image_url': image_url,
                    'source': source_name,
                    'venue': source_name,
                })

        except Exception as e:
            print(f"[TNEW] Error parsing API data: {e}")

    print(f"[TNEW] Extracted {len(events)} events")
    return events


# ============================================================================
# GOOGLE CALENDAR (Embedded)
# ============================================================================

def extract_gcal_events(soup, base_url: str, source_name: str) -> list:
    """
    Extract events from Google Calendar API data captured by Playwright.
    Handles ISO dates with timezone.
    """
    events = []
    seen = set()

    for script in soup.select('script[type="gcal-api-data"]'):
        try:
            data = json.loads(script.get_text())
            items = data.get('items', [])
            print(f"[GCal] Parsing {len(items)} calendar items")

            for item in items:
                title = item.get('summary', '').strip()
                if not title or title in seen:
                    continue
                seen.add(title)

                start = item.get('start', {})
                end = item.get('end', {})
                start_str = start.get('dateTime', '') or start.get('date', '')
                end_str = end.get('dateTime', '') or end.get('date', '')

                date_str = ''
                if start_str:
                    try:
                        dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        date_str = dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')
                    except:
                        date_str = start_str

                description = item.get('description', '') or ''
                if description:
                    description = re.sub(r'<[^>]+>', ' ', description)
                    description = re.sub(r'\s+', ' ', description).strip()[:200]

                location = item.get('location', '') or source_name

                events.append({
                    'title': title,
                    'date': date_str,
                    'end_date': end_str,
                    'venue': location,
                    'description': description,
                    'source_url': item.get('htmlLink', base_url),
                    'source': source_name,
                })

        except Exception as e:
            print(f"[GCal] Error parsing API data: {e}")

    print(f"[GCal] Extracted {len(events)} events")
    return events


# ============================================================================
# SQUARESPACE EVENTS
# ============================================================================

def extract_squarespace_events(soup, html: str, base_url: str, source_name: str) -> list:
    """
    Extract events from Squarespace sites.
    Detection: squarespace-cdn.com image URLs.
    Strategy 1: Google Calendar links (dates=YYYYMMDDTHHMMSSZ/...)
    Strategy 2: Heading + standalone links to /shows/, /events/, /calendar/
    """
    # Detection
    if 'squarespace-cdn.com' not in html and 'squarespace.com' not in html:
        return []

    print(f"[Squarespace] Detected Squarespace site")
    events = []
    seen = set()

    # Strategy 1: Google Calendar add links (most reliable dates)
    gcal_links = soup.select('a[href*="calendar.google.com/calendar/render"]')
    for link in gcal_links:
        href = link.get('href', '')

        # Extract dates from "dates=YYYYMMDDTHHMMSSZ/YYYYMMDDTHHMMSSZ"
        dates_match = re.search(r'dates=(\d{8}T\d{6}Z)/(\d{8}T\d{6}Z)', href)
        if not dates_match:
            continue

        start_raw = dates_match.group(1)
        end_raw = dates_match.group(2)

        try:
            start_dt = datetime.strptime(start_raw, '%Y%m%dT%H%M%SZ')
            date_str = start_dt.strftime('%b %d, %Y @ %I:%M %p').replace(' 0', ' ')
        except:
            date_str = start_raw

        # Extract title from "text=" parameter
        text_match = re.search(r'text=([^&]+)', href)
        title = ''
        if text_match:
            from urllib.parse import unquote
            title = unquote(text_match.group(1)).replace('+', ' ').strip()

        if not title:
            # Walk up to find heading
            container = link
            for _ in range(6):
                parent = container.parent
                if not parent or parent.name in ['body', 'html']:
                    break
                container = parent
                heading = container.select_one('h1, h2, h3, h4')
                if heading:
                    title = heading.get_text(strip=True)
                    break

        if not title or title in seen:
            continue
        seen.add(title)

        events.append({
            'title': title,
            'date_start': f"{start_dt.isoformat()}Z" if dates_match else '',
            'date': date_str,
            'source_url': base_url,
            'source': source_name,
            'venue': source_name,
        })

    if events:
        print(f"[Squarespace] Strategy 1 (GCal links): {len(events)} events")
        return events

    # Strategy 2: Links to event pages from headings AND standalone links
    event_path_patterns = ['/shows/', '/events/', '/calendar/', '/concerts/', '/performances/']

    for link in soup.select('a[href]'):
        href = link.get('href', '')
        if not href or href == '#':
            continue
        if not any(p in href for p in event_path_patterns):
            continue

        full_url = href if href.startswith('http') else urljoin(base_url, href)
        if full_url in seen:
            continue

        # Try to get title from the link or its parent heading
        title = link.get_text(strip=True)

        # Walk up to find a better container with more context
        container = link
        for _ in range(4):
            parent = container.parent
            if not parent or parent.name in ['body', 'html', 'main']:
                break
            container = parent
            heading = container.select_one('h1, h2, h3, h4')
            if heading and heading.get_text(strip=True) != title:
                title = heading.get_text(strip=True)
                break

        if not title or len(title) < 3:
            continue
        if title.lower() in ['read more', 'learn more', 'more info', 'view all', 'see all']:
            continue

        seen.add(full_url)

        # Try to find date near the link
        ct = container.get_text(' ', strip=True) if container else ''
        date_str = extract_date_from_text(ct) or ''
        ts = extract_time_from_text(ct)
        if ts:
            date_str = f"{date_str} @ {ts}" if date_str else ts

        events.append({
            'title': title,
            'date': date_str,
            'source_url': full_url,
            'source': source_name,
            'venue': source_name,
        })

    print(f"[Squarespace] Strategy 2 (event links): {len(events)} events")
    return events


# ============================================================================
# TICKETTAILOR EXTRACTOR
# ============================================================================

def extract_tickettailor_events(soup, base_url: str, source_name: str) -> tuple:
    """
    Extract events from TicketTailor pages (tickettailor.com).
    Used by: The Colony Tulsa, and others.
    TicketTailor renders event cards with titles, dates, and ticket links.
    Returns (events_list, was_detected).
    """
    if 'tickettailor.com' not in base_url:
        return [], False

    print(f"[TicketTailor] Detected TicketTailor site")

    events = []
    seen = set()

    # Strategy 1: Look for structured event cards/links
    # TicketTailor uses various card layouts with event links
    card_selectors = [
        '[class*="event-card"]',
        '[class*="EventCard"]',
        '[class*="listing"]',
        '[class*="event-listing"]',
        'a[href*="/events/"]',
        '[data-testid*="event"]',
        'article',
        '.card',
    ]

    cards = []
    for sel in card_selectors:
        found = soup.select(sel)
        if found:
            cards = found
            print(f"[TicketTailor] Found {len(found)} elements via '{sel}'")
            break

    for card in cards:
        # Debug: show card structure
        card_text = card.get_text(' ', strip=True)[:150]
        print(f"[TicketTailor] Card text: {card_text}")

        # Get title from heading, link text, or any prominent text
        title_el = (
                card.select_one('h1, h2, h3, h4, h5') or
                card.select_one('[class*="title"], [class*="Title"], [class*="name"], [class*="Name"]') or
                card.select_one('[class*="event"], [class*="Event"]') or
                card.select_one('a[href]') or
                card.select_one('strong, b, span')
        )
        if not title_el and card.name == 'a':
            title_el = card

        if not title_el:
            # Last resort: grab first non-trivial text node
            for text in card.stripped_strings:
                if len(text) > 3 and text.lower() not in ('get tickets', 'buy tickets', 'view event', 'sold out'):
                    title = text[:100]
                    break
            else:
                print(f"[TicketTailor] No title found in card")
                continue
        else:
            title = title_el.get_text(strip=True)
        if not title or len(title) < 3 or title.lower() in ('get tickets', 'buy tickets', 'view event'):
            continue
        if title in seen:
            continue
        seen.add(title)

        # Get date
        date_str = ''
        date_el = card.select_one('time, [class*="date"], [class*="Date"], [datetime]')
        if date_el:
            date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)
        else:
            # Search card text for date pattern
            card_text = card.get_text(' ', strip=True)
            from scraperUtils import extract_date_from_text, extract_time_from_text
            date_str = extract_date_from_text(card_text) or ''
            time_str = extract_time_from_text(card_text)
            if time_str:
                date_str = f"{date_str} @ {time_str}" if date_str else time_str

        # Get link
        link = ''
        link_el = card if card.name == 'a' else card.select_one('a[href]')
        if link_el:
            href = link_el.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                if href.startswith('/'):
                    link = f"https://www.tickettailor.com{href}"
                elif href.startswith('http'):
                    link = href
                else:
                    link = f"https://www.tickettailor.com/{href}"

        # Get image
        image = ''
        img_el = card.select_one('img[src]')
        if img_el:
            image = img_el.get('src', '')

        # Get description
        desc = ''
        desc_el = card.select_one('[class*="desc"], [class*="Desc"], [class*="summary"], p')
        if desc_el:
            desc = desc_el.get_text(strip=True)[:200]

        events.append({
            'title': title,
            'date': date_str,
            'description': desc,
            'source_url': link or base_url,
            'image_url': image,
            'source': source_name,
            'venue': source_name,
        })

    # Strategy 2: If no cards found, try all links with /events/ pattern
    if not events:
        for link in soup.select('a[href*="/events/"]'):
            href = link.get('href', '')
            title = link.get_text(strip=True)
            if not title or len(title) < 3 or title in seen:
                continue
            if title.lower() in ('get tickets', 'buy tickets', 'view event', 'view all'):
                continue
            seen.add(title)

            if href.startswith('/'):
                full_url = f"https://www.tickettailor.com{href}"
            else:
                full_url = href

            events.append({
                'title': title,
                'date': '',
                'source_url': full_url,
                'source': source_name,
                'venue': source_name,
            })

    print(f"[TicketTailor] Extracted {len(events)} events")
    return events, True