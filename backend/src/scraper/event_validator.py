"""
event_validator.py — Pipeline Stage 6: the validation gate.

Nothing reaches ``POST /api/events`` unless it passes this gate. Every
rejection carries a specific reason code so the cron logs say *why* an event
was dropped instead of surfacing a generic Rust 500 (per redesign §1C).

Contract checked (against the transformed event dict, i.e. the CreateEvent
shape the Rust backend expects):
  - title present and not a placeholder
  - start_time present, parseable, and not in the past (beyond a grace window)
  - price range coherent and non-negative
  - source_url present (synthetic URLs are assigned upstream in
    ``_post_events_to_db`` before validation runs)
  - venue present and not obviously garbage

This module has NO import side effects and touches no database or network.
It is not wired into the pipeline until the stage-4 refactor.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dateutil import parser as _dateutil_parser

# Reason codes — stable strings for log aggregation / debugging.
MISSING_TITLE = "MISSING_TITLE"
PLACEHOLDER_TITLE = "PLACEHOLDER_TITLE"
MISSING_START_TIME = "MISSING_START_TIME"
UNPARSEABLE_START_TIME = "UNPARSEABLE_START_TIME"
PAST_EVENT = "PAST_EVENT"
INVALID_PRICE_RANGE = "INVALID_PRICE_RANGE"
NEGATIVE_PRICE = "NEGATIVE_PRICE"
MISSING_SOURCE_URL = "MISSING_SOURCE_URL"
MISSING_VENUE = "MISSING_VENUE"
GARBAGE_VENUE = "GARBAGE_VENUE"

_PLACEHOLDER_TITLES = {"untitled event", "untitled", "event", "tbd", "n/a"}

# Allow same-day / recently-started (multi-hour, ongoing) events through; only
# reject events whose start is more than this far in the past.
_PAST_GRACE = timedelta(days=1)


def _parse(dt_str: Any) -> Optional[datetime]:
    try:
        dt = _dateutil_parser.parse(str(dt_str), fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def validate_event(xf: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Validate a transformed event. Returns a result dict:
      {"valid": bool, "reasons": [code, ...], "title": str, "source_url": str}

    ``now`` is injectable for deterministic tests; defaults to current UTC time.
    """
    now = now or datetime.now(timezone.utc)
    reasons: List[str] = []

    # --- Title ---
    title = (xf.get("title") or "").strip()
    if not title:
        reasons.append(MISSING_TITLE)
    elif title.lower() in _PLACEHOLDER_TITLES:
        reasons.append(PLACEHOLDER_TITLE)

    # --- Start time ---
    start_raw = xf.get("start_time")
    if not start_raw:
        reasons.append(MISSING_START_TIME)
    else:
        start_dt = _parse(start_raw)
        if start_dt is None:
            reasons.append(UNPARSEABLE_START_TIME)
        elif start_dt < now - _PAST_GRACE:
            reasons.append(PAST_EVENT)

    # --- Price range ---
    pmin = xf.get("price_min")
    pmax = xf.get("price_max")
    if (pmin is not None and pmin < 0) or (pmax is not None and pmax < 0):
        reasons.append(NEGATIVE_PRICE)
    if pmin is not None and pmax is not None and pmin > pmax:
        reasons.append(INVALID_PRICE_RANGE)

    # --- Source URL ---
    if not (xf.get("source_url") or "").strip():
        reasons.append(MISSING_SOURCE_URL)

    # --- Venue ---
    venue = (xf.get("venue") or "").strip()
    if not venue:
        reasons.append(MISSING_VENUE)
    elif len(venue) < 2 or venue.replace(".", "").replace(",", "").replace("-", "").isdigit():
        reasons.append(GARBAGE_VENUE)

    return {
        "valid": not reasons,
        "reasons": reasons,
        "title": title or "<no title>",
        "source_url": xf.get("source_url") or "<no url>",
    }