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


def _resolve_data_root() -> Path:
    """
    Resolve the base directory for scraper state.

    In production, set SCRAPER_DATA_DIR to a Railway volume mount such as
    `/data/scraper`. Locally, this falls back to the scraper directory.
    """
    configured = os.getenv("SCRAPER_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).parent

# ============================================================================
# AGGREGATOR / SOURCE PRIORITY
# ============================================================================

# Domains we treat as low-trust aggregators (priority 3).
# Events whose source_url comes from one of these will never win a canonical_url
# slot over a direct venue or ticketing source.
AGGREGATOR_DOMAINS = [
    'visittulsa.com',
    'bit918.com',
    'do918.com',
    'eventbrite.com',
    'eventbrite.co.uk',
    'evbuc.com',          # Eventbrite short links
    'allevents.in',
    'events.com',
    'eventful.com',
    'meetup.com',
    'facebook.com',       # FB event pages are aggregator-level for our purposes
]

# Ticketing platforms — better than pure aggregators but still not the venue
TICKETING_DOMAINS = [
    'ticketmaster.com',
    'livenation.com',
    'axs.com',
    'etix.com',
    'tickettailor.com',
    'ticketleap.com',
    'dice.fm',
    'seetickets.us',
]


# ============================================================================
# VENUE DISPLAY PRIORITY
# ============================================================================
# Controls sort order on the event feed — lower number surfaces first.
#   1 = Flagship  — major capacity music/concert venues, large performing arts
#                   centers, established comedy clubs, major casino entertainment,
#                   large festival/convention grounds
#   2 = Featured  — smaller clubs, black-box theaters, arts spaces, museums
#                   with regular events, mid-tier event centers
#   3 = Standard  — everything else (default)
#
# Mirrors the IN-lists in 002_venue_priority.sql exactly — keep in sync.

VENUE_PRIORITY_1 = {
    # Concert / music
    "bok center",
    "cain's ballroom", "cains",
    "tulsa theater", "tulsa theatre",
    "the vanguard",
    "brady theater",
    # Hard Rock sub-rooms
    "hard rock casino tulsa",
    "hard rock hotel & casino tulsa",
    "amp at hard rock casino tulsa",
    "riffs at hard rock casino tulsa",
    "track at hard rock casino tulsa",
    "hard at hard rock casino tulsa",
    # Performing arts
    "tulsa performing arts center",
    "chapman music hall - tpac",
    "john h. williams theatre",
    "liddy doenges theatre",
    "broken arrow performing arts center",
    "vantrease pace",
    # Comedy
    "bricktown comedy club",
    "loony bin", "loony bin comedy club",
    # Casinos / large entertainment
    "river spirit casino resort",
    "the cove at river spirit casino resort", "the cove",
    "the shrine", "shrine",
    # Festival / convention / fairground
    "gathering place", "the gathering place",
    "guthrie green",
    "expo square",
    "sagenet center", "sagenet center at expo square",
    "central park hall", "central park hall at expo square",
    "arvest convention center",
    "arvest convention center – acc",
    "arvest convention center – grand hall",
    "arvest convention center – legacy hall",
    "arvest convention center – pepsi exhibit hall a+b",
    "arvest convention center – tulsa ballroom",
    "arvest convention center, legacy hall",
    "river west festival park",
    "oneok field",
}

VENUE_PRIORITY_2 = {
    # Music clubs / bars with live music
    "chimera ballroom",
    "belafonte",
    "sound pony", "soundpony",
    "low down", "lowdown",
    "mercury lounge",
    "whittier", "whittier bar",
    "church studio", "the church studio",
    "cain's ballroom / the church studio",
    "starlite", "the starlite",
    "hunt club", "the hunt club",
    "bad ass renee's",
    "soul city gastropub and music house",
    "maggie's music box",
    "club majestic",
    "big 10 ballroom",
    "st. vitus",
    "fly loft", "flyloft downtown tulsa",
    "flywheel",
    # Performing arts / cinema
    "circle cinema",
    "tulsa ballet",
    "tulsa opera",
    "tulsa symphony orchestra",
    "bob dylan center",
    "american theatre company",
    "waterworks art center", "waterworks large studio", "waterworks weaving gallery",
    "crosstown arts",
    "tulsa spotlight theater",
    "spotlight theater / riverside studios",
    "tulsa artists' coalition",
    "tulsa artist fellowship project space",
    "living arts", "living arts of tulsa",
    "charles e. norman theatre",
    "linbury theatre",
    "liggett studio",
    "hardesty center for dance education",
    "lorton performance center",
    "lynn riggs theater",
    "sky gallery",
    "zarrow studio",
    "108 contemporary",
    # Museums / attractions
    "philbrook", "philbrook museum of art",
    "gilcrease",
    "discovery lab",
    "tulsa air and space museum & planetarium", "tasm",
    "the castle of muskogee",
    "woolaroc museum & wildlife preserve",
    "tulsa zoo",
    "oklahoma aquarium",
    "will rogers memorial museum",
    "jenks planetarium",
    "greenwood rising",
    "woody guthrie center",
    # Arts districts / community arts
    "tulsa arts district", "arts district",
    "magic city books", "magic city book club",
    # Event centers / markets / mid-tier casinos
    "mother road market", "mother road market & renaissance square",
    "skyline event center",
    "osage casino hotel tulsa skyline event center",
    "osage casino hotel tulsa",
    "mabee center",
    "renaissance square event center",
    "imperio event center",
    "gateway event center", "gateway tulsa event center",
    "claremore expo",
    # Gathering Place sub-venues
    "quiktrip great lawn",
    "quiktrip great lawn and oneok boathouse",
    "oneok boathouse",
    "redbud festival park",
    "blue dome district & riverside",
    "tunes at tul stage",
    "jenks riverwalk",
    # Bars / restaurants with notable live music
    "the colony",
    "kilkenny's irish pub",
    "american solera",
    "cabin boy brewery", "cabin boys brewery",
    "duet jazz restaurant", "duet restaurant",
    "route 66 village", "route 66 historical village",
}


def get_venue_display_priority(venue_name: str) -> int:
    """
    Return the display priority (1, 2, or 3) for a venue name.

    Priority 1 venues surface at the top of the event feed.
    Priority 2 venues sort before generic/community events.
    Priority 3 is the default for everything else.

    Mirrors the IN-lists in 002_venue_priority.sql — keep in sync.
    """
    if not venue_name:
        return 3
    key = venue_name.strip().lower()
    if key in VENUE_PRIORITY_1:
        return 1
    if key in VENUE_PRIORITY_2:
        return 2
    return 3


def is_aggregator_url(url: str) -> bool:
    """Return True if the URL belongs to a known aggregator domain."""
    if not url:
        return False
    try:
        hostname = urlparse(url).netloc.lower().lstrip('www.')
        return any(hostname == d or hostname.endswith('.' + d) for d in AGGREGATOR_DOMAINS)
    except Exception:
        return False


def get_source_priority(url: str, explicit_priority: int = None) -> int:
    """
    Derive a source priority from the URL domain.
      1 = direct venue website  (best)
      2 = ticketing platform    (good)
      3 = aggregator / unknown  (worst)
    An explicit_priority from saved_urls.json always wins.
    """
    if explicit_priority is not None:
        return explicit_priority
    if not url:
        return 3
    try:
        hostname = urlparse(url).netloc.lower().lstrip('www.')
        if any(hostname == d or hostname.endswith('.' + d) for d in AGGREGATOR_DOMAINS):
            return 3
        if any(hostname == d or hostname.endswith('.' + d) for d in TICKETING_DOMAINS):
            return 2
        # Recognise known venue domains as priority 1
        if hostname in KNOWN_VENUE_URLS or hostname.lstrip('www.') in {
            k.lstrip('www.') for k in KNOWN_VENUE_URLS
        }:
            return 1
        # Unknown external URL — treat as mid-tier until classified
        return 2
    except Exception:
        return 3


def make_content_hash(title: str, start_time: str, venue: str = '') -> str:
    """
    Generate a stable fingerprint for an event based on title + date/hour + venue.
    Two events from different sources that represent the same real-world event
    will produce the same hash and be deduplicated by the UPSERT.
    """
    import hashlib
    from dateutil import parser as date_parser

    def _norm(s: str) -> str:
        s = (s or '').lower().strip()
        s = re.sub(r'[^a-z0-9 ]', '', s)   # strip punctuation / special chars
        s = re.sub(r'\band\b', '&', s)      # normalise "and" → "&"
        s = re.sub(r'\s+', ' ', s)          # collapse whitespace
        return s.strip()

    # Round to date + hour only — absorbs minor time discrepancies between sources
    try:
        dt = date_parser.parse(str(start_time), fuzzy=True)
        time_part = dt.strftime('%Y-%m-%d-%H')
    except Exception:
        time_part = str(start_time or '')[:10]  # fallback: just YYYY-MM-DD

    key = f"{_norm(title)}|{time_part}|{_norm(venue)}"
    return hashlib.md5(key.encode()).hexdigest()


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

DATA_ROOT = _resolve_data_root()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = DATA_ROOT / "scraped_data"
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

SAVED_URLS_FILE = DATA_ROOT / "saved_urls.json"


def load_saved_urls() -> list:
    """Load saved URLs from file."""
    if SAVED_URLS_FILE.exists():
        try:
            return json.loads(SAVED_URLS_FILE.read_text())
        except:
            return []
    return []


def save_url(url: str, name: str, use_playwright: bool = True, priority: int = None, venue_priority: int = None) -> list:
    """Add a URL to saved list.
    priority: source trust tier (1=venue, 2=ticketing, 3=aggregator — auto-detected if omitted).
    venue_priority: display priority (1=flagship, 2=featured, 3=standard — falls back to get_venue_display_priority if omitted).
    """
    urls = load_saved_urls()
    resolved_priority = priority if priority is not None else get_source_priority(url)
    resolved_venue_priority = venue_priority if venue_priority is not None else get_venue_display_priority(name)
    for u in urls:
        if u['url'] == url:
            u['name'] = name
            u['playwright'] = use_playwright
            if priority is not None:
                u['priority'] = resolved_priority
            elif 'priority' not in u:
                u['priority'] = resolved_priority
            # venue_priority: always write if explicitly passed, otherwise don't overwrite existing
            if venue_priority is not None:
                u['venue_priority'] = resolved_venue_priority
            elif 'venue_priority' not in u:
                u['venue_priority'] = resolved_venue_priority
            SAVED_URLS_FILE.write_text(json.dumps(urls, indent=2))
            return urls

    urls.append({
        'url': url,
        'name': name,
        'playwright': use_playwright,
        'priority': resolved_priority,
        'venue_priority': resolved_venue_priority,
    })
    SAVED_URLS_FILE.write_text(json.dumps(urls, indent=2))
    return urls


def delete_saved_url(url: str) -> list:
    """Remove a URL from saved list."""
    urls = load_saved_urls()
    urls = [u for u in urls if u['url'] != url]
    SAVED_URLS_FILE.write_text(json.dumps(urls, indent=2))
    return urls


# ============================================================================
# KNOWN VENUE URL → CANONICAL NAME MAPPING
# ============================================================================
# Maps URL domains to their correct venue names.  Prevents operator typos
# (e.g. "shrine" instead of "The Shrine") from polluting the database.
# Add new venues here as they get onboarded.

KNOWN_VENUE_URLS = {
    'tulsashrine.com':              'The Shrine',
    'www.tulsashrine.com':          'The Shrine',
    'thevanguardtulsa.com':         'The Vanguard',
    'www.thevanguardtulsa.com':     'The Vanguard',
    'cainsballroom.com':            "Cain's Ballroom",
    'www.cainsballroom.com':        "Cain's Ballroom",
    'bokcenter.com':                'BOK Center',
    'www.bokcenter.com':            'BOK Center',
    'guthriegreen.com':             'Guthrie Green',
    'www.guthriegreen.com':         'Guthrie Green',
    'philbrook.org':                'Philbrook Museum of Art',
    'www.philbrook.org':            'Philbrook Museum of Art',
    'gilcrease.org':                'Gilcrease Museum',
    'my.gilcrease.org':             'Gilcrease Museum',
    'tulsapac.com':                 'Tulsa PAC',
    'www.tulsapac.com':             'Tulsa PAC',
    'circlecinema.org':             'Circle Cinema',
    'www.circlecinema.org':         'Circle Cinema',
    'gatheringplace.org':           'Gathering Place',
    'www.gatheringplace.org':       'Gathering Place',
    'exposquare.com':               'Expo Square',
    'www.exposquare.com':           'Expo Square',
    'hardrockcasinotulsa.com':      'Hard Rock Hotel & Casino Tulsa',
    'www.hardrockcasinotulsa.com':  'Hard Rock Hotel & Casino Tulsa',
    'tulsatheater.com':             'Tulsa Theater',
    'www.tulsatheater.com':         'Tulsa Theater',
    'mercuryloungetulsa.com':       'Mercury Lounge',
    'www.mercuryloungetulsa.com':   'Mercury Lounge',
    'motherroadmarket.com':         'Mother Road Market',
    'www.motherroadmarket.com':     'Mother Road Market',
    'bobdylancenter.com':           'Bob Dylan Center',
    'www.bobdylancenter.com':       'Bob Dylan Center',
    'thestarlitebar.com':           'Starlite',
    'www.thestarlitebar.com':       'Starlite',
    'discoverylab.org':             'Discovery Lab',
    'www.discoverylab.org':         'Discovery Lab',
    'tulsasymphony.org':            'Tulsa Symphony Orchestra',
    'www.tulsasymphony.org':        'Tulsa Symphony Orchestra',
}


def resolve_source_name(url: str, user_source_name: str) -> str:
    """
    Given a scrape URL and the operator-typed source name, return the
    canonical venue name if we recognize the domain.  Falls back to the
    user-provided name otherwise.
    """
    try:
        domain = urlparse(url).netloc.lower()
        if domain in KNOWN_VENUE_URLS:
            canonical = KNOWN_VENUE_URLS[domain]
            if canonical.lower() != user_source_name.lower():
                print(f"[VenueResolve] '{user_source_name}' → '{canonical}' (from URL)")
            return canonical
    except Exception:
        pass
    return user_source_name


# ============================================================================
# DATE/TIME PATTERN MATCHING
# ============================================================================

# Regex patterns for dates
DATE_PATTERNS = [
    # "Feb 5", "February 5", "Feb 5, 2026", "March 07th, 2026", "March 7th"
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?',
    # Day-first: "05 Mar", "12 April", "3 Jun" (Shrine calendar widget format)
    r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?:\s+\d{4})?\b',
    # "2/5/2026", "02/05/26"
    r'\d{1,2}/\d{1,2}/\d{2,4}',
    # "2026-02-05"
    r'\d{4}-\d{2}-\d{2}',
    # "Thursday, February 5" / "Thursday February 5th" / "Saturday March 07th, 2026"
    r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?',
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
