"""
Locate918 Async Scraper
=======================
Sequential scraping engine with per-venue normalization.

REWRITE: Replaced concurrent asyncio.gather with sequential processing.
  - Scrapes one venue at a time
  - Normalizes immediately after extraction (Gemini gets dedicated time)
  - Submits to backend before moving to next venue
  - Logs a per-venue report as it goes
  - Configurable delay between venues to avoid Gemini rate limits

This fixes:
  1. Gemini overload from parallel normalization requests
  2. Duplicate events from normalization fallback to raw data
  3. Railway cron crashes (new /cron-scrape endpoint returns JSON, not SSE)
"""

import asyncio
import json
import queue
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Light imports only at module level ───────────────────────────────────────
from scraperUtils import (
    OUTPUT_DIR,
    BACKEND_URL,
    check_robots_txt,
    resolve_source_name,
)

# ── Sequential pacing ────────────────────────────────────────────────────────
# Delay between venues (seconds) — gives Gemini breathing room
VENUE_DELAY = 3
# Delay after a normalization failure before retrying next venue
NORM_FAIL_DELAY = 10

# ── Status persistence ────────────────────────────────────────────────────────
STATUS_FILE = OUTPUT_DIR / "scrape_status.json"
_status_lock = threading.Lock()


def load_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {}
    except Exception:
        return {}


def save_status(status: dict) -> None:
    with _status_lock:
        try:
            STATUS_FILE.write_text(json.dumps(status, indent=2))
        except Exception as e:
            print(f"[Status] Write failed: {e}")


# ── Lazy extractor loader ─────────────────────────────────────────────────────
_extractors = None

def _get_extractors():
    """Import scraperExtractors on first call, then cache."""
    global _extractors
    if _extractors is None:
        from scraperExtractors import (
            extract_eventcalendarapp,
            extract_timely,
            extract_bok_center,
            extract_circle_cinema_events,
            extract_expo_square_events,
            extract_eventbrite_api_events,
            extract_simpleview_events,
            extract_sitewrench_events,
            extract_recdesk_events,
            extract_ticketleap_events,
            extract_libnet_events,
            extract_philbrook_events,
            extract_tulsapac_events,
            extract_roosterdays_events,
            extract_tulsabrunchfest_events,
            extract_okeq_events,
            extract_flywheel_events,
            extract_arvest_events,
            extract_tulsatough_events,
            extract_gradient_events,
            extract_tulsafarmersmarket_events,
            extract_okcastle_events,
            extract_broken_arrow_events,
            extract_tulsazoo_events,
            extract_hardrock_tulsa_events,
            extract_gypsy_events,
            extract_badass_renees_events,
            extract_rocklahoma_events,
            extract_tulsa_oktoberfest_events,
            extract_events_universal,
            fetch_with_httpx,
            fetch_with_playwright,
        )
        _extractors = {
            'chain': [
                (extract_eventcalendarapp,          "EventCalendarApp API"),
                (extract_timely,                    "Timely API"),
                (extract_bok_center,                "BOK Center API"),
                (extract_circle_cinema_events,      "Circle Cinema"),
                (extract_expo_square_events,        "Expo Square API"),
                (extract_eventbrite_api_events,     "Eventbrite API"),
                (extract_simpleview_events,         "Simpleview API"),
                (extract_sitewrench_events,         "SiteWrench API"),
                (extract_recdesk_events,            "RecDesk API"),
                (extract_ticketleap_events,         "TicketLeap"),
                (extract_libnet_events,             "LibNet API"),
                (extract_philbrook_events,          "Philbrook AJAX"),
                (extract_tulsapac_events,           "TulsaPAC API"),
                (extract_roosterdays_events,        "RoosterDays"),
                (extract_tulsabrunchfest_events,    "TulsaBrunchFest"),
                (extract_okeq_events,               "OKEQ"),
                (extract_flywheel_events,           "Flywheel"),
                (extract_arvest_events,             "Arvest"),
                (extract_tulsatough_events,         "TulsaTough"),
                (extract_gradient_events,           "Gradient"),
                (extract_tulsafarmersmarket_events, "TFM"),
                (extract_okcastle_events,           "OKCastle"),
                (extract_broken_arrow_events,       "BrokenArrow"),
                (extract_tulsazoo_events,           "TulsaZoo"),
                (extract_hardrock_tulsa_events,     "HardRockTulsa"),
                (extract_gypsy_events,              "Gypsy"),
                (extract_badass_renees_events,      "BadAssRenees"),
                (extract_rocklahoma_events,         "Rocklahoma"),
                (extract_tulsa_oktoberfest_events,  "TulsaOktoberfest"),
            ],
            'universal':       extract_events_universal,
            'fetch_httpx':     fetch_with_httpx,
            'fetch_playwright': fetch_with_playwright,
        }
    return _extractors


# ── Future date filter ────────────────────────────────────────────────────────

def _apply_future_filter(events: list) -> list:
    from dateutil import parser as _dp
    now = datetime.now()
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    filtered = []
    for ev in events:
        date_str = (ev.get('date') or ev.get('date_start') or ev.get('start_time') or '')
        if not date_str:
            filtered.append(ev)
            continue
        try:
            dt = _dp.parse(str(date_str), fuzzy=True).replace(tzinfo=None)
            if dt < cutoff:
                days_past = (cutoff - dt).days
                if days_past > 270:
                    dt = dt.replace(year=dt.year + 1)
                    ev['date'] = dt.strftime('%b %d, %Y')
                    if dt >= cutoff:
                        filtered.append(ev)
                else:
                    end_str = (ev.get('end_date') or ev.get('end_time') or ev.get('date_end') or '')
                    if end_str:
                        try:
                            end_dt = _dp.parse(str(end_str), fuzzy=True).replace(tzinfo=None)
                            if end_dt >= cutoff:
                                filtered.append(ev)
                                continue
                        except Exception:
                            pass
            else:
                filtered.append(ev)
        except Exception:
            filtered.append(ev)
    return filtered


# ── Core extraction chain ─────────────────────────────────────────────────────

async def run_extraction_chain(html: str, name: str, url: str,
                               future_only: bool = True) -> tuple:
    ext = _get_extractors()
    events: list = []
    methods: list = []

    for fn, label in ext['chain']:
        if events:
            break
        try:
            evs, detected = await fn(html, name, url, future_only)
            if detected and evs:
                events = evs
                methods.append(f"{label} ({len(evs)})")
                print(f"[{label}] {name}: {len(evs)} events")
        except Exception as e:
            print(f"[{label}] {name}: {e}")

    if not events:
        univ = ext['universal'](html, url, name)
        if univ:
            if '_extraction_methods' in univ[0]:
                methods = univ[0]['_extraction_methods']
                for e in univ:
                    e.pop('_extraction_methods', None)
            events = univ

    if future_only and events:
        events = _apply_future_filter(events)

    return events, methods


# ── DB pipeline (single venue) ───────────────────────────────────────────────

def _post_events_to_db(events: list, url: str, name: str,
                       source_priority: int = None) -> tuple:
    """
    Normalize then post events for ONE venue. Returns (db_saved, norm_ok).
    Sequential design means Gemini only handles one venue at a time.
    """
    import httpx as _httpx
    try:
        from scraperRoutes import normalize_batch, transform_event_for_backend
    except ImportError as e:
        print(f"[DB] Import error: {e}")
        return 0, False

    print(f"[DB] Normalizing {len(events)} events for {name}...")
    normalized = normalize_batch(events, source_url=url, source_name=name)
    normalization_succeeded = bool(normalized)

    if normalization_succeeded:
        print(f"[DB] ✓ Normalized {len(events)} → {len(normalized)} for {name}")
    else:
        print(f"[DB] ⚠ Normalization failed for {name}, using raw fallback")

    to_post = normalized if normalized else events
    saved = 0
    errors = 0
    for ev in to_post:
        try:
            xf = transform_event_for_backend(ev, source_priority=source_priority)
            if not xf.get('source_url'):
                xf['source_url'] = url
            if not xf.get('source_name'):
                xf['source_name'] = name
            resp = _httpx.post(f"{BACKEND_URL}/api/events", json=xf, timeout=10)
            if resp.status_code in [200, 201]:
                saved += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            print(f"[DB] {name}: {e}")

    print(f"[DB] {name}: {saved}/{len(to_post)} saved to DB ({errors} errors)")
    return saved, normalization_succeeded


# ── Single source scraper ─────────────────────────────────────────────────────

async def scrape_one(entry: dict,
                     sem_pw: asyncio.Semaphore = None,
                     sem_http: asyncio.Semaphore = None) -> dict:
    """Scrape a single venue. Semaphores are optional for sequential mode."""
    url    = entry.get('url', '')
    name   = resolve_source_name(url, entry.get('name', 'unknown'))
    use_pw = entry.get('use_playwright', entry.get('playwright', True))
    prio   = entry.get('priority', entry.get('venue_priority'))

    result = {
        'url':          url,
        'name':         name,
        'use_playwright': use_pw,
        'status':       'error',
        'event_count':  0,
        'events':       [],
        'methods':      [],
        'last_scraped': datetime.now().isoformat(),
        'error':        None,
        'error_report': None,
        'db_saved':     0,
        'norm_failed':  False,
    }

    try:
        robots = check_robots_txt(url)
        if not robots['allowed']:
            result['error'] = 'Blocked by robots.txt'
            return result

        ext = _get_extractors()

        # Use semaphore if provided (GUI mode), otherwise just fetch
        if use_pw:
            if sem_pw:
                async with sem_pw:
                    html = await ext['fetch_playwright'](url)
            else:
                html = await ext['fetch_playwright'](url)
        else:
            if sem_http:
                async with sem_http:
                    html = await ext['fetch_httpx'](url)
            else:
                html = await ext['fetch_httpx'](url)

        events, methods = await run_extraction_chain(html, name, url)
        result.update({
            'events':      events,
            'methods':     methods,
            'event_count': len(events),
            'status':      'working' if events else 'empty',
        })

        if events:
            # Save JSON backup
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = re.sub(r'[^\w\-]', '_', name)
            (OUTPUT_DIR / f"{safe}_{ts}.json").write_text(
                json.dumps(events, indent=2), encoding='utf-8'
            )

            # Normalize + submit to DB (synchronous — one venue at a time)
            loop = asyncio.get_event_loop()
            db_saved, norm_ok = await loop.run_in_executor(
                None, _post_events_to_db, events, url, name, prio
            )
            result['db_saved'] = db_saved
            result['norm_failed'] = not norm_ok

    except Exception as exc:
        tb = traceback.format_exc()
        result['error'] = str(exc)
        try:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = re.sub(r'[^\w\-]', '_', name)
            rname = f"error_{safe}_{ts}.json"
            (OUTPUT_DIR / rname).write_text(json.dumps({
                'url':       url,
                'name':      name,
                'error':     str(exc),
                'traceback': tb,
                'timestamp': result['last_scraped'],
            }, indent=2), encoding='utf-8')
            result['error_report'] = rname
        except Exception:
            pass

    return result


async def scrape_one_standalone(entry: dict) -> dict:
    """Standalone single-venue scrape (no semaphores)."""
    result = await scrape_one(entry)

    status = load_status()
    status[entry.get('url', '')] = {
        'name':         result['name'],
        'last_scraped': result['last_scraped'],
        'status':       result['status'],
        'event_count':  result['event_count'],
        'methods':      result['methods'],
        'error':        result['error'],
        'error_report': result['error_report'],
    }
    save_status(status)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SEQUENTIAL FULL RUN  (replaces concurrent scrape_all_prioritized)
# ══════════════════════════════════════════════════════════════════════════════

async def scrape_all_sequential(saved: list, q: queue.Queue = None) -> dict:
    """
    Scrape all venues ONE AT A TIME in priority order.

    Pipeline per venue:
      1. Fetch HTML
      2. Extract events
      3. Normalize via Gemini (dedicated, no contention)
      4. Submit to backend
      5. Log result
      6. Wait VENUE_DELAY seconds before next venue

    Returns a summary report dict (useful for /cron-scrape JSON response).
    """
    tiers: dict = {1: [], 2: [], 3: []}
    for entry in saved:
        p = entry.get('priority', entry.get('venue_priority', 3)) or 3
        tiers[min(max(int(p), 1), 3)].append(entry)

    total          = len(saved)
    status_data    = load_status()
    completed      = 0
    total_events   = 0
    total_saved_db = 0
    norm_failures  = 0
    errors         = []
    venue_reports  = []

    def _emit(msg):
        """Send to SSE queue if available, otherwise just print."""
        if q:
            q.put(msg)
        print(f"[Scraper] {msg.get('type', '')}: {msg.get('name', msg.get('total_sources', ''))}")

    _emit({
        'type': 'start',
        'total_sources': total,
        'p1': len(tiers[1]),
        'p2': len(tiers[2]),
        'p3': len(tiers[3]),
    })

    start_time = datetime.now()

    for tier_num in [1, 2, 3]:
        tier = tiers[tier_num]
        if not tier:
            continue

        _emit({'type': 'tier_start', 'tier': tier_num, 'count': len(tier)})

        # ── SEQUENTIAL: one venue at a time ──────────────────────────────
        for entry in tier:
            url  = entry.get('url', '')
            name = resolve_source_name(url, entry.get('name', ''))

            _emit({
                'type': 'source_start',
                'name': name,
                'url':  url,
                'tier': tier_num,
            })

            # Scrape this single venue (fetch → extract → normalize → submit)
            result = await scrape_one(entry)
            completed += 1

            total_events   += result['event_count']
            total_saved_db += result['db_saved']

            if result.get('norm_failed'):
                norm_failures += 1
            if result.get('error'):
                errors.append({'name': name, 'error': result['error']})

            # Build per-venue report
            venue_report = {
                'name':         result['name'],
                'url':          url,
                'tier':         tier_num,
                'status':       result['status'],
                'event_count':  result['event_count'],
                'db_saved':     result['db_saved'],
                'norm_failed':  result.get('norm_failed', False),
                'methods':      result['methods'],
                'error':        result['error'],
            }
            venue_reports.append(venue_report)

            # Update persistent status
            status_data[url] = {
                'name':         result['name'],
                'last_scraped': result['last_scraped'],
                'status':       result['status'],
                'event_count':  result['event_count'],
                'methods':      result['methods'],
                'error':        result['error'],
                'error_report': result['error_report'],
                'norm_failed':  result.get('norm_failed', False),
            }
            save_status(status_data)

            _emit({
                'type':         'source_done',
                'name':         result['name'],
                'url':          url,
                'tier':         tier_num,
                'status':       result['status'],
                'event_count':  result['event_count'],
                'methods':      result['methods'],
                'db_saved':     result['db_saved'],
                'error':        result['error'],
                'error_report': result['error_report'],
                'completed':    completed,
                'total':        total,
            })

            # ── Pacing delay ─────────────────────────────────────────────
            if result.get('norm_failed'):
                # Extra delay after norm failure so Gemini can recover
                print(f"[Pacing] Norm failed for {name}, waiting {NORM_FAIL_DELAY}s...")
                await asyncio.sleep(NORM_FAIL_DELAY)
            else:
                await asyncio.sleep(VENUE_DELAY)

    # ── Normalization retry pass ─────────────────────────────────────────────
    retry_venues = [r for r in venue_reports if r.get('norm_failed') and r['event_count'] > 0]

    if retry_venues:
        print(f"\n[NormRetry] Retrying {len(retry_venues)} venue(s) after 30s cooldown...")
        _emit({'type': 'norm_retry_start', 'count': len(retry_venues)})
        await asyncio.sleep(30)

        try:
            from scraperRoutes import normalize_batch, transform_event_for_backend
            import httpx as _httpx

            for vr in retry_venues:
                url  = vr['url']
                name = vr['name']
                sdata = status_data.get(url, {})
                # Reload events from the saved JSON file
                events = sdata.get('events', [])
                if not events:
                    # Try to find the most recent JSON file for this venue
                    safe = re.sub(r'[^\w\-]', '_', name)
                    json_files = sorted(OUTPUT_DIR.glob(f"{safe}_*.json"), reverse=True)
                    if json_files:
                        try:
                            events = json.loads(json_files[0].read_text())
                        except Exception:
                            pass

                if not events:
                    print(f"[NormRetry] {name}: no events to retry")
                    continue

                prio = next(
                    (e.get('priority', e.get('venue_priority'))
                     for e in saved if e.get('url') == url),
                    None
                )

                print(f"[NormRetry] Retrying: {name} ({len(events)} events)")
                normalized = normalize_batch(events, source_url=url, source_name=name)
                if normalized:
                    retry_saved = 0
                    for ev in normalized:
                        try:
                            xf = transform_event_for_backend(ev, source_priority=prio)
                            if not xf.get('source_url'): xf['source_url'] = url
                            if not xf.get('source_name'): xf['source_name'] = name
                            resp = _httpx.post(f"{BACKEND_URL}/api/events", json=xf, timeout=10)
                            if resp.status_code in [200, 201]:
                                retry_saved += 1
                                total_saved_db += 1
                        except Exception as e:
                            print(f"[NormRetry] {name}: {e}")
                    print(f"[NormRetry] {name}: {retry_saved}/{len(normalized)} saved")
                    _emit({'type': 'norm_retry_done', 'name': name, 'saved': retry_saved})
                else:
                    print(f"[NormRetry] {name}: still failing")
                    _emit({'type': 'norm_retry_done', 'name': name, 'saved': 0})

                # Delay between retries too
                await asyncio.sleep(VENUE_DELAY)

        except Exception as e:
            print(f"[NormRetry] Error: {e}")

    elapsed = (datetime.now() - start_time).total_seconds()

    summary = {
        'type':              'complete',
        'total_sources':     total,
        'sources_scraped':   completed,
        'total_events':      total_events,
        'total_saved':       total_saved_db,
        'norm_failures':     norm_failures,
        'error_count':       len(errors),
        'errors':            errors[:20],  # Cap error list
        'venues':            venue_reports,
        'elapsed_seconds':   round(elapsed, 1),
        'timestamp':         datetime.now().isoformat(),
    }

    _emit(summary)
    if q:
        q.put(None)  # Signal SSE stream to close

    # Save summary report
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (OUTPUT_DIR / f"scrape_report_{ts}.json").write_text(
            json.dumps(summary, indent=2), encoding='utf-8'
        )
    except Exception:
        pass

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY COMPAT: scrape_all_prioritized wraps sequential with SSE queue
# ══════════════════════════════════════════════════════════════════════════════

async def scrape_all_prioritized(saved: list, q: queue.Queue) -> None:
    """SSE-compatible wrapper. Used by /scrape-all GUI endpoint."""
    await scrape_all_sequential(saved, q=q)


# ══════════════════════════════════════════════════════════════════════════════
# CRON ENTRY POINT: returns summary dict, no SSE
# ══════════════════════════════════════════════════════════════════════════════

async def scrape_all_cron(saved: list) -> dict:
    """
    Entry point for /cron-scrape. Runs sequentially, returns JSON summary.
    No queue, no SSE, no threading — just scrape and report.
    """
    return await scrape_all_sequential(saved, q=None)