import os
import asyncio
import httpx
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

LIST_URL = "https://www.visittulsa.com/events/?bounds=false&view=list&sort=date"
SITE_BASE = "https://www.visittulsa.com"
SOURCE_NAME = "Visit Tulsa"
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8001")

HEADERS = {
    "User-Agent": "Locate918 Event Aggregator (educational project)"
}


async def get_rendered_html(page, url: str, timeout_ms: int = 30000) -> str:
    """
    User Playwright page to load a JS page and return the fully rendered HTML.
    """

    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    # Wait for the event items to appear
    await page.wait_for_selector('div.item[data-type="events"]', timeout=timeout_ms)

    # Extra safety: let JS finish populating
    await page.wait_for_timeout(1000)

    return await page.content()

async def discover_event_links(page, limit: int = 30):
    """
    Discover event links from the list page using Playwright.
    """
    html = await get_rendered_html(page, LIST_URL)
    soup = BeautifulSoup(html, "html.parser")

    seen = set()
    events_data = []

    # Find all event cards
    for item in soup.select('div.item[data-type="events"]'):
        # get the event link
        link_el = item.select_one("a[href]")
        if not link_el:
            continue
        
        href = (link_el.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue

        if not href.startswith("/event/"):
            continue

        if "/event/rss" in href or "/event/ical" in href:
            continue

        full_url = SITE_BASE + href

        if full_url in seen:
            continue
        seen.add(full_url)

        # Extract venue from the list page
        venue_el = item.select_one("li.locations a") # Adjust selector if needed
        venue = venue_el.get_text(strip=True) if venue_el else "Unknown"

        events_data.append((full_url, venue))

        if len(events_data) >= limit:
            break

    return events_data

async def parse_event_detail(page, url: str, venue_from_list: str):
    """
    Navigate to event detail page and extract all information including time.
    """

    # Navigate to the detail page
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait for content to load
    await page.wait_for_selector("h1", timeout=10000)
    await page.wait_for_timeout(500)

    # Get the rendered HTML
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Title
    h1 = soup.select_one("h1")
    title = h1.get_text(strip=True) if h1 else "Unknown"

    date_text = "Unknown"
    time_text = "Unknown"
    venue_text = venue_from_list

    for dl in soup.find_all("dl"):
            dts = dl.select("dt")
            for dt in dts:
                dt_text = dt.get_text(strip=True)
                dd = dt.find_next_sibling("dd")

            # Extract Dates
                if "Date" in dt_text or "Recurrence" in dt_text:
                    if dd:
                        date_text = dd.get_text(strip=True)

            # Extract Time
                elif "Time" in dt_text:
                    if dd:
                        time_text = dd.get_text(strip=True)

            # Extract Venue/Presenter
                elif "Presented By" in dt_text or "Venue" in dt_text:
                    if dd:
                        venue_text = dd.get_text(strip=True)

    return {
        "title": title,
        "date": date_text,
        "doors": time_text,
        "venue": venue_text,
        "source": SOURCE_NAME,
        "source_url": url
    }

async def scrape_visit_tulsa(send_to_normalize: bool=False, limit: int=50):
    """
    Scrape Visit Tulsa events and optionally send each event to normalize.
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_extra_http_headers({
            "User-Agent": HEADERS["User-Agent"]
        })

        # Discover event links from the list page
        events_data = await discover_event_links(page, limit=limit)
        print(f"[{SOURCE_NAME}] Found {len(events_data)} event links")

        events = []

        # Parse each event detail page
        for i, (url, venue) in enumerate(events_data, start = 1):
            try:
                evt = await parse_event_detail(page, url, venue)
                events.append(evt)
                print(f"[{SOURCE_NAME}] Scraped {i}/{len(events_data)}: {evt['title']}")

                # Polite rate limit
                await asyncio.sleep(1)

            except Exception as ex:
                print(f"[{SOURCE_NAME}] Failed to scrape {url}: {ex}")

        await browser.close()

    print(f"[{SOURCE_NAME}] Extracted {len(events)} events")

    # Send to normalize if requested
    if not send_to_normalize:
        for e in events:
            payload = {
                "raw_content": str(e),
                "source_url": e["source_url"],
                "source_name": SOURCE_NAME
            }
            print(payload)
        return events
    
    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        for e in events:
            payload = {
                "raw_content": str(e),
                "source_url": e["source_url"],
                "source_name": SOURCE_NAME
            }

            try:
                r = await client.post(f"{LLM_SERVICE_URL}/api/normalize", json=payload)
                r.raise_for_status()
            except Exception as ex:
                print(f"[{SOURCE_NAME}] normalize failed:", e["source_url"], ex)

            await asyncio.sleep(1)

    return events
    
if __name__ == "__main__":
    asyncio.run(scrape_visit_tulsa(send_to_normalize=False, limit=10))
        