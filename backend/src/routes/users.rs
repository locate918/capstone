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
//! - `GET  /api/users/me`                 - Get current user (from JWT)
//! - `GET  /api/users/me/profile`         - Get full profile (for LLM)
//! - `GET  /api/users/me/preferences`     - Get category preferences
//! - `POST /api/users/me/preferences`     - Add/update a preference
//! - `PUT  /api/users/me/preferences`     - Update user settings
//! - `GET  /api/users/me/interactions`    - Get interaction history
//! - `POST /api/users/me/interactions`    - Record an interaction
//!
//! ## Owner
//! Will (Coordinator/Backend Lead)

// =============================================================================
// IMPORTS
// =============================================================================

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post, put},
    Json, Router,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::auth::AuthUser;
use crate::models::{
    CreateUserInteraction, CreateUserPreference, UpdateUserPreferences,
    User, UserInteraction, UserInteractionWithEvent, UserPreference, UserProfile,
};

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
               price_max, family_friendly_only, created_at, updated_at
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
               price_max, family_friendly_only, created_at, updated_at
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
    let user_exists = sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)")
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
    // Use parameterized queries to prevent SQL injection
    let user = sqlx::query_as::<_, User>(
        r#"
        UPDATE users
        SET location_preference = COALESCE($2, location_preference),
            radius_miles = COALESCE($3, radius_miles),
            price_max = COALESCE($4, price_max),
            family_friendly_only = COALESCE($5, family_friendly_only),
            updated_at = NOW()
        WHERE id = $1
        RETURNING id, email, name, location_preference, radius_miles,
                  price_max, family_friendly_only, created_at, updated_at
        "#,
    )
        .bind(auth.user_id)
        .bind(&payload.location_preference)
        .bind(&payload.radius_miles)
        .bind(&payload.price_max)
        .bind(&payload.family_friendly_only)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)?;

    // DEBUG: User preferences updated (settings)
    println!(
        "[DEBUG] User preferences updated: User {} updated their profile settings",
        auth.user_id
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
    let user_exists = sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)")
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
