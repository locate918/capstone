-- Locate918 — Pipeline Redesign, Phase 1: Schema Migration
-- Version: 003
-- Author: Will
-- Date: 2026-05-28
--
-- PURPOSE
--   Introduce a stable INTEGER venue identity (venue_id) assigned at ingestion
--   time, so the database can resolve venues with a plain integer FK JOIN
--   instead of the current double LOWER(TRIM(COALESCE(...))) text JOIN through
--   venue_aliases.
--
-- SCOPE (intentionally ADDITIVE ONLY — nothing is dropped or rewritten here)
--   1. venues.venue_id            SERIAL UNIQUE  (UUID id stays the PK)
--   2. events.venue_id            INTEGER, nullable, FK -> venues(venue_id)
--   3. venue_alias_lookup         alias_text TEXT PK -> venue_id INTEGER FK
--   4. Seed venue_alias_lookup from the existing venue_aliases (149 rows)
--   5. Backfill events.venue_id   (by venue name, then by alias)
--   6. Index on events.venue_id   for the future FK JOIN
--
-- DELIBERATELY NOT DONE HERE (deferred to later phases per the redesign order):
--   - content_hash column/index is LEFT INTACT. Rust (events.rs, users.rs) and
--     the scraper (scraperRoutes.py, scraperUtils.py) still read/write it on all
--     1,713 rows. Dropping it now would 500 every events query + ingest. The
--     drop/rebase happens in Phase 9 after the code stops referencing it.
--   - The events.rs / users.rs JOINs are NOT switched to venue_id yet. This
--     migration only POPULATES venue_id; the text JOIN + DISTINCT ON stay until
--     the Rust update (Phase 5). venue_id is inert (read by nothing) until then.
--   - The legacy venue_aliases table is kept alive (used by the scraper's
--     _load_venue_aliases() and the live JOINs) until Phase 9 verification.
--
-- IDEMPOTENT: uses IF NOT EXISTS / ON CONFLICT DO NOTHING throughout, so a
-- re-run is a no-op. Runs in a single transaction.

BEGIN;

-- =============================================================================
-- 1. venues.venue_id — stable integer identifier (UUID id remains PK)
-- =============================================================================
-- SERIAL creates a sequence and backfills the existing 63 rows with 1..N.
-- New venues inserted via venues.rs (which does not list venue_id) get the
-- sequence default automatically — no backend change required for inserts.
ALTER TABLE venues
    ADD COLUMN IF NOT EXISTS venue_id SERIAL;

-- UNIQUE is required so events.venue_id can FK-reference it.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'venues_venue_id_key'
    ) THEN
        ALTER TABLE venues ADD CONSTRAINT venues_venue_id_key UNIQUE (venue_id);
    END IF;
END $$;

-- =============================================================================
-- 2. events.venue_id — nullable FK to the new integer key
-- =============================================================================
-- Nullable on purpose: ~272 future events have venue strings that match no
-- venue today and will backfill to NULL (they already get no venue enrichment
-- under the current text JOIN, so this is not a regression). ON DELETE SET NULL
-- so removing a venue never orphans/deletes its events.
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS venue_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'events_venue_id_fkey'
    ) THEN
        ALTER TABLE events
            ADD CONSTRAINT events_venue_id_fkey
            FOREIGN KEY (venue_id) REFERENCES venues(venue_id) ON DELETE SET NULL;
    END IF;
END $$;

-- =============================================================================
-- 3. venue_alias_lookup — alias_text -> venue_id (replaces text->text aliases)
-- =============================================================================
-- alias_text is stored normalized as LOWER(TRIM(...)) so resolution is a direct
-- key lookup (no per-query LOWER/TRIM). The legacy venue_aliases table is left
-- untouched and continues to back the live JOINs / scraper until Phase 9.
CREATE TABLE IF NOT EXISTS venue_alias_lookup (
    alias_text  TEXT PRIMARY KEY,
    venue_id    INTEGER NOT NULL REFERENCES venues(venue_id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_venue_alias_lookup_venue_id
    ON venue_alias_lookup(venue_id);

-- Match the rest of the schema: RLS on, no policy → service-role/backend access
-- only. The scraper reads with the service-role key, which bypasses RLS.
ALTER TABLE venue_alias_lookup ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 4. Seed venue_alias_lookup
-- =============================================================================
-- (a) Every venue name resolves to itself, so canonical names are matchable
--     through the same lookup path as aliases.
INSERT INTO venue_alias_lookup (alias_text, venue_id)
SELECT DISTINCT LOWER(TRIM(v.name)), v.venue_id
FROM venues v
WHERE v.name IS NOT NULL AND TRIM(v.name) <> ''
ON CONFLICT (alias_text) DO NOTHING;

-- (b) Existing aliases, resolving parent_venue -> venues.venue_id.
--     INNER JOIN drops the 1 orphan alias whose parent_venue matches no venue
--     (logged below). If two aliases normalize to the same text, the first wins.
INSERT INTO venue_alias_lookup (alias_text, venue_id)
SELECT DISTINCT LOWER(TRIM(va.alias)), v.venue_id
FROM venue_aliases va
JOIN venues v ON LOWER(TRIM(v.name)) = LOWER(TRIM(va.parent_venue))
WHERE va.alias IS NOT NULL AND TRIM(va.alias) <> ''
ON CONFLICT (alias_text) DO NOTHING;

-- (c) Curated short-form aliases identified during the Phase 1 dry-run —
--     abbreviations the heuristic resolver can't infer ("TPAC" -> Tulsa PAC,
--     "mercury" -> Mercury Lounge, ...). Keyed by venue NAME so the venue_id
--     stays correct regardless of SERIAL assignment order. These resolved ~256
--     previously-unmatched events.
INSERT INTO venue_alias_lookup (alias_text, venue_id)
SELECT a.alias, v.venue_id
FROM (VALUES
    ('tpac',             'Tulsa PAC'),
    ('bricktown comedy', 'Bricktown Comedy Club'),
    ('whittier',         'The Whittier Bar'),
    ('mercury',          'Mercury Lounge'),
    ('river spirit',     'River Spirit Casino'),
    ('church studio',    'The Church Studio'),
    ('maggies',          'Maggie''s'),
    ('ren fair',         'Oklahoma Renaissance Festival'),
    ('may fest',         'Tulsa Mayfest'),
    ('oktoberfest',      'Tulsa Oktoberfest'),
    ('badassrenee''s',   'BadAss Renee''s'),
    ('gypsy',            'Gypsy Coffee House')
) AS a(alias, vname)
JOIN venues v ON LOWER(TRIM(v.name)) = LOWER(TRIM(a.vname))
ON CONFLICT (alias_text) DO NOTHING;

-- =============================================================================
-- 5. Backfill events.venue_id
-- =============================================================================
-- Pass 1: direct venue-name match.
UPDATE events e
SET venue_id = v.venue_id
FROM venues v
WHERE e.venue_id IS NULL
  AND e.venue IS NOT NULL
  AND LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name));

-- Pass 2: alias match for whatever is still unresolved.
UPDATE events e
SET venue_id = vl.venue_id
FROM venue_alias_lookup vl
WHERE e.venue_id IS NULL
  AND e.venue IS NOT NULL
  AND LOWER(TRIM(e.venue)) = vl.alias_text;

-- =============================================================================
-- 6. Index for the future integer FK JOIN (Phase 5)
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_events_venue_id ON events(venue_id);

-- =============================================================================
-- Apply-time summary (visible in the migration output)
-- =============================================================================
DO $$
DECLARE
    orphan_aliases   INTEGER;
    lookup_rows      INTEGER;
    ev_total         INTEGER;
    ev_matched       INTEGER;
    ev_future_null   INTEGER;
BEGIN
    SELECT count(*) INTO orphan_aliases
    FROM venue_aliases va
    LEFT JOIN venues v ON LOWER(TRIM(v.name)) = LOWER(TRIM(va.parent_venue))
    WHERE v.id IS NULL;

    SELECT count(*) INTO lookup_rows FROM venue_alias_lookup;
    SELECT count(*) INTO ev_total    FROM events;
    SELECT count(*) INTO ev_matched  FROM events WHERE venue_id IS NOT NULL;
    SELECT count(*) INTO ev_future_null
    FROM events WHERE venue_id IS NULL AND start_time >= NOW();

    RAISE NOTICE '003 pipeline redesign applied:';
    RAISE NOTICE '  venue_alias_lookup rows seeded : %', lookup_rows;
    RAISE NOTICE '  orphan aliases skipped (no venue): %', orphan_aliases;
    RAISE NOTICE '  events with venue_id           : % / %', ev_matched, ev_total;
    RAISE NOTICE '  future events still unmatched  : %', ev_future_null;
END $$;

COMMIT;
