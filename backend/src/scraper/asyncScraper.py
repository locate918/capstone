"""
Locate918 Async Scraper
=======================
Priority-based concurrent scraping engine.

Extractors are imported lazily on first use — this keeps Flask startup
fast so the GUI loads immediately.
"""

import asyncio
import json
import queue
import re
import threading
import traceback
from datetime import datetime
from pathlib import Path

# ── Light imports only at module level ───────────────────────────────────────
# scraperUtils is tiny; scraperExtractors/scraperRoutes are heavy and lazy.
from scraperUtils import (
    OUTPUT_DIR,
    BACKEND_URL,
    check_robots_txt,
    resolve_source_name,
)

# ── Concurrency caps ──────────────────────────────────────────────────────────
PW_CONCURRENCY   = 3
HTTP_CONCURRENCY = 8

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


# ── DB pipeline ───────────────────────────────────────────────────────────────

def _post_events_to_db(events: list, url: str, name: str,
                       source_priority: int = None) -> tuple:
    """Returns (db_saved, normalization_succeeded)."""
    import httpx as _httpx
    try:
        from scraperRoutes import normalize_batch, transform_event_for_backend
    except ImportError as e:
        print(f"[DB] Import error: {e}")
        return 0, False

    normalized = normalize_batch(events, source_url=url, source_name=name)
    normalization_succeeded = bool(normalized)
    to_post = normalized if normalized else events
    saved = 0
    for ev in to_post:
        try:
            xf = transform_event_for_backend(ev, source_priority=source_priority)
            if not xf.get('source_url'):
                xf['source_url'] = url
            if not xf.get('source_name'):
                xf['source_name'] = name
            resp = _httpx.post(f"{BACKEND_URL}/api/events", json=xf, timeout=5)
            if resp.status_code in [200, 201]:
                saved += 1
        except Exception as e:
            print(f"[DB] {name}: {e}")
    return saved, normalization_succeeded


# ── Single source scraper ─────────────────────────────────────────────────────

async def scrape_one(entry: dict,
                     sem_pw: asyncio.Semaphore,
                     sem_http: asyncio.Semaphore) -> dict:
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
    }

    try:
        robots = check_robots_txt(url)
        if not robots['allowed']:
            result['error'] = 'Blocked by robots.txt'
            return result

        ext = _get_extractors()
        sem = sem_pw if use_pw else sem_http
        async with sem:
            fetch_fn = ext['fetch_playwright'] if use_pw else ext['fetch_httpx']
            html = await fetch_fn(url)

        events, methods = await run_extraction_chain(html, name, url)
        result.update({
            'events':      events,
            'methods':     methods,
            'event_count': len(events),
            'status':      'working' if events else 'empty',
        })

        if events:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = re.sub(r'[^\w\-]', '_', name)
            (OUTPUT_DIR / f"{safe}_{ts}.json").write_text(
                json.dumps(events, indent=2), encoding='utf-8'
            )
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
    sem_pw   = asyncio.Semaphore(1)
    sem_http = asyncio.Semaphore(1)
    result = await scrape_one(entry, sem_pw, sem_http)

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


# ── Priority-based full run ───────────────────────────────────────────────────

async def scrape_all_prioritized(saved: list, q: queue.Queue) -> None:
    sem_pw   = asyncio.Semaphore(PW_CONCURRENCY)
    sem_http = asyncio.Semaphore(HTTP_CONCURRENCY)

    tiers: dict = {1: [], 2: [], 3: []}
    for entry in saved:
        p = entry.get('priority', entry.get('venue_priority', 3)) or 3
        tiers[min(max(int(p), 1), 3)].append(entry)

    total          = len(saved)
    status_data    = load_status()
    completed      = 0
    total_events   = 0
    total_saved_db = 0

    q.put({
        'type': 'start',
        'total_sources': total,
        'p1': len(tiers[1]),
        'p2': len(tiers[2]),
        'p3': len(tiers[3]),
    })

    for tier_num in [1, 2, 3]:
        tier = tiers[tier_num]
        if not tier:
            continue

        q.put({'type': 'tier_start', 'tier': tier_num, 'count': len(tier)})

        for entry in tier:
            q.put({
                'type': 'source_start',
                'name': resolve_source_name(entry.get('url', ''), entry.get('name', '')),
                'url':  entry.get('url', ''),
                'tier': tier_num,
            })

        tasks   = [scrape_one(entry, sem_pw, sem_http) for entry in tier]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for entry, result in zip(tier, results):
            completed += 1

            if isinstance(result, BaseException):
                result = {
                    'url':          entry.get('url', ''),
                    'name':         resolve_source_name(entry.get('url', ''), entry.get('name', '')),
                    'status':       'error',
                    'error':        str(result),
                    'error_report': None,
                    'event_count':  0,
                    'events':       [],
                    'methods':      [],
                    'last_scraped': datetime.now().isoformat(),
                    'db_saved':     0,
                }

            url             = result['url']
            total_events   += result['event_count']
            total_saved_db += result['db_saved']

            status_data[url] = {
                'name':         result['name'],
                'last_scraped': result['last_scraped'],
                'status':       result['status'],
                'event_count':  result['event_count'],
                'methods':      result['methods'],
                'error':        result['error'],
                'error_report': result['error_report'],
                'norm_failed':  result.get('norm_failed', False),
                'events':       result.get('events', []),
            }
            save_status(status_data)

            q.put({
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

    # ── Normalization retry queue ─────────────────────────────────────────────
    # Re-attempt normalization for any sources that fell back to raw events
    norm_queue = [
        r for r in [
            status_data.get(e.get('url', {})) for e in saved
        ] if r and r.get('norm_failed')
    ]

    if norm_queue:
        import time
        print(f"[NormRetry] Retrying normalization for {len(norm_queue)} source(s) after 30s cooldown...")
        q.put({'type': 'norm_retry_start', 'count': len(norm_queue)})
        time.sleep(30)  # Let Gemini recover

        try:
            from scraperRoutes import normalize_batch, transform_event_for_backend
            import httpx as _httpx

            for entry in saved:
                url  = entry.get('url', '')
                sdata = status_data.get(url, {})
                if not sdata.get('norm_failed'):
                    continue
                name = sdata.get('name', url)
                prio = entry.get('priority', entry.get('venue_priority'))
                events = sdata.get('events', [])
                if not events:
                    continue

                print(f"[NormRetry] Retrying: {name}")
                normalized = normalize_batch(events, source_url=url, source_name=name)
                if normalized:
                    retry_saved = 0
                    for ev in normalized:
                        try:
                            xf = transform_event_for_backend(ev, source_priority=prio)
                            if not xf.get('source_url'): xf['source_url'] = url
                            if not xf.get('source_name'): xf['source_name'] = name
                            resp = _httpx.post(f"{BACKEND_URL}/api/events", json=xf, timeout=5)
                            if resp.status_code in [200, 201]:
                                retry_saved += 1
                                total_saved_db += 1
                        except Exception as e:
                            print(f"[NormRetry] {name}: {e}")
                    print(f"[NormRetry] {name}: {retry_saved}/{len(normalized)} saved")
                    q.put({'type': 'norm_retry_done', 'name': name, 'saved': retry_saved})
                else:
                    print(f"[NormRetry] {name}: still failing, skipping")
        except Exception as e:
            print(f"[NormRetry] Error: {e}")

    q.put({
        'type':            'complete',
        'total_events':    total_events,
        'total_saved':     total_saved_db,
        'sources_scraped': completed,
    })
    q.put(None)