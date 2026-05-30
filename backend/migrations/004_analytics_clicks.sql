-- 004_analytics_clicks.sql
-- Dedicated, append-only click analytics for venue traffic measurement.
--
-- This is intentionally SEPARATE from `user_interactions`: that table feeds the
-- ML preference model and only exists for authenticated users. This table
-- captures raw click traffic for ALL visitors (anonymous via a client-generated
-- `anon_id`) and is keyed on `venue_id` so per-venue traffic aggregates cleanly.
--
-- `provider` and `click_uid` are carried now so that re-applying for affiliate
-- programs later (Ticketmaster / StubHub) needs no schema or endpoint change:
--   - provider   = which destination a click went to (analytics dimension today)
--   - click_uid  = stable per-click id, the future affiliate sub-id for
--                  reconciling network-reported commissions back to a venue/event.

CREATE TABLE IF NOT EXISTS analytics_clicks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Who (best-effort). anon_id is always present; user_id only when logged in.
    anon_id         TEXT NOT NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,

    -- What was clicked.
    event_id        UUID    REFERENCES events(id)      ON DELETE SET NULL,
    venue_id        INTEGER REFERENCES venues(venue_id) ON DELETE SET NULL,

    -- outbound_ticket | outbound_venue | event_detail
    click_type      TEXT NOT NULL,
    -- ticketmaster | stubhub | eventbrite | venue_direct | aggregator | unknown
    provider        TEXT NOT NULL DEFAULT 'unknown',
    destination_url TEXT,

    -- Reconciliation key (future affiliate sub-id).
    click_uid       UUID NOT NULL,

    -- Lightweight context.
    referrer        TEXT,
    user_agent      TEXT
);

CREATE INDEX IF NOT EXISTS idx_analytics_clicks_venue_time
    ON analytics_clicks (venue_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_clicks_provider_time
    ON analytics_clicks (provider, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_clicks_click_uid
    ON analytics_clicks (click_uid);

-- RLS on for parity with the rest of the schema. No public policies are added:
-- only the backend writes/reads via its direct Postgres connection (which is not
-- subject to RLS), so the anon/authenticated PostgREST roles get no access.
ALTER TABLE analytics_clicks ENABLE ROW LEVEL SECURITY;