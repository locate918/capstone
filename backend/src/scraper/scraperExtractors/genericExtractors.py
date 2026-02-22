"""
Locate918 Scraper - Generic Fallback Extractors
=================================================
Used when no platform-specific extractor matches:
  - Repeating structure detection (lists of similar items)
  - Date/time proximity matching (dates near title-like text)
  - Section heading context helper

FIX: Repeating structures now groups items by parent element before
     similarity check, preventing nav items from mixing with content.
FIX: Section heading finder (_find_section_heading) added to capture
     context from nearby h1-h3 headings for generic card titles.
FIX: PAST EVENTS section stripping uses find_all_next() for robust removal.
"""

import re
from urllib.parse import urljoin
from bs4 import NavigableString

from scraperUtils import (
    COMBINED_DATE_PATTERN,
    COMBINED_TIME_PATTERN,
    extract_date_from_text,
    extract_time_from_text,
    text_has_date,
)


def _find_section_heading(element) -> str:
    """
    Walk up DOM to find the nearest preceding h1-h3 heading.
    Useful for getting context when event card titles are generic
    (e.g., "Friday Tickets" -> section heading "Boarte Piano Trio").
    """
    current = element
    for _ in range(10):
        parent = current.parent
        if not parent or parent.name in ['body', 'html']:
            break

        # Look for preceding sibling headings
        for sibling in current.previous_siblings:
            if hasattr(sibling, 'name') and sibling.name in ['h1', 'h2', 'h3']:
                text = sibling.get_text(strip=True)
                if text and len(text) > 3:
                    return text

        current = parent

    return ''


def _strip_past_events_section(soup):
    """
    FIX: Remove all content after "Past Events" markers.
    Uses find_all_next() which works regardless of nesting depth.
    Previous approach broke when marker was direct child of <body>.
    """
    markers = ['past events', 'previous events', 'past shows', 'past performances', 'archive']

    for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'p']):
        text = el.get_text(strip=True).lower()
        if text in markers:
            print(f"[PastEvents] Found '{text}' marker, removing subsequent elements")
            # Remove all elements after this marker
            for following in el.find_all_next():
                following.decompose()
            # Remove the marker itself
            el.decompose()
            break


def extract_by_date_proximity(soup, base_url, source_name):
    """
    Find events by looking for date patterns and grabbing nearby title-like text.
    Enhanced with section heading context for generic titles.
    """
    events = []
    seen_titles = set()

    body = soup.find('body') or soup

    date_elements = []
    for element in body.find_all(text=True):
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text and text_has_date(text):
                date_elements.append(element.parent)

    for date_el in date_elements:
        container = date_el
        for _ in range(5):
            parent = container.parent
            if not parent or parent.name in ['body', 'html', 'main', 'section']:
                break
            container = parent
            date_count = len([c for c in container.find_all(text=True) if text_has_date(str(c))])
            if date_count > 3:
                container = date_el.parent
                break

        title = ''
        title_el = None

        # Try selectors in priority order, but skip date-like results
        for selector in ['h1, h2, h3, h4, h5, h6', 'a[href]', '[class*="title"]', 'strong, b']:
            candidate = container.select_one(selector)
            if candidate:
                candidate_text = candidate.get_text(strip=True)
                # Skip if it looks like a date, day name, or CTA
                if candidate_text and len(candidate_text) > 3:
                    lower = candidate_text.lower().strip()
                    if text_has_date(candidate_text):
                        continue
                    if lower in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                                 'saturday', 'sunday', 'get tickets', 'buy tickets',
                                 'buy now', 'book now', 'register', 'learn more', 'read more'):
                        continue
                    # Skip day-of-week abbreviations
                    if re.match(r'^(mon|tue|wed|thu|fri|sat|sun)\w*$', lower):
                        continue
                    title = candidate_text
                    title_el = candidate
                    break

        if not title:
            texts = [t.strip() for t in container.stripped_strings]
            for t in texts:
                if len(t) > 5 and not text_has_date(t) and not COMBINED_TIME_PATTERN.search(t):
                    title = t[:100]
                    break

        if not title or title in seen_titles:
            continue

        # FIX: Add section heading context for generic titles
        section_heading = _find_section_heading(container)
        description = ''
        if section_heading and section_heading.lower() != title.lower():
            description = f"Section: {section_heading}"

        seen_titles.add(title)

        container_text = container.get_text(' ', strip=True)
        date_str = extract_date_from_text(container_text) or ''
        time_str = extract_time_from_text(container_text)
        if time_str:
            date_str = f"{date_str} @ {time_str}" if date_str else time_str

        link = ''
        link_el = container.select_one('a[href]')
        if link_el:
            href = link_el.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                link = urljoin(base_url, href)

        events.append({
            'title': title,
            'date': date_str,
            'description': description,
            'source_url': link,
            'source': source_name,
        })

    return events


def extract_repeating_structures(soup, base_url, source_name):
    """
    Find events by detecting repeating HTML structures (lists of similar items).

    FIX: Groups items by parent element before similarity check.
    Previously, soup.select('ul > li') returned ALL <li> from every <ul>,
    mixing nav items with content. Now each parent's children are checked
    independently.
    """
    events = []
    seen = set()

    list_selectors = [
        'ul > li', 'ol > li',
        '.events-list > div', '.events-list > article',
        '.event-list > div', '.event-list > article',
        '[class*="list"] > [class*="item"]',
        '[class*="events"] > [class*="event"]',
        '[class*="calendar"] > div',
        '.row > .col',
        'table tbody tr',
    ]

    for selector in list_selectors:
        all_items = soup.select(selector)
        if len(all_items) < 2:
            continue

        # FIX: Group items by their parent element
        parent_groups = {}
        for item in all_items:
            parent_id = id(item.parent)
            if parent_id not in parent_groups:
                parent_groups[parent_id] = []
            parent_groups[parent_id].append(item)

        for parent_id, items in parent_groups.items():
            if len(items) < 2:
                continue

            # Check similarity within this parent group
            first_classes = set(items[0].get('class', []))
            similar_count = sum(1 for item in items if set(item.get('class', [])) == first_classes)

            if similar_count < len(items) * 0.5:
                continue

            for item in items:
                item_text = item.get_text(' ', strip=True)
                if not text_has_date(item_text):
                    continue

                title_el = item.select_one('h1, h2, h3, h4, h5, h6, a[href], [class*="title"], strong')
                title = title_el.get_text(strip=True) if title_el else ''

                if not title:
                    for text in item.stripped_strings:
                        if len(text) > 5 and not text_has_date(text):
                            title = text[:100]
                            break

                if not title or title in seen:
                    continue

                # FIX: Add section heading context
                section_heading = _find_section_heading(item)
                description = ''
                if section_heading and section_heading.lower() != title.lower():
                    description = f"Section: {section_heading}"

                seen.add(title)

                date_str = extract_date_from_text(item_text) or ''
                time_str = extract_time_from_text(item_text)
                if time_str:
                    date_str = f"{date_str} @ {time_str}" if date_str else time_str

                link = ''
                link_el = item.select_one('a[href]')
                if link_el:
                    href = link_el.get('href', '')
                    if href and not href.startswith('#'):
                        link = urljoin(base_url, href)

                events.append({
                    'title': title,
                    'date': date_str,
                    'description': description,
                    'source_url': link,
                    'source': source_name,
                })

    return events