-- Locate918 Database Schema
-- Version: 4.0
--
-- Changelog from v3.0:
--   - Added user_saved_events table for bookmarking events
--   - Updated user_interactions table to support event_categories as array

-- =============================================================================
-- EVENTS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic info
    title TEXT NOT NULL,
    description TEXT,

    -- Location
    venue TEXT,
    venue_address TEXT,
    location TEXT,  -- General area: "Downtown Tulsa", "Broken Arrow"

    -- Timing
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    time_estimated BOOLEAN DEFAULT FALSE,  -- TRUE if start_time was guessed, not explicit

    -- Categorization (array for multiple categories)
    categories TEXT[],  -- e.g., ['concerts', 'rock', 'live music']

    -- Filtering attributes
    outdoor BOOLEAN DEFAULT FALSE,
    family_friendly BOOLEAN DEFAULT FALSE,

    -- Pricing (DOUBLE PRECISION for Rust f64 compatibility)
    price_min DOUBLE PRECISION,
    price_max DOUBLE PRECISION,

    -- Source tracking
    source_url TEXT NOT NULL,
    source_name TEXT,       -- "Eventbrite", "Visit Tulsa", "Cain's Ballroom"
    image_url TEXT,

    -- Cross-source deduplication
    -- content_hash is an MD5 of normalize(title) + date/hour + normalize(venue).
    -- Two events from different sources that represent the same real-world event
    -- will share a hash and be merged by the UPSERT rather than stored twice.
    content_hash TEXT,

    -- Source trust tier:
    --   1 = direct venue website  (highest trust)
    --   2 = ticketing platform    (e.g. Eventbrite, Ticketmaster)
    --   3 = aggregator            (e.g. Visit Tulsa, BIT, do918) — lowest trust
    source_priority INT DEFAULT 3,

    -- Best known URL for this event from the highest-trust source scraped so far.
    -- Only set/upgraded when source_priority <= 2. Never overwritten by an aggregator.
    -- Used by the frontend instead of source_url so RSVP links always point to the
    -- venue or ticketing page, never back to Visit Tulsa / BIT / Eventbrite.
    canonical_url TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate scrapes of the same URL
    CONSTRAINT unique_source_url UNIQUE (source_url)
);

-- Standard query indexes
CREATE INDEX IF NOT EXISTS idx_events_start_time        ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_location          ON events(location);
CREATE INDEX IF NOT EXISTS idx_events_categories        ON events USING GIN(categories);
CREATE INDEX IF NOT EXISTS idx_events_outdoor           ON events(outdoor) WHERE outdoor = TRUE;
CREATE INDEX IF NOT EXISTS idx_events_family_friendly   ON events(family_friendly) WHERE family_friendly = TRUE;
CREATE INDEX IF NOT EXISTS idx_events_source_name       ON events(source_name);

-- Cross-source dedup index — partial so existing NULL rows are unaffected
CREATE UNIQUE INDEX IF NOT EXISTS events_content_hash_key
    ON events (content_hash)
    WHERE content_hash IS NOT NULL;

-- =============================================================================
-- USERS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,

    -- Preference settings (used by LLM for personalization)
    location_preference TEXT,
    radius_miles INTEGER,
    price_max DOUBLE PRECISION,
    family_friendly_only BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at on every write
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- USER PREFERENCES TABLE
-- =============================================================================
-- Explicit category preferences set by the user.
-- Weight scale: -5 (hate) to +5 (love)

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_user_category UNIQUE (user_id, category)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- =============================================================================
-- USER INTERACTIONS TABLE
-- =============================================================================
-- Implicit preferences inferred from behaviour (clicks, saves, dismisses).

CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL,  -- 'clicked', 'saved', 'dismissed', 'attended'

    -- Denormalized for faster ML queries
    event_categories TEXT[],
    event_venue TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id  ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_event_id ON user_interactions(event_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_type     ON user_interactions(interaction_type);

-- =============================================================================
-- USER SAVED EVENTS TABLE
-- =============================================================================
-- Tracks which events users have bookmarked for later review.

CREATE TABLE IF NOT EXISTS user_saved_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Each user can only save each event once
    CONSTRAINT unique_user_event_save UNIQUE (user_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_user_saved_events_user_id  ON user_saved_events(user_id);
CREATE INDEX IF NOT EXISTS idx_user_saved_events_event_id ON user_saved_events(event_id);

-- =============================================================================
-- VENUES TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS venues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    address TEXT,
    city TEXT DEFAULT 'Tulsa',

    -- Geocoordinates (populated via Nominatim / Google Places)
    latitude  DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    -- Venue attributes for LLM context
    capacity INTEGER,
    venue_type TEXT,    -- 'arena', 'club', 'theater', 'outdoor', 'restaurant'
    noise_level TEXT,   -- 'quiet', 'moderate', 'loud'
    parking_info TEXT,
    accessibility_info TEXT,

    -- Links
    website TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);