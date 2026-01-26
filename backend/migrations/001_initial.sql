-- Locate918 Database Schema
-- Version: 2.0 (AI Chat Interface Architecture)
--
-- This schema supports:
-- - Event storage with rich metadata for LLM tool queries
-- - User preferences (explicit) and interactions (implicit)
-- - Venue information for contextual queries

-- =============================================================================
-- EVENTS TABLE
-- =============================================================================
-- Core table storing all scraped events. Populated by Skylar's scrapers
-- via the /api/normalize endpoint.

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
    source_name TEXT,  -- "Eventbrite", "Visit Tulsa", "Cain's Ballroom"
    image_url TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate scrapes
    CONSTRAINT unique_source_url UNIQUE (source_url)
    );

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_location ON events(location);
CREATE INDEX IF NOT EXISTS idx_events_categories ON events USING GIN(categories);
CREATE INDEX IF NOT EXISTS idx_events_outdoor ON events(outdoor) WHERE outdoor = TRUE;
CREATE INDEX IF NOT EXISTS idx_events_family_friendly ON events(family_friendly) WHERE family_friendly = TRUE;
CREATE INDEX IF NOT EXISTS idx_events_source_name ON events(source_name);

-- =============================================================================
-- USERS TABLE
-- =============================================================================
-- User accounts with preference settings for personalization.

CREATE TABLE IF NOT EXISTS users (
                                     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,

    -- Preference settings (used by LLM for personalization)
    location_preference TEXT,      -- Preferred area
    radius_miles INTEGER,          -- How far willing to travel
    price_max DOUBLE PRECISION,    -- Budget limit (DOUBLE PRECISION for Rust f64)
    family_friendly_only BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- USER PREFERENCES TABLE
-- =============================================================================
-- Explicit category preferences (user told us directly).
-- Weight scale: -5 (hate) to +5 (love)

CREATE TABLE IF NOT EXISTS user_preferences (
                                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 0,  -- -5 to +5
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_user_category UNIQUE (user_id, category)
    );

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- =============================================================================
-- USER INTERACTIONS TABLE
-- =============================================================================
-- Implicit preferences (inferred from behavior).
-- Tracks clicks, saves, dismisses for ML recommendations.

CREATE TABLE IF NOT EXISTS user_interactions (
                                                 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL,  -- 'clicked', 'saved', 'dismissed', 'attended'

-- Denormalized for faster ML queries
    event_category TEXT,
    event_venue TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_event_id ON user_interactions(event_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_type ON user_interactions(interaction_type);

-- =============================================================================
-- VENUES TABLE (Optional - for venue-specific queries)
-- =============================================================================
-- Separate venue info for queries like "Is Cain's loud?" or "Does BOK have parking?"

CREATE TABLE IF NOT EXISTS venues (
                                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    address TEXT,
    city TEXT DEFAULT 'Tulsa',

    -- Venue attributes for LLM context
    capacity INTEGER,
    venue_type TEXT,  -- 'arena', 'club', 'theater', 'outdoor', 'restaurant'
    noise_level TEXT, -- 'quiet', 'moderate', 'loud'
    parking_info TEXT,
    accessibility_info TEXT,

    -- Links
    website TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );