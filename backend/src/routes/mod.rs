//! # Routes Module
//!
//! This module is the central routing hub for the Locate918 API.
//! It combines all route handlers from submodules and creates the
//! main application router.
//!
//! ## Current Endpoints
//!
//! ### Events (`/api/events`)
//! - `GET  /api/events`           - List all events
//! - `POST /api/events`           - Create a new event
//! - `GET  /api/events/:id`       - Get a single event by ID
//! - `GET  /api/events/search`    - Search events by query/category
//!
//! ### Users (`/api/users`)
//! - `POST /api/users`                    - Create a new user
//! - `GET  /api/users/:id`                - Get user by ID
//! - `GET  /api/users/:id/profile`        - Get full user profile (for LLM)
//! - `GET  /api/users/:id/preferences`    - Get user's category preferences
//! - `POST /api/users/:id/preferences`    - Add/update a preference
//! - `GET  /api/users/:id/interactions`   - Get user's event interactions
//! - `POST /api/users/:id/interactions`   - Record a new interaction
//!
//! ### Venues (`/api/venues`)
//! - `GET  /api/venues`           - List all venues
//! - `POST /api/venues`           - Create/register a venue
//! - `GET  /api/venues/:id`       - Get a single venue
//! - `GET  /api/venues/missing`   - Get venues missing website URLs
//! - `PATCH /api/venues/:id`      - Update venue (add website, etc.)
//!
//! ### Chat (`/api/chat`) - Coming Soon
//! - `POST /api/chat`             - Natural language event search (Ben's task)

// =============================================================================
// SUBMODULE DECLARATIONS
// =============================================================================
// Each submodule handles a specific resource/feature area.
// The actual route handlers are defined in these files.

pub mod events; // Event-related endpoints (CRUD + search)
mod chat;    // LLM-powered natural language chat (Ben - AI Engineer)
mod users;   // User management, preferences, and interactions
mod venues;  // Venue registry for source URL lookups

// =============================================================================
// IMPORTS
// =============================================================================

use axum::Router;   // Axum's router type for building route trees
use sqlx::PgPool;   // PostgreSQL connection pool type (passed as state)

// =============================================================================
// ROUTE FACTORY
// =============================================================================

/// Creates and returns the main API router with all endpoints.
///
/// # Type Parameter
/// - `Router<PgPool>`: A router that carries a PostgreSQL connection pool
///   as shared state. This allows all handlers to access the database.
///
/// # How Nesting Works
/// - `.nest("/events", events::routes())` takes all routes from `events::routes()`
///   and prefixes them with `/events`
/// - Combined with the `/api` prefix in main.rs, the full path becomes `/api/events`
///
/// # Example Request Flow
/// ```text
/// Client Request: GET /api/events/search?q=music
///                     ^^^^ ^^^^^^ ^^^^^^
///                      |     |      |
///                      |     |      +-- Handled by events::search_events()
///                      |     +--------- Nested under /events
///                      +--------------- Nested under /api (in main.rs)
/// ```
///
/// # Adding New Route Groups
/// To add a new feature area (e.g., venues):
/// 1. Create `routes/venues.rs` with a `pub fn routes() -> Router<PgPool>`
/// 2. Add `mod venues;` above
/// 3. Add `.nest("/venues", venues::routes())` below
pub fn create_routes() -> Router<PgPool> {
    Router::new()
        // ---------------------------------------------------------------------
        // Events Routes
        // ---------------------------------------------------------------------
        // All event-related endpoints: listing, creating, searching events.
        // Owner: Will (Coordinator/Backend Lead)
        .nest("/events", events::routes())

        // ---------------------------------------------------------------------
        // Users Routes
        // ---------------------------------------------------------------------
        // User management, preferences (likes/dislikes), and interaction tracking.
        // These power the personalization system for LLM recommendations.
        // Owner: Will (Coordinator/Backend Lead)
        .nest("/users", users::routes())

        // ---------------------------------------------------------------------
        // Venues Routes
        // ---------------------------------------------------------------------
        // Venue registry populated by scraper. Used to look up venue websites
        // so we can link to original sources instead of aggregators.
        // Owner: Will (Coordinator/Backend Lead)
        .nest("/venues", venues::routes())

    // ---------------------------------------------------------------------
    // Chat Routes (Coming Soon)
    // ---------------------------------------------------------------------
    // Natural language interface powered by Gemini/LLM.
    // Will interpret user queries like "What's happening downtown Friday?"
    // and return personalized event recommendations.
    // Owner: Ben (AI Engineer)
    //
    // Uncomment when Ben implements the chat functionality:
    // .nest("/chat", chat::routes())
}