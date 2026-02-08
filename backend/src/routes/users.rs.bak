//! # Users Routes
//!
//! This module handles all user-related API endpoints including
//! user accounts, preferences, and interaction tracking.
//!
//! ## Endpoints
//! - `POST /api/users`                    - Create a new user
//! - `GET  /api/users/:id`                - Get user by ID
//! - `GET  /api/users/:id/profile`        - Get full profile (for LLM)
//! - `GET  /api/users/:id/preferences`    - Get category preferences
//! - `POST /api/users/:id/preferences`    - Add/update a preference
//! - `PUT  /api/users/:id/preferences`    - Update user settings
//! - `GET  /api/users/:id/interactions`   - Get interaction history
//! - `POST /api/users/:id/interactions`   - Record an interaction
//!
//! ## Owner
//! Will (Coordinator/Backend Lead)

// =============================================================================
// IMPORTS
// =============================================================================

use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post, put},
    Json, Router,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{
    CreateUser, CreateUserInteraction, CreateUserPreference, UpdateUserPreferences,
    User, UserInteraction, UserInteractionWithEvent, UserPreference, UserProfile,
};

// =============================================================================
// ROUTE DEFINITIONS
// =============================================================================

/// Creates the router for all user endpoints.
pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/", post(create_user))
        .route("/:id", get(get_user))
        .route("/:id/profile", get(get_user_profile))
        .route("/:id/preferences", get(get_preferences).post(add_preference).put(update_preferences))
        .route("/:id/interactions", get(get_interactions).post(add_interaction))
}

// =============================================================================
// HANDLER: CREATE USER
// =============================================================================

/// Creates a new user account.
///
/// # Endpoint
/// `POST /api/users`
async fn create_user(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateUser>,
) -> Result<(StatusCode, Json<User>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO users (id, email, name, location_preference, radius_miles, price_max, family_friendly_only, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        "#,
    )
        .bind(&id)
        .bind(&payload.email)
        .bind(&payload.name)
        .bind(&payload.location_preference)
        .bind(&payload.radius_miles)
        .bind(&payload.price_max)
        .bind(&payload.family_friendly_only)
        .bind(&now)
        .bind(&now)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let user = User {
        id,
        email: payload.email,
        name: payload.name,
        location_preference: payload.location_preference,
        radius_miles: payload.radius_miles,
        price_max: payload.price_max,
        family_friendly_only: payload.family_friendly_only,
        created_at: now,
        updated_at: now,
    };

    Ok((StatusCode::CREATED, Json(user)))
}

// =============================================================================
// HANDLER: GET USER
// =============================================================================

/// Returns a single user by ID.
///
/// # Endpoint
/// `GET /api/users/:id`
async fn get_user(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<User>, StatusCode> {
    let user = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, location_preference, radius_miles, price_max, family_friendly_only, created_at, updated_at
        FROM users
        WHERE id = $1
        "#
    )
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    match user {
        Some(u) => Ok(Json(u)),
        None => Err(StatusCode::NOT_FOUND),
    }
}

// =============================================================================
// HANDLER: GET USER PROFILE (for LLM)
// =============================================================================

/// Returns complete user profile for LLM personalization.
///
/// # Endpoint
/// `GET /api/users/:id/profile`
///
/// Includes:
/// - Basic user info
/// - All category preferences
/// - Recent 20 interactions with event details
async fn get_user_profile(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<UserProfile>, StatusCode> {
    // Fetch user
    let user = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, location_preference, radius_miles, price_max, family_friendly_only, created_at, updated_at
        FROM users
        WHERE id = $1
        "#
    )
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Fetch preferences
    let preferences = sqlx::query_as::<_, UserPreference>(
        "SELECT id, user_id, category, weight, created_at FROM user_preferences WHERE user_id = $1"
    )
        .bind(id)
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
               (SELECT categories[1] FROM events WHERE id = ui.event_id) as event_category,
               ui.created_at
        FROM user_interactions ui
        JOIN events e ON ui.event_id = e.id
        WHERE ui.user_id = $1
        ORDER BY ui.created_at DESC
        LIMIT 20
        "#
    )
        .bind(id)
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

/// Returns all category preferences for a user.
///
/// # Endpoint
/// `GET /api/users/:id/preferences`
async fn get_preferences(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<UserPreference>>, StatusCode> {
    let preferences = sqlx::query_as::<_, UserPreference>(
        "SELECT id, user_id, category, weight, created_at FROM user_preferences WHERE user_id = $1 ORDER BY weight DESC"
    )
        .bind(id)
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
/// `POST /api/users/:id/preferences`
///
/// Uses UPSERT - creates if new, updates if exists.
async fn add_preference(
    State(pool): State<PgPool>,
    Path(user_id): Path<Uuid>,
    Json(payload): Json<CreateUserPreference>,
) -> Result<(StatusCode, Json<UserPreference>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Use INSERT ... ON CONFLICT for upsert behavior
    let result = sqlx::query_as::<_, UserPreference>(
        r#"
        INSERT INTO user_preferences (id, user_id, category, weight, created_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, category)
        DO UPDATE SET weight = EXCLUDED.weight
        RETURNING id, user_id, category, weight, created_at
        "#
    )
        .bind(&id)
        .bind(&user_id)
        .bind(&payload.category)
        .bind(&payload.weight)
        .bind(&now)
        .fetch_one(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok((StatusCode::CREATED, Json(result)))
}

// =============================================================================
// HANDLER: UPDATE USER PREFERENCES (settings)
// =============================================================================

/// Updates user's preference settings (location, radius, price, etc).
///
/// # Endpoint
/// `PUT /api/users/:id/preferences`
async fn update_preferences(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
    Json(payload): Json<UpdateUserPreferences>,
) -> Result<Json<User>, StatusCode> {
    // Build dynamic update query
    let mut updates = vec!["updated_at = NOW()".to_string()];

    if let Some(ref loc) = payload.location_preference {
        updates.push(format!("location_preference = '{}'", loc.replace('\'', "''")));
    }
    if let Some(radius) = payload.radius_miles {
        updates.push(format!("radius_miles = {}", radius));
    }
    if let Some(price) = payload.price_max {
        updates.push(format!("price_max = {}", price));
    }
    if let Some(ff) = payload.family_friendly_only {
        updates.push(format!("family_friendly_only = {}", ff));
    }

    let query = format!(
        r#"
        UPDATE users
        SET {}
        WHERE id = $1
        RETURNING id, email, name, location_preference, radius_miles, price_max, family_friendly_only, created_at, updated_at
        "#,
        updates.join(", ")
    );

    let user = sqlx::query_as::<_, User>(&query)
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(user))
}

// =============================================================================
// HANDLER: GET INTERACTIONS
// =============================================================================

/// Returns all interactions for a user.
///
/// # Endpoint
/// `GET /api/users/:id/interactions`
async fn get_interactions(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<UserInteraction>>, StatusCode> {
    let interactions = sqlx::query_as::<_, UserInteraction>(
        r#"
        SELECT id, user_id, event_id, interaction_type, event_category, event_venue, created_at
        FROM user_interactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 100
        "#
    )
        .bind(id)
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
/// `POST /api/users/:id/interactions`
///
/// Automatically captures event category and venue for ML.
async fn add_interaction(
    State(pool): State<PgPool>,
    Path(user_id): Path<Uuid>,
    Json(payload): Json<CreateUserInteraction>,
) -> Result<(StatusCode, Json<UserInteraction>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Fetch event details for denormalization
    let event = sqlx::query_as::<_, (Option<String>, Option<String>)>(
        "SELECT (SELECT categories[1] FROM events WHERE id = $1), venue FROM events WHERE id = $1"
    )
        .bind(&payload.event_id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let (event_category, event_venue) = event.unwrap_or((None, None));

    sqlx::query(
        r#"
        INSERT INTO user_interactions (id, user_id, event_id, interaction_type, event_category, event_venue, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        "#
    )
        .bind(&id)
        .bind(&user_id)
        .bind(&payload.event_id)
        .bind(&payload.interaction_type)
        .bind(&event_category)
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
        user_id,
        event_id: payload.event_id,
        interaction_type: payload.interaction_type,
        event_category,
        event_venue,
        created_at: now,
    };

    Ok((StatusCode::CREATED, Json(interaction)))
}