import os
import asyncio
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.cainsballroom.com/events/"
SOURCE_NAME = "Cain's Ballroom"
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8001")

HEADERS = {
    "User-Agent": "Locate918 Event Aggregator (educational project)"
}

def extract_events_from_html(html: str):
    """
    Parse Cain's Ballroom listing HTML and return a list of event dicts.
    """

    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for a in soup.select('a.url[rel="bookmark"]'):
        title = a.get_text(strip=True) or "Unknown"
        link = (a.get("href") or "").strip()

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.cainsballroom.com" + link

        # dedup by URL
        if link in seen:
            continue
        seen.add(link)

        # find nearby date/doors information by walking up a little
        container = a.parent
        for _ in range(4):
            if container is None:
                break
            container = container.parent

        date_text = "Unknown"
        doors_text = "Unknown"

        if container:
            date_el = container.select_one(".eventDateList #eventDate")
            if date_el:
                date_text = date_el.get_text(strip=True)

            doors_el = container.select_one("span.rhp-event__time-text--list")
            if doors_el:
                doors_text = doors_el.get_text(strip=True)

        events.append({
            "title": title,
            "date": date_text,
            "doors": doors_text,
            "venue": SOURCE_NAME,
            "source": SOURCE_NAME,
            "source_url": link
        })

    return events
    
async def scrape_cains_ballroom(send_to_normalize: bool = False, limit: int = 50):
    """
    Scrape Cain's Ballroom events and optionally send each event to /api/normalize.
     """

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        resp = await client.get(BASE_URL)
        resp.raise_for_status()

        events = extract_events_from_html(resp.text)[:limit]
        print(f"[Cain's] Extracted {len(events)} events")

        if not send_to_normalize:
            for e in events[:5]:
                payload = {
                    "raw_content": str(e),
                    "source_url": e["source_url"],
                    "source_name": SOURCE_NAME
                }
                print(payload)
            return events
            
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
                print("[Cain's] normalize failed:", e["source_url"], ex)

            await asyncio.sleep(1)

        return events
        
if __name__ == "__main__":
    asyncio.run(scrape_cains_ballroom(send_to_normalize=False, limit=25))