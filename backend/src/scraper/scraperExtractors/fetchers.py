"""
Locate918 Scraper - Page Fetching
==================================
HTTP (httpx) and browser (Playwright) page fetching with API interception
for Etix, RecDesk, TNEW/Tessitura, and Google Calendar.

FIX: TNEW false positives — the manual /api/products/productionseasons fetch
now validates that the response is actually JSON before injecting it.
Previously, non-TNEW sites returned HTML which caused JSON parse errors.
"""

import json
import httpx
from scraperUtils import HEADERS


async def fetch_with_httpx(url: str) -> str:
    """Fetch a page using httpx (no JavaScript rendering)."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def fetch_with_playwright(url: str) -> str:
    """
    Fetch a page using Playwright (full JavaScript rendering).

    Handles platform-specific API interception:
    - Etix: Captures /api/ responses during page load
    - RecDesk: Captures GetCalendarItems API, triggers manually if needed
    - TicketLeap: Waits for React to render event cards
    - Generic: Captures TNEW and Google Calendar API responses
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers(HEADERS)

        is_etix = 'etix.com' in url
        is_recdesk = 'recdesk.com' in url
        is_ticketleap = 'ticketleap.com' in url
        is_tickettailor = 'tickettailor.com' in url
        is_tnew = False
        etix_api_data = []
        recdesk_api_data = []
        tnew_api_data = []
        gcal_api_data = []

        if is_etix:
            async def capture_response(response):
                url_str = response.url
                if any(p in url_str for p in ['/api/', '/online/', '/ticket/v/', '/performances',
                                              '/events', '/search', '/organization', '/listings']):
                    try:
                        ct = response.headers.get('content-type', '')
                        if 'json' in ct or 'javascript' in ct:
                            body = await response.text()
                            etix_api_data.append(body)
                            print(f"[Etix] Captured API response ({len(body)} bytes) from {url_str[:80]}...")
                    except:
                        pass

            page.on('response', capture_response)

            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
            except:
                await page.goto(url, timeout=60000)

            try:
                await page.wait_for_selector(
                    '[class*="performance"], [class*="event-card"], [class*="MuiCard"], '
                    '[class*="event"], [class*="upcoming"], [class*="EventCard"], '
                    '[class*="listing"], a[href*="/ticket/p/"], h3, h4',
                    timeout=20000
                )
            except:
                pass

            # Extra wait for React hydration + scroll to trigger lazy loading
            await page.wait_for_timeout(5000)
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(3000)
            await page.evaluate('window.scrollTo(0, 0)')
            await page.wait_for_timeout(2000)

            html_size = len(await page.content())
            print(f"[Etix] Page rendered: {html_size/1024:.1f}KB, captured {len(etix_api_data)} API responses")

        elif is_recdesk:
            async def capture_recdesk_response(response):
                if 'GetCalendarItems' in response.url:
                    try:
                        body = await response.text()
                        recdesk_api_data.append(body)
                        print(f"[RecDesk] Captured API response ({len(body)} bytes)")
                    except:
                        pass

            page.on('response', capture_recdesk_response)

            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except:
                await page.goto(url, timeout=45000)

            await page.wait_for_timeout(3000)

            if not recdesk_api_data:
                print(f"[RecDesk] No auto API call detected, triggering manually...")
                try:
                    api_result = await page.evaluate('''
                        async () => {
                            try {
                                const resp = await fetch(
                                    window.location.origin + '/Community/Calendar/GetCalendarItems',
                                    {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                            'X-Requested-With': 'XMLHttpRequest'
                                        },
                                        body: '{}'
                                    }
                                );
                                const text = await resp.text();
                                return text;
                            } catch(e) {
                                return '__ERROR__' + e.message;
                            }
                        }
                    ''')
                    if api_result and not api_result.startswith('__ERROR__'):
                        recdesk_api_data.append(api_result)
                        print(f"[RecDesk] Manual fetch captured ({len(api_result)} bytes)")
                    else:
                        print(f"[RecDesk] Manual fetch failed: {api_result}")
                except Exception as e:
                    print(f"[RecDesk] Manual fetch error: {e}")

        elif is_ticketleap:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except:
                await page.goto(url, timeout=30000)

            try:
                await page.wait_for_selector(
                    'button, a[href*="/tickets/"], [class*="event"]',
                    timeout=10000
                )
            except:
                pass

            await page.wait_for_timeout(3000)
            print(f"[TicketLeap] Page rendered: {len(await page.content())/1024:.1f}KB")

        elif is_tickettailor:
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except:
                await page.goto(url, timeout=45000)

            # TicketTailor renders event cards via JS — wait for them
            try:
                await page.wait_for_selector(
                    '[class*="event"], [class*="listing"], [class*="card"], '
                    'a[href*="/events/"], a[href*="/tickets/"]',
                    timeout=15000
                )
            except:
                pass

            await page.wait_for_timeout(3000)
            # Scroll to load any lazy content
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(2000)
            print(f"[TicketTailor] Page rendered: {len(await page.content())/1024:.1f}KB")

        else:
            # ── Generic handler with TNEW and Google Calendar detection ──
            async def capture_generic_response(response):
                nonlocal is_tnew
                url_str = response.url

                # Capture TNEW (Tessitura) API responses
                if '/api/products/productionseasons' in url_str or '/api/products/performances' in url_str:
                    try:
                        ct = response.headers.get('content-type', '')
                        if 'json' in ct:
                            body = await response.text()
                            # FIX: Validate it's actual JSON, not HTML
                            body_stripped = body.strip()
                            if body_stripped.startswith('[') or body_stripped.startswith('{'):
                                tnew_api_data.append(body)
                                is_tnew = True
                                print(f"[TNEW] Captured API response ({len(body)} bytes)")
                            else:
                                print(f"[TNEW] Response looks like HTML, skipping")
                    except:
                        pass

                # Capture Google Calendar API responses
                elif ('googleapis.com/calendar/v3/calendars/' in url_str or
                      'clients6.google.com/calendar/v3/calendars/' in url_str):
                    try:
                        ct = response.headers.get('content-type', '')
                        if 'json' in ct:
                            body = await response.text()
                            gcal_api_data.append(body)
                            print(f"[GCal] Captured API response ({len(body)} bytes)")
                    except:
                        pass

            page.on('response', capture_generic_response)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except:
                await page.goto(url, timeout=30000)

            # Wait for calendar/event widgets to load
            await page.wait_for_timeout(5000)

            try:
                await page.wait_for_selector(
                    '[class*="event"], [class*="calendar"], [class*="timely"], '
                    'iframe[src*="calendar.google.com"]',
                    timeout=5000
                )
            except:
                pass

            # Check for Google Calendar iframe
            if not gcal_api_data:
                try:
                    for frame in page.frames:
                        if 'calendar.google.com' in (frame.url or ''):
                            print(f"[GCal] Found Google Calendar iframe")
                            await page.wait_for_timeout(3000)
                            break
                except:
                    pass

            # ── FIX: TNEW false positive guard ──
            # Only attempt manual TNEW fetch if we haven't already captured data
            # AND we validate the response is real JSON (not HTML from a non-TNEW site)
            if not tnew_api_data:
                try:
                    tnew_result = await page.evaluate('''
                        async () => {
                            try {
                                const resp = await fetch(
                                    window.location.origin + '/api/products/productionseasons',
                                    {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                            'X-Requested-With': 'XMLHttpRequest'
                                        },
                                        body: JSON.stringify({})
                                    }
                                );
                                // Only return if response is JSON
                                const ct = resp.headers.get('content-type') || '';
                                if (!ct.includes('json')) return '__NOTJSON__';
                                if (!resp.ok) return '__NOTFOUND__';
                                const text = await resp.text();
                                // Validate it starts with [ or { (actual JSON, not HTML)
                                const trimmed = text.trim();
                                if (!trimmed.startsWith('[') && !trimmed.startsWith('{')) return '__NOTJSON__';
                                return text;
                            } catch(e) {
                                return '__ERROR__' + e.message;
                            }
                        }
                    ''')
                    if (tnew_result and
                            not tnew_result.startswith('__ERROR__') and
                            not tnew_result.startswith('__NOTFOUND__') and
                            not tnew_result.startswith('__NOTJSON__')):
                        tnew_api_data.append(tnew_result)
                        is_tnew = True
                        print(f"[TNEW] Manual fetch captured ({len(tnew_result)} bytes)")
                except Exception:
                    pass  # Not a TNEW site, silently continue

        # ── WordPress / Tribe Events Calendar pagination ──
        # Tribe paginates via /events/page/2/, /events/page/3/ etc.
        # Follow next-page links up to MAX_PAGES and concatenate all HTML.
        MAX_TRIBE_PAGES = 5
        all_html_parts = []
        current_html = await page.content()
        all_html_parts.append(current_html)

        from bs4 import BeautifulSoup as _BS4
        for _pg in range(2, MAX_TRIBE_PAGES + 1):
            try:
                _soup = _BS4(current_html, 'html.parser')
                # Tribe next-page link selectors
                next_link = (
                        _soup.select_one('a.tribe-events-nav-next') or
                        _soup.select_one('a[rel="next"]') or
                        _soup.select_one('.tribe-events-c-nav__next a') or
                        _soup.select_one('a.next.page-numbers')
                )
                if not next_link or not next_link.get('href'):
                    break
                next_url = next_link['href']
                # Sanity check — must be on same domain
                from urllib.parse import urlparse as _urlparse
                if _urlparse(next_url).netloc and _urlparse(next_url).netloc != _urlparse(url).netloc:
                    break
                print(f"[Pagination] Following page {_pg}: {next_url}")
                try:
                    await page.goto(next_url, wait_until="domcontentloaded", timeout=20000)
                except:
                    await page.goto(next_url, timeout=20000)
                await page.wait_for_timeout(2500)
                current_html = await page.content()
                all_html_parts.append(current_html)
            except Exception as _pe:
                print(f"[Pagination] Stopped at page {_pg}: {_pe}")
                break

        if len(all_html_parts) > 1:
            print(f"[Pagination] Fetched {len(all_html_parts)} pages total")
            # Combine: keep first page head/body wrapper, append inner bodies from extras
            combined = all_html_parts[0]
            for _extra in all_html_parts[1:]:
                _s = _BS4(_extra, 'html.parser')
                _body = _s.find('body')
                combined += f"\n<!-- PAGINATION_PAGE -->\n{str(_body) if _body else _extra}"
        else:
            combined = all_html_parts[0]

        # ── Collect HTML and inject captured API data ──
        html = combined

        if etix_api_data:
            html += "\n<!-- ETIX_API_DATA -->\n"
            for data in etix_api_data:
                html += f"<script type='etix-api-data'>{data}</script>\n"
            print(f"[Etix] Appended {len(etix_api_data)} API responses to HTML")

        if recdesk_api_data:
            html += "\n<!-- RECDESK_API_DATA -->\n"
            for data in recdesk_api_data:
                html += f"<script type='recdesk-api-data'>{data}</script>\n"
            print(f"[RecDesk] Appended {len(recdesk_api_data)} API responses to HTML")

        if tnew_api_data:
            html += "\n<!-- TNEW_API_DATA -->\n"
            for data in tnew_api_data:
                html += f"<script type='tnew-api-data'>{data}</script>\n"
            print(f"[TNEW] Appended {len(tnew_api_data)} API responses to HTML")

        if gcal_api_data:
            html += "\n<!-- GCAL_API_DATA -->\n"
            for data in gcal_api_data:
                html += f"<script type='gcal-api-data'>{data}</script>\n"
            print(f"[GCal] Appended {len(gcal_api_data)} API responses to HTML")

        # Also capture iframe content
        try:
            for frame in page.frames:
                if frame != page.main_frame:
                    try:
                        frame_content = await frame.content()
                        html += f"\n<!-- IFRAME_CONTENT -->\n{frame_content}"
                    except:
                        pass
        except:
            pass

        await browser.close()
    return html