-- 005_events_ticket_provider.sql
-- Classify each event's outbound ticket/source link into a provider bucket so we
-- can quantify monetizable inventory (how many Ticketmaster / StubHub / Eventbrite
-- links we actually carry) and slice traffic by destination.
--
-- Implemented as a STORED generated column over (canonical_url, source_url):
--   - auto-computed for every existing row when this runs (no separate backfill)
--   - auto-maintained on every future INSERT/UPDATE (no scraper/app changes)
--   - prefers canonical_url (direct venue/ticketing) and falls back to source_url
--
-- Buckets mirror the frontend classifyProvider() in services/analytics.js.

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS ticket_provider TEXT
    GENERATED ALWAYS AS (
        CASE
            WHEN COALESCE(canonical_url, source_url) ~* 'ticketmaster\.com|livenation\.com|ticketweb\.com'
                THEN 'ticketmaster'
            WHEN COALESCE(canonical_url, source_url) ~* 'stubhub\.com'
                THEN 'stubhub'
            WHEN COALESCE(canonical_url, source_url) ~* 'eventbrite\.(com|co\.uk)|evbuc\.com'
                THEN 'eventbrite'
            WHEN COALESCE(canonical_url, source_url) ~* 'visittulsa\.com|bit918\.com|do918\.com|allevents\.in|events\.com|eventful\.com|meetup\.com|facebook\.com'
                THEN 'aggregator'
            WHEN COALESCE(canonical_url, source_url) IS NOT NULL
             AND COALESCE(canonical_url, source_url) <> ''
                THEN 'venue_direct'
            ELSE NULL
        END
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_events_ticket_provider ON events (ticket_provider);
