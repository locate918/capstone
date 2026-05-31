# Post-Capstone Changelog

Work completed after the capstone submission. Covers the move off LLM-based
event normalization and the bug fixes / feed-quality work that followed.

_Window: 2026-05-28 → 2026-05-31._

---

## 1. Move away from LLM normalization

The ingestion pipeline previously leaned on a Gemini "normalize" step to turn
raw scraped events into clean records (dates, venue matching, descriptions,
categories, validation). That step was fragile — a single LLM timeout dropped a
whole venue's batch — and non-deterministic. It has been replaced with a set of
deterministic Python stages.

### Phase 1–3 — new pipeline modules + schema (`d439e02`, 2026-05-28)

- **Migration 003** (applied to Supabase): integer `venue_id` on `venues` and
  `events`; new `venue_alias_lookup` table seeded from canonical names + aliases
  + 12 curated short-form aliases; event backfill (1679/1713 ≈ 98%); RLS on the
  new table.
- New deterministic modules (added but not yet wired in):
  - `venue_resolver.py` — stage 2: heuristic venue string → `venue_id`
  - `date_parser.py` — stage 3: deterministic dates + `time_estimated` flag
  - `field_extractor.py` — stage 4: description / flags / categories, no LLM
  - `event_validator.py` — stage 6: reason-coded validation gate
- LLM slimming: `gemini.normalize_events` no longer matches venues or fetches the
  venue-name cache; `schemas.NormalizedEvent` gains `venue_id`.

### Phase 4 — deterministic ingestion in the cron path (`d74daae`, 2026-05-28)

Rewired `_post_events_to_db` to the no-LLM pipeline:
`transform (field mapping only) → date_parser → field_extractor → venue_resolver
→ event_validator gate → POST`. Removed the Gemini `normalize_batch` call from
the cron.

Behavior changes:
- Events with unparseable/missing dates or placeholder titles are now **rejected
  with reason codes** instead of being posted with a fabricated `NOW + 1 day`
  date.
- `venue_id` is resolved client-side (heuristic); the backend resolves as a
  fallback.
- `content_hash` is recomputed from the final venue/time.
- No more retry-on-normalization-failure (a deterministic pipeline has no such
  failure mode).

### Flask scrape routes migrated (`f206b6f`, 2026-05-28)

`/to-database` and `/upload-all-to-database` no longer call Gemini
`normalize_batch`; both now run through the shared
`asyncScraper._post_events_to_db` pipeline — the same path the cron uses.
`/to-database` keeps its venue registration and Google Places enrichment.

Also removed dead code left behind by the rewrite (net **−538 lines**):
- `_dead_generate`, a ~310-line orphaned SSE generator wired to no route
- `normalize_batch` and the unused `LLM_SERVICE_URL` / headers imports
- the unreachable normalization-retry pass in `scrape_all_sequential`

---

## 2. Date & scraper bug fixes

### Date-only events stamped at 7 PM local, not midnight (`a595761`, 2026-05-28)

When a source gave a date with no clock time, `dateutil` defaulted to `00:00`,
which surfaced in the UI as a misleading "12:00 AM" (≈31% of upcoming events).
`parse_event_dates` now re-stamps time-estimated events at 19:00 Tulsa local
(matching the old LLM's fallback), built from a naive local datetime so DST is
handled correctly. The `time_estimated` flag stays `True`. Explicit times are
untouched.

### Day-early shift from fabricated midnight timestamps (`faa10bf`, 2026-05-29)

Date-only sources (Looney Bin, Route 66 Village, Church Studio, Living Arts,
Circle Cinema release-date fallback) emitted a spurious `T00:00:00`, which
`_has_explicit_time()` read as a real time and so skipped the 7 PM
normalization — rendering one calendar day early in Central.
- `date_parser`: treat an exact `00:00:00` from both probes as estimated, so any
  fabricated midnight gets the default-hour stamp.
- extractors: emit bare `%Y-%m-%d` when the source has no showtime (Living Arts
  keeps its explicit `23:59` end-of-day).

### Looney Bin — phantom next-year events (`09fcb36`, 2026-05-29)

The homepage lists month/day with no year; the year was inferred by bumping on
*any* month decrease. Recurring events listed slightly out of order (e.g.
Jun→May) were misread as a year rollover, stamping the rest of the list a year
ahead and accumulating phantom 2027/2028 copies.
- Bump the year only on a large backward jump (≥6 months, a real Dec→Jan wrap).
- Added a ~14-month horizon cap as defense-in-depth.

### Looney Bin — absolute source URLs (`a38eca4`, 2026-05-29)

The page serves relative hrefs (`/ShowDetails/...`). Storing them raw made
`source_url` non-canonical (broke as a ticket link) and broke the upsert key:
when a re-scrape changed URL form, the conflict target didn't match and
corrected events were inserted as duplicates. Hrefs are now resolved against the
base URL (`urljoin`) so `source_url` is absolute and stable across scrapes.

---

## 3. Feed curation — Circle Cinema (2026-05-31, `2e25b70` → `9c09f40`)

Circle Cinema runs multi-day feature films (several showtimes/day for ~a week)
that flooded the "This Week in Tulsa" feed alongside one-off special screenings.

The `/api/events` query now overrides the returned `venue_priority` to **3** for
any Circle Cinema (`venue_id 48`) title whose showings **span more than one
calendar day** (detected with `MIN(day) <> MAX(day)` per title). The frontend's
P1/P2-only "This Week" filter then excludes those feature films, while
single-day special screenings keep priority 2 and stay in the feed.

- Iteration 1 (`2e25b70`) only re-sorted features lower — still visible.
- Iteration 2 (`44d9fae`) overrode `venue_priority` itself so the feed filter
  excludes them.
- Iteration 3 (`9c09f40`) switched detection from "more than one showtime per
  day" to "spans more than one day," which correctly keeps single-day specials
  that happen to have a matinee + evening (e.g. Puddysticks, Okie Film Night).

Ordering/visibility only — every showtime row is still returned by the API and
remains available in the All Events / by-venue views.

---

## 4. Data quality — StubHub / River Spirit titles (2026-05-31, `20b653b`)

StubHub event pages render each card as one concatenated text blob
(`Jun4ThuAlabama8:00 PMTulsa, OK, US...See tickets`), and the generic extractor
was storing the whole blob as the title.

- **Scraper fix:** `clean_stubhub_title()` in `transform_event_for_backend()`
  recovers the real event name from between the date/day prefix and the showtime
  (the hour is constrained to 1–12 so a trailing number like "...Night 409" is
  not mistaken for the time), with the StubHub URL artist-slug as fallback. Runs
  before `content_hash` so dedup keys off the clean title.
- **Existing data:** the 15 live River Spirit events were corrected in place with
  `content_hash` recomputed to match the fixed scraper's output (so the next cron
  run does not re-insert blobs), and 7 duplicate rows were removed (6 StubHub
  blob/variant rows + 1 cross-source ticketsales duplicate).

**Known follow-up:** cross-source duplicates with differently-formatted titles
(e.g. "Vince Gill" vs "Vince Gill at The Cove at River Spirit Casino") are not
deduped because they hash differently — a real fix needs title normalization
that strips a trailing "at {venue}" before hashing.

---

## 5. Frontend & analytics (2026-05-30)

### Venue-traffic click tracking + cookie disclosure (`8e6da85`)

- Migrations `004_analytics_clicks.sql` and `005_events_ticket_provider.sql`.
- New `analytics.rs` route + `analytics.js` service tracking outbound
  venue/ticket clicks, surfaced on `EventCard` / `EventModal`.
- `CookieConsent` component for disclosure.

### Removed open-beta disclaimer modal (`1f547cc`)

Dropped the beta disclaimer modal from `App.js` (−94 lines) and the related
footer reference.
