"""
date_parser.py — Pipeline Stage 3: deterministic date parsing.

Replaces the inline date-handling block in
``scraperRoutes.transform_event_for_backend`` with a single, testable function.

Design goals (per the pipeline redesign, §2 / §1C):
  - Deterministic: no LLM involvement.
  - Honest: when a date can't be parsed, return ``None`` instead of silently
    fabricating a ``NOW()+1 day`` placeholder (the old behaviour, which let
    undated garbage reach the database). The validation gate (stage 6) is
    responsible for rejecting events whose ``start_time`` is None.
  - Timezone-correct: naive datetimes are assumed to be Tulsa local time
    (America/Chicago, CDT/CST) and converted to UTC, matching the existing
    transform. Already-aware datetimes are converted to UTC.
  - Flags estimated times: ``time_estimated`` is True when the source string
    carried a date but no explicit clock time (so the start hour was guessed).

This module has NO import side effects and touches no database or network.
It is not wired into the pipeline until the stage-4 refactor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

import pytz
from dateutil import parser as _dateutil_parser

TULSA_TZ = pytz.timezone("America/Chicago")

# Two sentinel defaults that differ ONLY in time-of-day. We parse the same
# string against both; if the resulting clock time is identical to the default
# in both cases, dateutil found no time component in the input, so the time is
# estimated. If the two results differ, an explicit time was present.
_PROBE_A = datetime(1900, 1, 1, 0, 0, 0)
_PROBE_B = datetime(1900, 1, 1, 13, 47, 11)


def _has_explicit_time(date_str: str) -> bool:
    """True if ``date_str`` contains a parseable clock time (not just a date)."""
    try:
        a = _dateutil_parser.parse(date_str, fuzzy=True, default=_PROBE_A)
        b = _dateutil_parser.parse(date_str, fuzzy=True, default=_PROBE_B)
    except (ValueError, OverflowError, TypeError):
        return False
    a_t = (a.hour, a.minute, a.second)
    b_t = (b.hour, b.minute, b.second)
    # Exact midnight from BOTH probes means the string pins 00:00:00 (either a
    # date-only source whose extractor fabricated a "T00:00:00", or a literal
    # midnight). Treat it as estimated: events in this dataset don't start at
    # exactly midnight, and a literal midnight renders a day early once
    # converted to Tulsa local (UTC-5/-6). Stamping the default hour keeps the
    # calendar date correct. (No time token → b echoes _PROBE_B, not midnight,
    # so that case falls through to the comparison below and stays estimated.)
    if a_t == (0, 0, 0) and b_t == (0, 0, 0):
        return False
    # If no time token was present, each parse just echoes its default's time.
    return a_t != (_PROBE_A.hour, _PROBE_A.minute, _PROBE_A.second) \
        or b_t != (_PROBE_B.hour, _PROBE_B.minute, _PROBE_B.second)


def _to_utc(dt: datetime) -> datetime:
    """Convert a parsed datetime to UTC, assuming Tulsa local time if naive."""
    if dt.tzinfo is None:
        return TULSA_TZ.localize(dt).astimezone(pytz.utc)
    return dt.astimezone(pytz.utc)


def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a single date/time string to an aware UTC datetime, or None."""
    if not date_str or not str(date_str).strip():
        return None
    try:
        return _to_utc(_dateutil_parser.parse(str(date_str), fuzzy=True))
    except (ValueError, OverflowError, TypeError):
        return None


def parse_event_dates(
    start_raw: Optional[str],
    end_raw: Optional[str] = None,
    default_hour: int = 19,
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Resolve an event's start/end into ISO-8601 UTC strings.

    Returns ``(start_iso, end_iso, time_estimated)``:
      - ``start_iso`` is None when the start date is missing/unparseable. The
        caller (validation gate) must reject such events rather than store them.
      - ``end_iso`` is None when absent/unparseable (end time is optional).
      - ``time_estimated`` is True when a start date was found but no explicit
        clock time accompanied it.

    When the source carries a date but no clock time, dateutil defaults the
    missing time to midnight, which surfaces in the UI as a misleading
    "12:00 AM". Instead we stamp a sensible default hour (``default_hour``,
    Tulsa local — 7 PM, matching the previous LLM's generic fallback) so undated
    events sort and display reasonably. ``time_estimated`` stays True so the UI
    can still flag the time as a guess.
    """
    start_dt = parse_datetime(start_raw)
    if start_dt is None:
        return None, None, False

    time_estimated = not _has_explicit_time(str(start_raw))
    if time_estimated:
        # Re-stamp the (Tulsa-local) date at the default hour, then back to UTC.
        # Build from a naive local datetime so pytz handles DST correctly.
        local_date = start_dt.astimezone(TULSA_TZ).date()
        local_naive = datetime(
            local_date.year, local_date.month, local_date.day, default_hour, 0, 0
        )
        start_dt = TULSA_TZ.localize(local_naive).astimezone(pytz.utc)

    end_dt = parse_datetime(end_raw)
    end_iso = end_dt.isoformat() if end_dt else None

    return start_dt.isoformat(), end_iso, time_estimated
