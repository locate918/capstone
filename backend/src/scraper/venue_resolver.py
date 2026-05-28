"""
venue_resolver.py — Pipeline Stage 2: heuristic venue -> integer venue_id.

SKELETON. Not wired into the pipeline yet. Cannot produce useful output until
migration 003 is applied (creates venues.venue_id + venue_alias_lookup). Until
then resolve() degrades gracefully to None (treated as "unresolved").

Resolution cascade (deterministic — NO LLM):
  1. Job-carried ID  — a scrape job may pass venue_id directly (e.g. a future
     config that pins it); when present it wins outright.
  2. Exact lookup    — LOWER(TRIM(venue)) against venue_alias_lookup, whose keys
     003 seeds from both canonical names and aliases.
  3. Heuristic lookup — a small set of deterministic normalizations (drop "the",
     drop city/state suffix, "and"<->"&", strip punctuation) applied to BOTH the
     query and the lookup keys, so "The Vanguard Tulsa" matches "The Vanguard".
  4. Unresolved      — log to unresolved_venues.json for periodic triage; return
     None. The validation gate decides whether a NULL venue_id is fatal.

Resolution is by venue NAME, not a hand-assigned integer: saved_urls entries
already carry the canonical name, and 003 seeds every venues.name as a
self-alias, so a direct source resolves exactly without maintaining integer IDs
in config.

NORMALIZATION CONTRACT: exact keys are stored by 003 as ``LOWER(TRIM(text))``.
_exact() MUST mirror that. The heuristic index is built locally from the same
rows, so it needs no DB-side counterpart.

No import side effects. Reads Supabase via REST, mirroring
scraperUtils._load_venue_aliases (same SUPABASE_URL / SUPABASE_KEY env).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional

import httpx

# Exact index (LOWER(TRIM) keys) and heuristic index (aggressively normalized).
_exact_idx: Dict[str, int] = {}
_fuzzy_idx: Dict[str, int] = {}
_idx_time: float = 0.0
_IDX_TTL = 3600  # 1 hour

# Trailing location tokens to drop ("the vanguard tulsa" -> "the vanguard").
_SUFFIXES = ("tulsa", "ok", "oklahoma", "broken arrow", "jenks", "owasso")


def _data_dir() -> Path:
    root = os.getenv("LOCATE918_DATA_DIR")
    return Path(root) if root else Path(__file__).resolve().parent


_UNRESOLVED_FILE = _data_dir() / "unresolved_venues.json"


def _exact(venue: str) -> str:
    """LOWER(TRIM(...)) — must match the key normalization 003 seeds with."""
    return (venue or "").lower().strip()


def _aggressive(venue: str) -> str:
    """Lossy normalization for heuristic matching; applied to query AND keys."""
    s = (venue or "").lower().strip()
    s = re.sub(r"^the\s+", "", s)                 # drop leading "the"
    for suf in _SUFFIXES:                          # drop trailing place name
        s = re.sub(rf"\s+{re.escape(suf)}$", "", s)
    s = re.sub(r"\band\b", "&", s)                 # unify and / &
    s = re.sub(r"[^a-z0-9& ]", "", s)              # strip punctuation
    s = re.sub(r"\s+", " ", s).strip()             # collapse whitespace
    return s


def _load_indexes(force: bool = False) -> None:
    """Fetch venue_alias_lookup and (re)build exact + heuristic indexes, hourly."""
    global _exact_idx, _fuzzy_idx, _idx_time
    if _exact_idx and not force and (time.time() - _idx_time) < _IDX_TTL:
        return

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        return  # creds missing or table absent → degrade to no-op

    try:
        resp = httpx.get(
            f"{supabase_url}/rest/v1/venue_alias_lookup?select=alias_text,venue_id",
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        exact: Dict[str, int] = {}
        fuzzy: Dict[str, int] = {}
        for row in resp.json():
            text, vid = row.get("alias_text"), row.get("venue_id")
            if not text or vid is None:
                continue
            vid = int(vid)
            exact.setdefault(_exact(text), vid)
            fuzzy.setdefault(_aggressive(text), vid)  # first alias wins on collision
        _exact_idx, _fuzzy_idx, _idx_time = exact, fuzzy, time.time()
        print(f"[VenueResolver] Indexed {len(_exact_idx)} aliases "
              f"({len(_fuzzy_idx)} heuristic keys)")
    except Exception as e:
        # 003 not applied yet → table 404s here; expected pre-migration.
        print(f"[VenueResolver] Lookup unavailable: {e}")


def _log_unresolved(venue: str, source_name: str = "") -> None:
    """Append an unresolved venue string for later admin ID assignment."""
    try:
        existing = []
        if _UNRESOLVED_FILE.exists():
            existing = json.loads(_UNRESOLVED_FILE.read_text())
        key = _exact(venue)
        for row in existing:
            if row.get("normalized") == key:
                row["count"] = row.get("count", 1) + 1
                break
        else:
            existing.append(
                {"venue": venue, "normalized": key, "source_name": source_name, "count": 1}
            )
        _UNRESOLVED_FILE.write_text(json.dumps(existing, indent=2))
    except Exception as e:
        print(f"[VenueResolver] Could not log unresolved venue '{venue}': {e}")


def resolve(
    venue: Optional[str],
    job_venue_id: Optional[int] = None,
    source_name: str = "",
) -> Optional[int]:
    """
    Resolve an event to an integer venue_id, or None if unresolved (then logged).

    job_venue_id wins outright when provided. Otherwise we try an exact lookup,
    then a heuristic lookup, before giving up.
    """
    if job_venue_id is not None:
        return job_venue_id
    if not venue or not venue.strip():
        return None

    _load_indexes()

    hit = _exact_idx.get(_exact(venue))
    if hit is not None:
        return hit

    hit = _fuzzy_idx.get(_aggressive(venue))
    if hit is not None:
        return hit

    _log_unresolved(venue, source_name)
    return None