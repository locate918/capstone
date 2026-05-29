"""
field_extractor.py — Pipeline Stage 4: deterministic field extraction (NO LLM).

Ports three jobs out of the Gemini prompt into testable Python so the LLM can be
removed from the ingest path entirely:

  - clean_description()  : strip HTML / entities / fluff, truncate at a word
                           boundary. Replaces the LLM "summarize description" job.
  - infer_flags()        : outdoor / family_friendly from venue + keyword rules
                           (ported from gemini.py normalize_events, lines 477-481).
  - categorize()         : map raw / empty categories onto the canonical 12-item
                           taxonomy via keyword rules (ported from lines 447-475).

CATEGORY ACCURACY: keyword classification is deliberately simpler than the LLM.
CATEGORY_KEYWORDS / TAG_MAP below are the tunable knobs — eyeball and adjust.
Output categories MUST stay within CANONICAL_CATEGORIES because the Rust
recommendation engine matches them against user_preferences.category.

No import side effects, no DB, no network.
"""

from __future__ import annotations

import html
import re
from typing import Dict, List, Optional, Tuple

# The only categories allowed downstream (must match onboarding / user_preferences).
CANONICAL_CATEGORIES = [
    "Music", "Comedy", "Arts & Theater", "Festival", "Film", "Food & Drink",
    "Nightlife", "Sports & Fitness", "Family", "Educational",
    "Nature & Outdoors", "Community",
]

# Keyword signals per canonical category. Matched as whole words (case-insensitive).
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    # Genre words + "in concert"/"tribute" added so listing blurbs that name a
    # genre ("country and rock", "indie pop") get caught instead of falling through.
    "Music": ["concert", "live music", "live band", "band", "dj", "dj set",
              "open mic", "acoustic", "singer", "songwriter", "gig", "tour",
              "album", "in concert", "tribute", "headliner", "headlining",
              "rock", "country", "jazz", "blues", "folk", "indie", "metal",
              "punk", "hip hop", "rap", "r&b", "soul", "funk", "reggae", "bluegrass"],
    "Comedy": ["comedy", "comedian", "stand-up", "standup", "improv", "open mic comedy"],
    # Dropped "play"/"musical"/"dance" — they mis-tagged concerts as theater.
    # Real theater is covered by the specific terms below (a stage musical still
    # hits "theater"/"broadway"/"performing arts").
    "Arts & Theater": ["theater", "theatre", "ballet", "opera", "symphony",
                       "orchestra", "exhibit", "exhibition", "gallery", "drag",
                       "circus", "art show", "performing arts", "theatrical",
                       "drama", "broadway", "choreography", "dance performance",
                       "stage production"],
    "Festival": ["festival", "fest", "celebration", "carnival"],
    "Film": ["film", "movie", "screening", "cinema", "documentary", "premiere"],
    "Food & Drink": ["food", "tasting", "cooking class", "brewery", "wine", "beer",
                     "cocktail", "brunch", "food truck", "farmers market", "dinner",
                     "culinary", "happy hour", "whiskey", "distillery"],
    # "party" -> "dance party" (bare "party" matched watch/release/birthday parties).
    "Nightlife": ["nightlife", "club night", "dj night", "21+", "late night",
                  "late-night", "dance party", "bar crawl", "trivia", "karaoke"],
    # "game" dropped (matched "video game", "board game"); specific sports added.
    "Sports & Fitness": ["run", "marathon", "5k", "10k", "cycling", "bike ride",
                         "yoga", "fitness", "tournament", "league", "workout",
                         "hockey", "football", "basketball", "baseball", "soccer",
                         "wrestling", "boxing", "mma", "fight night", "rodeo",
                         "roller derby", "esports"],
    "Family": ["kids", "children", "all ages", "all-ages", "family", "storytime",
               "family-friendly", "toddler"],
    "Educational": ["lecture", "workshop", "seminar", "class", "library", "book",
                    "author", "talk", "panel", "museum program", "reading"],
    "Nature & Outdoors": ["hike", "hiking", "nature walk", "trail", "garden",
                          "park", "outdoor", "open air", "wildlife"],
    # bare "drive" -> specific charity drives (matched "test drive", "scenic drive").
    "Community": ["nonprofit", "fundraiser", "volunteer", "neighborhood", "market",
                  "vendor", "tradeshow", "community", "fair", "food drive",
                  "toy drive", "blood drive"],
}

# Raw source tags (from extractors) -> canonical category.
TAG_MAP: Dict[str, str] = {
    "art": "Arts & Theater", "arts": "Arts & Theater", "theatre": "Arts & Theater",
    "theater": "Arts & Theater", "music": "Music", "concert": "Music",
    "comedy": "Comedy", "film": "Film", "movie": "Film", "museum": "Educational",
    "education": "Educational", "family": "Family", "kids": "Family",
    "food": "Food & Drink", "festival": "Festival", "sports": "Sports & Fitness",
    "fitness": "Sports & Fitness", "outdoors": "Nature & Outdoors",
    "nature": "Nature & Outdoors", "community": "Community", "nightlife": "Nightlife",
}

_OUTDOOR_SIGNALS = ["park", "garden", "green", "amphitheater", "amphitheatre", "zoo",
                    "lawn", "patio", "open air", "outdoor", "festival grounds", "riverfront"]
_FAMILY_POS = ["kids", "children", "all ages", "all-ages", "family", "storytime", "toddler"]
_FAMILY_NEG = ["18+", "21+", "burlesque", "adult", "nightclub"]


def clean_description(raw: Optional[str], max_chars: int = 500) -> Optional[str]:
    """Strip HTML/entities, collapse whitespace, truncate at a word boundary."""
    if not raw:
        return None
    text = re.sub(r"<[^>]+>", " ", str(raw))   # drop tags
    text = html.unescape(text)                  # &amp; -> &, etc.
    text = re.sub(r"\s+", " ", text).strip()    # collapse whitespace
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]    # don't split mid-word
    return cut.rstrip(",.;:") + "…"


def _word_present(needle: str, haystack: str) -> bool:
    """Whole-token match for single words; substring for multi-word phrases."""
    if " " in needle or "+" in needle or "-" in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


def categorize(
    title: str = "",
    description: str = "",
    source_categories: Optional[List[str]] = None,
) -> List[str]:
    """
    Map an event onto 1-3 canonical categories. Returns [] if nothing matches
    (an un-categorized event still shows in the feed, just not in preference-based
    recommendations). Title hits weigh more than description/tag hits.
    """
    title_l = (title or "").lower()
    body_l = (description or "").lower()
    scores: Dict[str, int] = {c: 0 for c in CANONICAL_CATEGORIES}

    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if _word_present(kw, title_l):
                scores[cat] += 2
            elif _word_present(kw, body_l):
                scores[cat] += 1

    for tag in source_categories or []:
        mapped = TAG_MAP.get((tag or "").strip().lower())
        if mapped:
            scores[mapped] += 2

    # Override rules (ported from prompt "ASSIGNMENT RULES"):
    # a comedian's show is Comedy, never Music / Arts & Theater.
    if scores["Comedy"] > 0:
        scores["Music"] = 0
        scores["Arts & Theater"] = 0

    ranked = [c for c in sorted(CANONICAL_CATEGORIES, key=lambda c: -scores[c])
              if scores[c] > 0]
    return ranked[:3]


def infer_flags(
    title: str = "",
    description: str = "",
    venue: str = "",
    venue_type: Optional[str] = None,
) -> Tuple[bool, bool]:
    """Return (outdoor, family_friendly) from venue + keyword rules."""
    blob = " ".join([title or "", description or "", venue or ""]).lower()
    vtype = (venue_type or "").lower()

    outdoor = vtype in ("outdoor", "park", "garden") or any(s in blob for s in _OUTDOOR_SIGNALS)

    family = any(s in blob for s in _FAMILY_POS) or any(
        v in (venue or "").lower() for v in ("library", "zoo", "park")
    )
    if any(s in blob for s in _FAMILY_NEG) and "all ages" not in blob and "all-ages" not in blob:
        family = False

    return outdoor, family