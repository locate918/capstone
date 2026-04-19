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
import os
import httpx
from scraperUtils import HEADERS


# ──────────────────────────────────────────────────────────────────────
# Residential proxy routing
# ──────────────────────────────────────────────────────────────────────
# Some venues sit behind enterprise bot managers (Akamai, Cloudflare Bot
# Management, PerimeterX, etc.) that silently block ALL traffic from
# datacenter IPs — including Railway, AWS, GCP, and every other major
# cloud provider. No amount of UA spoofing, cookie bootstrapping, or
# TLS mimicry gets past this; the only real fix is to egress through
# a residential IP.
#
# When RESIDENTIAL_PROXY_URL is set (via Railway env vars or local
# .env), Playwright requests to flagged hostnames route through that
# proxy. Everything else continues to egress directly — no unnecessary
# proxy cost for venues that work fine from datacenter IPs.
#
# Setup (one-time):
#   1. Sign up at webshare.io (free tier, 1GB/mo) or iproyal.com
#      (pay-per-GB, ~$1.75/GB)
#   2. Set three env vars in Railway:
#        RESIDENTIAL_PROXY_URL   = http://proxy.provider.com:12321
#        RESIDENTIAL_PROXY_USER  = your-username
#        RESIDENTIAL_PROXY_PASS  = your-password
#   3. Redeploy. TPAC (and any other domain in _PROXY_VENUES) now
#      routes through the residential IP.

# Hostnames that require residential egress. Substring match against
# the URL. Add new entries here as you discover bot-blocked venues.
_PROXY_VENUES: tuple = (
    'am.ticketmaster.com',   # Tulsa PAC (Akamai Bot Manager)
)


def _proxy_for_url(url: str) -> dict | None:
    """Return a Playwright `proxy=` config dict for URLs that need residential
    egress, or None to egress directly. Gated on RESIDENTIAL_PROXY_URL env var:
    if that's unset, always returns None (no behavior change for anyone who
    hasn't wired up a provider)."""
    if not url:
        return None
    server = os.getenv('RESIDENTIAL_PROXY_URL', '').strip()
    url_l = url.lower()
    matches_proxy_venue = any(host in url_l for host in _PROXY_VENUES)

    # Diagnostic: one-time-per-URL log. When a URL matches a proxy venue but
    # the env var isn't visible, this tells us the env is the problem
    # (vs. some other bug). Prints value length only — never the value itself.
    if matches_proxy_venue:
        user_set = bool(os.getenv('RESIDENTIAL_PROXY_USER', '').strip())
        pass_set = bool(os.getenv('RESIDENTIAL_PROXY_PASS', '').strip())
        print(
            f"[Fetcher] Proxy env check for {url!r}: "
            f"URL={'set' if server else 'EMPTY'}, "
            f"USER={'set' if user_set else 'EMPTY'}, "
            f"PASS={'set' if pass_set else 'EMPTY'}",
            flush=True,
        )

    if not server:
        return None
    if not matches_proxy_venue:
        return None

    cfg: dict = {'server': server}
    user = os.getenv('RESIDENTIAL_PROXY_USER', '').strip()
    pw   = os.getenv('RESIDENTIAL_PROXY_PASS', '').strip()
    if user:
        cfg['username'] = user
    if pw:
        cfg['password'] = pw
    return cfg


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
        # CRITICAL: set timezone_id on the browser context. Default headless Chromium
        # runs in UTC, so any venue whose calendar widget renders times client-side
        # (Timely/Starlite, some Squarespace blocks, Google Calendar embeds, etc.)
        # will display every event as UTC. That makes a 9pm CDT show render as
        # "2:00am" the next day. Pinning the context to America/Chicago makes the
        # rendered DOM match what a Tulsa user would see in their browser.
        #
        # Also: check whether this URL needs residential-proxy egress (for
        # venues behind enterprise bot managers that hard-block datacenter IPs).
        # Returns None when RESIDENTIAL_PROXY_URL env isn't set — zero behavior
        # change for anyone not using a proxy provider.
        proxy_cfg = _proxy_for_url(url)
        if proxy_cfg:
            print(f"[Fetcher] Routing through residential proxy for {url}", flush=True)

        context_kwargs: dict = {
            "timezone_id": "America/Chicago",
            "locale":      "en-US",
        }
        if proxy_cfg:
            context_kwargs["proxy"] = proxy_cfg

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.set_extra_http_headers(HEADERS)

        is_etix = 'etix.com' in url
        is_recdesk = 'recdesk.com' in url
        is_ticketleap = 'ticketleap.com' in url
        is_tickettailor = 'tickettailor.com' in url
        is_tpac = 'am.ticketmaster.com/tulsapac' in url
        is_tnew = False
        etix_api_data = []
        recdesk_api_data = []
        tnew_api_data = []
        gcal_api_data = []
        tpac_api_data = {}  # name -> raw JSON text

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

        elif is_tpac:
            # Tulsa PAC / Ticketmaster Account Manager.
            #
            # BOT-DETECTION REALITY (observed in Railway logs):
            #   • Standalone httpx from Railway IPs → HTTP 903 (Akamai soft-block)
            #   • Playwright navigation → succeeds (148KB shell returns fine)
            #   • React hydration in Playwright → blocked (0 event rows ever render)
            #
            # STRATEGY: navigate first to establish an Akamai session (cookies,
            # bot-clearance tokens), THEN hit the 4 public JSON APIs via
            # context.request which reuses the browser's TLS fingerprint,
            # HTTP/2 connection, and cookies. That inherits the "I'm a browser"
            # reputation Playwright earned during navigation — the same
            # endpoints that returned 903 to httpx now return 200.
            #
            # Captured JSON is stapled into the returned HTML as <script>
            # tags (same pattern as Etix/RecDesk/TNEW), so the extractor
            # can parse it without any architecture change.
            await page.set_extra_http_headers({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            })

            # Navigate to let Akamai set session cookies
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"[TulsaPAC] Navigation error (continuing anyway): {e}", flush=True)

            # Brief settle for Akamai bot-manager cookie handshake
            await page.wait_for_timeout(2500)

            # Hit the 4 public APIs through the browser's network stack.
            tpac_base = 'https://am.ticketmaster.com/tulsapac'
            api_targets = [
                ('buy',       '/api/v1/members/events/buy'),
                ('events_p0', '/api/admin/v2/events?_format=json&epoch=upcoming'),
                ('events_p1', '/api/admin/v2/events?_format=json&epoch=upcoming&page=1'),
                ('venues',    '/api/admin/v2/venues?_format=json'),
            ]
            for name, path in api_targets:
                try:
                    resp = await context.request.get(
                        f'{tpac_base}{path}',
                        headers={'Accept': 'application/json'},
                        timeout=20000,
                    )
                    status = resp.status
                    body   = await resp.text()
                    # Accept only actual JSON payloads
                    body_stripped = body.strip()
                    if status == 200 and (body_stripped.startswith('{') or body_stripped.startswith('[')):
                        tpac_api_data[name] = body
                        print(f"[TulsaPAC] {name}: {status} ({len(body)} bytes) ✓", flush=True)
                    else:
                        sample = body[:120].replace('\n', ' ')
                        print(f"[TulsaPAC] {name}: {status} — body sample: {sample!r}", flush=True)
                except Exception as e:
                    print(f"[TulsaPAC] {name} error: {type(e).__name__}: {e}", flush=True)

            html_size = len(await page.content())
            print(f"[TulsaPAC] Page shell: {html_size/1024:.1f}KB, "
                  f"captured {len(tpac_api_data)}/{len(api_targets)} APIs via browser session",
                  flush=True)

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

        if tpac_api_data:
            html += "\n<!-- TPAC_API_DATA -->\n"
            for name, data in tpac_api_data.items():
                # JSON payloads can legally contain "</script>", which would
                # close the tag early and break downstream HTML parsing.
                # Escape by splitting the sequence with a backslash-zero
                # replacement that's invalid inside the JSON we'll parse.
                safe = data.replace('</', '<\\/')
                html += f"<script type='tpac-api-data' data-name='{name}'>{safe}</script>\n"
            print(f"[TulsaPAC] Appended {len(tpac_api_data)} API responses to HTML", flush=True)

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