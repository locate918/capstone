"""
Locate918 Scraper - Utilities & Configuration
===============================================
Shared config, robots.txt checking, URL management, and date/time pattern matching.
"""

import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available - install with: pip install playwright && playwright install chromium")

# ============================================================================
# CONFIGURATION
# ============================================================================

OUTPUT_DIR = Path("scraped_data")
OUTPUT_DIR.mkdir(exist_ok=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8001")
HEADERS = {"User-Agent": "Locate918 Event Aggregator (educational project)"}
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

# Cache for robots.txt parsers (avoid re-fetching)
_robots_cache = {}

# Cache for venue websites (avoid re-fetching listing pages)
_venue_website_cache = {}


# ============================================================================
# VENUE WEBSITE LOOKUP
# ============================================================================

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


# ============================================================================
# ROBOTS.TXT CHECKER
# ============================================================================

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


# ============================================================================
# URL MANAGEMENT
# ============================================================================

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