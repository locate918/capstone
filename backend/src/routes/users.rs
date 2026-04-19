//! # Users Routes
//!
//! Handles all user-related API endpoints including
//! user accounts, preferences, and interaction tracking.
//!
//! ## Authentication
//! All endpoints require a valid Supabase JWT in the `Authorization` header.
//! User creation is handled automatically by the database trigger when
//! someone signs up via Supabase Auth — no `POST /api/users` endpoint needed.
//!
//! ## Endpoints
//! - `GET  /api/users/me`                         - Get current user (from JWT)
//! - `GET  /api/users/me/profile`                 - Get full profile (for LLM)
//! - `GET  /api/users/me/preferences`             - Get category preferences
//! - `POST /api/users/me/preferences`             - Add/update a preference
//! - `PUT  /api/users/me/preferences`             - Update user settings
//! - `GET  /api/users/me/interactions`            - Get interaction history
//! - `POST /api/users/me/interactions`            - Record an interaction
//! - `GET  /api/users/me/saved-events`            - Get saved events
//! - `POST /api/users/me/saved-events/:eventId`   - Save an event
//! - `DELETE /api/users/me/saved-events/:eventId` - Unsave an event
//! - `GET  /api/users/me/recommendations`        - Get personalized recommendations
//!
//! ## Owner
//! Will (Coordinator/Backend Lead)

// =============================================================================
// IMPORTS
// =============================================================================

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use sqlx::PgPool;
use uuid::Uuid;

use crate::auth::AuthUser;
use crate::models::{
    CreateUserInteraction, CreateUserPreference, UpdateUserPreferences, User, UserInteraction,
    UserInteractionWithEvent, UserPreference, UserProfile, UserSavedEvent,
};

// Reuse Event struct from events module
use crate::routes::events::Event;

// =============================================================================
// ROUTE DEFINITIONS
// =============================================================================

/// Creates the router for all user endpoints.
///
/// All routes use the `AuthUser` extractor which validates the Supabase JWT
/// and extracts the user's UUID. No path parameter needed — identity comes
/// from the token.
pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/me", get(get_current_user))
        .route("/me/profile", get(get_my_profile))
        .route(
            "/me/preferences",
            get(get_my_preferences)
                .post(add_my_preference)
                .put(update_my_preferences),
        )
        .route(
            "/me/interactions",
            get(get_my_interactions).post(add_my_interaction),
        )
        .route("/me/saved-events", get(get_saved_events))
        .route(
            "/me/saved-events/:eventId",
            post(save_event).delete(unsave_event),
        )
        .route("/me/recommendations", get(get_my_recommendations))
}

// =============================================================================
// QUERY PARAMETERS FOR RECOMMENDATIONS
// =============================================================================

#[derive(Debug, Deserialize)]
pub struct RecommendationsQuery {
    /// Maximum number of results (default: 100, max: 2000)
    pub limit: Option<i32>,
}

// =============================================================================
// HANDLER: GET SAVED EVENTS
// =============================================================================

/// Returns all saved events for the authenticated user.
///
/// # Endpoint
/// `GET /api/users/me/saved-events`
///
/// Returns events sorted by save date (newest first).
async fn get_saved_events(
    auth: AuthUser,
    State(pool): State<PgPool>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let user_id = auth.user_id;

    println!("[DEBUG] Fetching saved events for user: {}", user_id);

    let events = sqlx::query_as::<_, Event>(
        r#"
        SELECT
            e.id, e.title, e.description, e.venue, e.venue_address, e.location,
            e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
            e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
            e.time_estimated, e.content_hash, e.source_priority, e.canonical_url,
            e.created_at, e.updated_at,
            v.website      AS venue_website,
            v.latitude     AS venue_latitude,
            v.longitude    AS venue_longitude,
            v.venue_priority AS venue_priority
        FROM user_saved_events se
        JOIN events e ON se.event_id = e.id
        LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
        WHERE se.user_id = $1
        ORDER BY se.created_at DESC
        "#,
    )
    .bind(user_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error fetching saved events: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    println!(
        "[DEBUG] Found {} saved events for user {}",
        events.len(),
        user_id
    );

    Ok(Json(events))
}

// =============================================================================
// HANDLER: SAVE EVENT
// =============================================================================

/// Saves an event to the user's bookmarks.
///
/// # Endpoint
/// `POST /api/users/me/saved-events/:eventId`
///
/// # Behavior
/// - Creates a user_saved_events record if the event isn't already saved
/// - Returns 201 Created if the save is new
/// - Returns 200 OK if the event was already saved (idempotent)
/// - Records a "saved" interaction for preference weight updates
async fn save_event(
    auth: AuthUser,
    State(pool): State<PgPool>,
    Path(event_id): Path<Uuid>,
) -> Result<(StatusCode, Json<UserSavedEvent>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Verify the event exists
    let event_exists =
        sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM events WHERE id = $1)")
            .bind(&event_id)
            .fetch_one(&pool)
            .await
            .map_err(|e| {
                eprintln!("Database error: {}", e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

    if !event_exists {
        return Err(StatusCode::NOT_FOUND);
    }

    // Verify the user exists
    let user_exists =
        sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)")
            .bind(auth.user_id)
            .fetch_one(&pool)
            .await
            .map_err(|e| {
                eprintln!("Database error: {}", e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

    if !user_exists {
        return Err(StatusCode::FORBIDDEN);
    }

    // Attempt to insert, using UPSERT to ensure idempotency
    let result = sqlx::query_as::<_, UserSavedEvent>(
        r#"
        INSERT INTO user_saved_events (id, user_id, event_id, created_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, event_id)
        DO UPDATE SET id = EXCLUDED.id
        RETURNING id, user_id, event_id, created_at
        "#,
    )
    .bind(&id)
    .bind(auth.user_id)
    .bind(&event_id)
    .bind(&now)
    .fetch_one(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Record the "saved" interaction for weight updates
    // Fetch event details for denormalization
    let (event_categories, event_venue) =
        sqlx::query_as::<_, (Option<Vec<String>>, Option<String>)>(
            "SELECT categories, venue FROM events WHERE id = $1",
        )
        .bind(&event_id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .unwrap_or((None, None));

    let interaction_id = Uuid::new_v4();
    sqlx::query(
        r#"
        INSERT INTO user_interactions (id, user_id, event_id, interaction_type, event_categories, event_venue, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        "#,
    )
        .bind(&interaction_id)
        .bind(auth.user_id)
        .bind(&event_id)
        .bind("saved")
        .bind(&event_categories)
        .bind(&event_venue)
        .bind(&now)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    println!(
        "[DEBUG] Event saved: User {} saved Event {}",
        auth.user_id, event_id
    );

    Ok((StatusCode::CREATED, Json(result)))
}

// =============================================================================
// HANDLER: UNSAVE EVENT
// =============================================================================

/// Removes an event from the user's saved bookmarks.
///
/// # Endpoint
/// `DELETE /api/users/me/saved-events/:eventId`
///
/// # Behavior
/// - Deletes the user_saved_events record
/// - Returns 204 No Content on success
/// - Returns 404 if the saved event doesn't exist
/// - Records an "unsaved" interaction for preference tracking
async fn unsave_event(
    auth: AuthUser,
    State(pool): State<PgPool>,
    Path(event_id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    let user_id = auth.user_id;

    // Verify the saved event exists before attempting deletion
    let saved_event_exists = sqlx::query_scalar::<_, bool>(
        "SELECT EXISTS(SELECT 1 FROM user_saved_events WHERE user_id = $1 AND event_id = $2)",
    )
    .bind(user_id)
    .bind(&event_id)
    .fetch_one(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    if !saved_event_exists {
        return Err(StatusCode::NOT_FOUND);
    }

    // Delete the saved event
    sqlx::query("DELETE FROM user_saved_events WHERE user_id = $1 AND event_id = $2")
        .bind(user_id)
        .bind(&event_id)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Record the "unsaved" interaction for tracking
    let interaction_id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Fetch event details for denormalization
    let (event_categories, event_venue) =
        sqlx::query_as::<_, (Option<Vec<String>>, Option<String>)>(
            "SELECT categories, venue FROM events WHERE id = $1",
        )
        .bind(&event_id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .unwrap_or((None, None));

    sqlx::query(
        r#"
        INSERT INTO user_interactions (id, user_id, event_id, interaction_type, event_categories, event_venue, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        "#,
    )
        .bind(&interaction_id)
        .bind(user_id)
        .bind(&event_id)
        .bind("unsaved")
        .bind(&event_categories)
        .bind(&event_venue)
        .bind(&now)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    println!(
        "[DEBUG] Event unsaved: User {} unsaved Event {}",
        user_id, event_id
    );

    Ok(StatusCode::NO_CONTENT)
}

// =============================================================================
// HANDLER: GET RECOMMENDATIONS
// =============================================================================

/// Returns personalized event recommendations based on user category preferences.
///
/// # Endpoint
/// `GET /api/users/me/recommendations?limit=15`
///
/// # Algorithm
/// 1. Fetch user's category preferences with weights (from onboarding)
/// 2. Score all upcoming events within next 2 months based on category matches
/// 3. Return top N events sorted by score, then by date (earliest first)
///
/// # Scoring
/// - Base score: 0
/// - For each event category that matches a user preference: +weight
/// - Minimum threshold: 4.0 (ensures high-quality matches)
/// - If user has no preferences: return nothing (user hasn't completed onboarding)
/// - Time window: NOW() to NOW() + 60 days (2 months)
async fn get_my_recommendations(
    auth: AuthUser,
    State(pool): State<PgPool>,
    Query(params): Query<RecommendationsQuery>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let limit = params.limit.unwrap_or(15).min(100);
    let user_id = auth.user_id;

    println!(
        "[DEBUG] Recommendations request: User {} limit={}",
        user_id, limit
    );

    // Step 1: Fetch user's category preferences
    let preferences = sqlx::query_as::<_, (String, f64)>(
        "SELECT category, weight FROM user_preferences WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error fetching preferences: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Debug: Log fetched preferences
    println!("[DEBUG] Total preferences found: {}", preferences.len());
    for (cat, weight) in &preferences {
        println!("[DEBUG] Preference: category='{}', weight={}", cat, weight);
    }

    if preferences.is_empty() {
        println!(
            "[DEBUG] User {} has no preferences, returning empty recommendations",
            user_id
        );
        return Ok(Json(vec![]));
    }

    println!(
        "[DEBUG] User {} has {} category preferences",
        user_id,
        preferences.len()
    );

    // Step 2: First, let's see what events exist and their categories
    let sample_events = sqlx::query_as::<_, (String, Option<Vec<String>>)>(
        "SELECT title, categories FROM events WHERE start_time >= NOW() AND start_time < NOW() + INTERVAL '60 days' LIMIT 5"
    )
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error fetching sample events: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    println!("[DEBUG] Sample events (first 5, within 2 months):");
    for (title, cats) in &sample_events {
        println!("[DEBUG]   - '{}': categories={:?}", title, cats);
    }

    // Step 3: Build scoring query - limit to 2 months ahead, sort by score then date
    let events = sqlx::query_as::<_, Event>(
        r#"
        WITH scored_events AS (
            SELECT
                e.id, e.title, e.description, e.venue, e.venue_address, e.location,
                e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
                e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
                e.time_estimated, e.content_hash, e.source_priority, e.canonical_url,
                e.created_at, e.updated_at,
                v.website      AS venue_website,
                v.latitude     AS venue_latitude,
                v.longitude    AS venue_longitude,
                v.venue_priority AS venue_priority,
                -- Only sum weights for preferences where categories match
                COALESCE(SUM(up.weight), 0) AS total_score
            FROM events e
            LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
            -- IMPORTANT: Only join preferences that have matching categories
            LEFT JOIN user_preferences up ON up.user_id = $1
                AND e.categories IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM unnest(e.categories) AS event_cat
                    WHERE LOWER(event_cat) = LOWER(up.category)
                )
            WHERE e.start_time >= NOW()
              AND e.start_time < NOW() + INTERVAL '60 days'
            GROUP BY e.id, e.title, e.description, e.venue, e.venue_address, e.location,
                     e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
                     e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
                     e.time_estimated, e.content_hash, e.source_priority, e.canonical_url,
                     e.created_at, e.updated_at,
                     v.website, v.latitude, v.longitude, v.venue_priority
        )
        SELECT *
        FROM scored_events
        WHERE total_score >= 5.0
        ORDER BY total_score DESC, start_time ASC
        LIMIT $2
        "#,
    )
    .bind(user_id)
    .bind(limit)
    .fetch_all(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error fetching recommendations: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    println!(
        "[DEBUG] Returning {} recommendations for user {} (within 2 months)",
        events.len(),
        user_id
    );

    for (i, event) in events.iter().take(5).enumerate() {
        println!(
            "[DEBUG] Recommendation {}: title='{}', date='{}', categories={:?}",
            i + 1,
            event.title,
            event.start_time,
            event.categories
        );
    }

    Ok(Json(events))
}

// =============================================================================
// HANDLER: GET CURRENT USER
// =============================================================================

/// Returns the authenticated user's account info.
///
/// # Endpoint
/// `GET /api/users/me`
///
/// # Auth
/// Requires valid Supabase JWT. User ID comes from the `sub` claim.
async fn get_current_user(
    auth: AuthUser,
    State(pool): State<PgPool>,
) -> Result<Json<User>, StatusCode> {
    let user = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, location_preference, radius_miles,
               price_max, family_friendly_only, use_smart_search, 
               has_completed_onboarding, created_at, updated_at
        FROM users
        WHERE id = $1
        "#,
    )
    .bind(auth.user_id)
    .fetch_optional(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    match user {
        Some(u) => Ok(Json(u)),
        None => {
            // User exists in auth.users but not in public.users yet.
            // This can happen if the auth trigger hasn't fired or failed.
            // Return 404 — the frontend can prompt the user to try again.
            eprintln!(
                "Auth user {} has no public.users row — trigger may have failed",
                auth.user_id
            );
            Err(StatusCode::NOT_FOUND)
        }
    }
}

// =============================================================================
// HANDLER: GET USER PROFILE (for LLM)
// =============================================================================

/// Returns complete user profile for LLM personalization.
///
/// # Endpoint
/// `GET /api/users/me/profile`
///
/// Includes: basic user info, category preferences, recent 20 interactions
async fn get_my_profile(
    auth: AuthUser,
    State(pool): State<PgPool>,
) -> Result<Json<UserProfile>, StatusCode> {
    let user_id = auth.user_id;

    // Fetch user
    let user = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, location_preference, radius_miles,
               price_max, family_friendly_only, use_smart_search, 
               has_completed_onboarding, created_at, updated_at
        FROM users
        WHERE id = $1
        "#,
    )
    .bind(user_id)
    .fetch_optional(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .ok_or(StatusCode::NOT_FOUND)?;

    // Fetch preferences
    let preferences = sqlx::query_as::<_, UserPreference>(
        r#"
        SELECT id, user_id, category, 
               ROUND((weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400.0))::numeric, 2)::float8 AS weight, 
               created_at, updated_at 
        FROM user_preferences WHERE user_id = $1
        "#,
    )
        .bind(user_id)
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Fetch recent interactions with event details
    let recent_interactions = sqlx::query_as::<_, UserInteractionWithEvent>(
        r#"
        SELECT ui.interaction_type, e.title as event_title,
               e.categories as event_categories,
               ui.created_at
        FROM user_interactions ui
        JOIN events e ON ui.event_id = e.id
        WHERE ui.user_id = $1
        ORDER BY ui.created_at DESC
        LIMIT 20
        "#,
    )
    .bind(user_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(UserProfile {
        user,
        preferences,
        recent_interactions,
    }))
}

// =============================================================================
// HANDLER: GET PREFERENCES
// =============================================================================

/// Returns all category preferences for the authenticated user.
///
/// # Endpoint
/// `GET /api/users/me/preferences`
async fn get_my_preferences(
    auth: AuthUser,
    State(pool): State<PgPool>,
) -> Result<Json<Vec<UserPreference>>, StatusCode> {
    let preferences = sqlx::query_as::<_, UserPreference>(
        r#"
        SELECT id, user_id, category, 
               ROUND((weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400.0))::numeric, 2)::float8 AS weight, 
               created_at, updated_at 
        FROM user_preferences WHERE user_id = $1 ORDER BY weight DESC
        "#,
    )
        .bind(auth.user_id)
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(preferences))
}

// =============================================================================
// HANDLER: ADD/UPDATE PREFERENCE
// =============================================================================

/// Adds or updates a category preference.
///
/// # Endpoint
/// `POST /api/users/me/preferences`
///
/// Uses UPSERT — creates if new, updates weight if category already exists.
async fn add_my_preference(
    auth: AuthUser,
    State(pool): State<PgPool>,
    Json(payload): Json<CreateUserPreference>,
) -> Result<(StatusCode, Json<UserPreference>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Ensure the user exists in public.users to avoid foreign key constraint error
    let user_exists =
        sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)")
            .bind(auth.user_id)
            .fetch_one(&pool)
            .await
            .map_err(|e| {
                eprintln!("Database error: {}", e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

    if !user_exists {
        eprintln!(
            "[ERROR] Preference update failed: User {} does not exist in public.users. Profile trigger may have failed.",
            auth.user_id
        );
        return Err(StatusCode::FORBIDDEN);
    }

    let result = sqlx::query_as::<_, UserPreference>(
        r#"
        INSERT INTO user_preferences (id, user_id, category, weight, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $5)
        ON CONFLICT (user_id, category)
        DO UPDATE SET 
            weight = ROUND(((user_preferences.weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - user_preferences.updated_at)) / 86400.0)) + EXCLUDED.weight)::numeric, 2)::float8,
            updated_at = EXCLUDED.updated_at
        RETURNING id, user_id, category, weight, created_at, updated_at
        "#,
    )
        .bind(&id)
        .bind(auth.user_id)
        .bind(&payload.category)
        .bind(&payload.weight)
        .bind(&now)
        .fetch_one(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // DEBUG: User preferences updated (category-specific)
    println!(
        "[DEBUG] User preference updated: User {} set category '{}' to weight {}",
        auth.user_id, result.category, result.weight
    );

    Ok((StatusCode::CREATED, Json(result)))
}

// =============================================================================
// HANDLER: UPDATE USER PREFERENCES (settings)
// =============================================================================

/// Updates the authenticated user's preference settings.
///
/// # Endpoint
/// `PUT /api/users/me/preferences`
///
/// Updates location, radius, price, and family-friendly settings.
async fn update_my_preferences(
    auth: AuthUser,
    State(pool): State<PgPool>,
    Json(payload): Json<UpdateUserPreferences>,
) -> Result<Json<User>, StatusCode> {
    // DEBUG: Log the incoming payload
    println!(
        "[DEBUG] update_my_preferences payload received: use_smart_search={:?}, has_completed_onboarding={:?}",
        payload.use_smart_search,
        payload.has_completed_onboarding
    );

    // Use parameterized queries to prevent SQL injection
    let user = sqlx::query_as::<_, User>(
        r#"
        UPDATE users
        SET location_preference = COALESCE($2, location_preference),
            radius_miles = COALESCE($3, radius_miles),
            price_max = COALESCE($4, price_max),
            family_friendly_only = COALESCE($5, family_friendly_only),
            use_smart_search = CASE 
                WHEN $6::boolean IS NOT NULL THEN $6::boolean
                ELSE use_smart_search
            END,
            has_completed_onboarding = CASE 
                WHEN $7::boolean IS NOT NULL THEN $7::boolean
                ELSE has_completed_onboarding
            END,
            updated_at = NOW()
        WHERE id = $1
        RETURNING id, email, name, location_preference, radius_miles,
                  price_max, family_friendly_only, use_smart_search, 
                  has_completed_onboarding, created_at, updated_at
        "#,
    )
    .bind(auth.user_id)
    .bind(&payload.location_preference)
    .bind(&payload.radius_miles)
    .bind(&payload.price_max)
    .bind(&payload.family_friendly_only)
    .bind(&payload.use_smart_search)
    .bind(&payload.has_completed_onboarding)
    .fetch_optional(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .ok_or(StatusCode::NOT_FOUND)?;

    // DEBUG: User preferences updated (settings) with onboarding status
    println!(
        "[DEBUG] User preferences updated: User {} has_completed_onboarding={} (from payload: {:?})",
        auth.user_id, user.has_completed_onboarding, payload.has_completed_onboarding
    );

    Ok(Json(user))
}

// =============================================================================
// HANDLER: GET INTERACTIONS
// =============================================================================

/// Returns interaction history for the authenticated user.
///
/// # Endpoint
/// `GET /api/users/me/interactions`
async fn get_my_interactions(
    auth: AuthUser,
    State(pool): State<PgPool>,
) -> Result<Json<Vec<UserInteraction>>, StatusCode> {
    let interactions = sqlx::query_as::<_, UserInteraction>(
        r#"
        SELECT id, user_id, event_id, interaction_type, event_categories, event_venue, created_at
        FROM user_interactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 100
        "#,
    )
    .bind(auth.user_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(interactions))
}

// =============================================================================
// HANDLER: ADD INTERACTION
// =============================================================================

/// Records a new user interaction with an event.
///
/// # Endpoint
/// `POST /api/users/me/interactions`
///
/// Automatically captures event category and venue for ML.
async fn add_my_interaction(
    auth: AuthUser,
    State(pool): State<PgPool>,
    Json(payload): Json<CreateUserInteraction>,
) -> Result<(StatusCode, Json<UserInteraction>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Fetch event details for denormalization
    let event = sqlx::query_as::<_, (Option<Vec<String>>, Option<String>)>(
        "SELECT categories, venue FROM events WHERE id = $1",
    )
    .bind(&payload.event_id)
    .fetch_optional(&pool)
    .await
    .map_err(|e| {
        eprintln!("Database error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let (event_categories, event_venue) = event.unwrap_or((None, None));

    // Ensure the user exists in public.users to avoid foreign key constraint error
    let user_exists =
        sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)")
            .bind(auth.user_id)
            .fetch_one(&pool)
            .await
            .map_err(|e| {
                eprintln!("Database error: {}", e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

    if !user_exists {
        eprintln!(
            "[ERROR] Interaction tracking failed: User {} does not exist in public.users. Profile trigger may have failed.",
            auth.user_id
        );
        return Err(StatusCode::FORBIDDEN);
    }

    // DEBUG: Interaction detected
    println!(
        "[DEBUG] Interaction detected: User {} performed '{}' on Event {}",
        auth.user_id, payload.interaction_type, payload.event_id
    );

    sqlx::query(
        r#"
        INSERT INTO user_interactions (id, user_id, event_id, interaction_type, event_categories, event_venue, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        "#,
    )
        .bind(&id)
        .bind(auth.user_id)
        .bind(&payload.event_id)
        .bind(&payload.interaction_type)
        .bind(&event_categories)
        .bind(&event_venue)
        .bind(&now)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let interaction = UserInteraction {
        id,
        user_id: auth.user_id,
        event_id: payload.event_id,
        interaction_type: payload.interaction_type,
        event_categories,
        event_venue,
        created_at: now,
    };

    Ok((StatusCode::CREATED, Json(interaction)))
}
