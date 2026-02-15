//! # Events Routes
//!
//! This module handles all event-related API endpoints.
//! Events are the core data type for Locate918 - they represent
//! local happenings that users want to discover.
//!
//! ## Endpoints
//! - `GET  /api/events`         - List all events (sorted by start time)
//! - `POST /api/events`         - Create or update an event (UPSERT)
//! - `GET  /api/events/:id`     - Get a single event by UUID
//! - `GET  /api/events/search`  - Search with multiple filters
//!
//! ## Owner
//! Will (Coordinator/Backend Lead)

// =============================================================================
// IMPORTS
// =============================================================================

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::get,
    Json,
    Router,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

// =============================================================================
// DATA STRUCTURES
// =============================================================================

/// Event model returned from API (includes venue_website from JOIN)
#[derive(Debug, Serialize, FromRow)]
pub struct Event {
    pub id: Uuid,
    pub title: String,
    pub description: Option<String>,
    pub venue: Option<String>,
    pub venue_address: Option<String>,
    pub location: Option<String>,
    pub source_url: String,
    pub source_name: Option<String>,
    pub start_time: DateTime<Utc>,
    pub end_time: Option<DateTime<Utc>>,
    pub categories: Option<Vec<String>>,
    pub price_min: Option<f64>,
    pub price_max: Option<f64>,
    pub outdoor: Option<bool>,
    pub family_friendly: Option<bool>,
    pub image_url: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    // NEW: venue website from venues table
    pub venue_website: Option<String>,
}

/// Payload for creating/updating events (no venue_website - that comes from venues table)
#[derive(Debug, Deserialize)]
pub struct CreateEvent {
    pub title: String,
    pub description: Option<String>,
    pub venue: Option<String>,
    pub venue_address: Option<String>,
    pub location: Option<String>,
    pub source_url: String,
    pub source_name: Option<String>,
    pub start_time: DateTime<Utc>,
    pub end_time: Option<DateTime<Utc>>,
    pub categories: Option<Vec<String>>,
    pub price_min: Option<f64>,
    pub price_max: Option<f64>,
    pub outdoor: Option<bool>,
    pub family_friendly: Option<bool>,
    pub image_url: Option<String>,
}

// =============================================================================
// ROUTE DEFINITIONS
// =============================================================================

/// Creates the router for all event endpoints.
pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/", get(list_events).post(create_event))
        .route("/search", get(search_events))
        .route("/:id", get(get_event))
}

// =============================================================================
// QUERY PARAMETERS FOR LIST
// =============================================================================

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    /// Maximum number of results (default: 100, max: 1000)
    pub limit: Option<i32>,
}

// =============================================================================
// HANDLER: LIST ALL EVENTS
// =============================================================================

/// Returns all upcoming events, sorted by start time.
/// Includes venue_website from venues table via LEFT JOIN.
///
/// # Endpoint
/// `GET /api/events`
/// `GET /api/events?limit=500`
async fn list_events(
    State(pool): State<PgPool>,
    Query(params): Query<ListQuery>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let limit = params.limit.unwrap_or(100).min(1000);

    let events = sqlx::query_as::<_, Event>(
        r#"
        SELECT
            e.id, e.title, e.description, e.venue, e.venue_address, e.location,
            e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
            e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
            e.created_at, e.updated_at,
            v.website AS venue_website
        FROM events e
        LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
        WHERE e.start_time >= NOW()
        ORDER BY e.start_time ASC
        LIMIT $1
        "#
    )
        .bind(limit)
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(events))
}

// =============================================================================
// HANDLER: GET SINGLE EVENT
// =============================================================================

/// Returns a single event by its UUID.
/// Includes venue_website from venues table via LEFT JOIN.
///
/// # Endpoint
/// `GET /api/events/:id`
async fn get_event(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Event>, StatusCode> {
    let event = sqlx::query_as::<_, Event>(
        r#"
        SELECT
            e.id, e.title, e.description, e.venue, e.venue_address, e.location,
            e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
            e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
            e.created_at, e.updated_at,
            v.website AS venue_website
        FROM events e
        LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
        WHERE e.id = $1
        "#
    )
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    match event {
        Some(e) => Ok(Json(e)),
        None => Err(StatusCode::NOT_FOUND),
    }
}

// =============================================================================
// HANDLER: CREATE EVENT (UPSERT)
// =============================================================================

/// Creates a new event or updates existing one if source_url already exists.
///
/// # Endpoint
/// `POST /api/events`
///
/// Uses UPSERT (ON CONFLICT DO UPDATE) to handle re-scraping the same events.
/// If an event with the same source_url exists, it will be updated.
async fn create_event(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateEvent>,
) -> Result<(StatusCode, Json<Event>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // First, do the UPSERT
    let result = sqlx::query(
        r#"
        INSERT INTO events (
            id, title, description, venue, venue_address, location,
            source_url, source_name, start_time, end_time, categories,
            price_min, price_max, outdoor, family_friendly, image_url,
            created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        ON CONFLICT (source_url) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            venue = EXCLUDED.venue,
            venue_address = EXCLUDED.venue_address,
            location = EXCLUDED.location,
            source_name = EXCLUDED.source_name,
            start_time = EXCLUDED.start_time,
            end_time = EXCLUDED.end_time,
            categories = EXCLUDED.categories,
            price_min = EXCLUDED.price_min,
            price_max = EXCLUDED.price_max,
            outdoor = EXCLUDED.outdoor,
            family_friendly = EXCLUDED.family_friendly,
            image_url = EXCLUDED.image_url,
            updated_at = NOW()
        "#
    )
        .bind(&id)
        .bind(&payload.title)
        .bind(&payload.description)
        .bind(&payload.venue)
        .bind(&payload.venue_address)
        .bind(&payload.location)
        .bind(&payload.source_url)
        .bind(&payload.source_name)
        .bind(&payload.start_time)
        .bind(&payload.end_time)
        .bind(&payload.categories)
        .bind(&payload.price_min)
        .bind(&payload.price_max)
        .bind(&payload.outdoor)
        .bind(&payload.family_friendly)
        .bind(&payload.image_url)
        .bind(&now)
        .bind(&now)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Then fetch the event with venue_website JOIN
    let event = sqlx::query_as::<_, Event>(
        r#"
        SELECT
            e.id, e.title, e.description, e.venue, e.venue_address, e.location,
            e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
            e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
            e.created_at, e.updated_at,
            v.website AS venue_website
        FROM events e
        LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
        WHERE e.source_url = $1
        "#
    )
        .bind(&payload.source_url)
        .fetch_one(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error fetching created event: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok((StatusCode::OK, Json(event)))
}

// =============================================================================
// SEARCH QUERY PARAMETERS
// =============================================================================

#[derive(Debug, Deserialize)]
pub struct SearchQuery {
    /// Text search in title and description
    pub q: Option<String>,

    /// Filter by category (matches any in array)
    pub category: Option<String>,

    /// Filter by venue name (partial match)
    pub venue: Option<String>,

    /// Filter by location/area
    pub location: Option<String>,

    /// Filter by minimum date
    pub start_after: Option<DateTime<Utc>>,

    /// Filter by maximum date
    pub start_before: Option<DateTime<Utc>>,

    /// Only outdoor events
    pub outdoor: Option<bool>,

    /// Only family-friendly events
    pub family_friendly: Option<bool>,

    /// Maximum price filter
    pub max_price: Option<f64>,

    /// Pagination offset
    pub offset: Option<i32>,

    /// Results per page (max 100)
    pub limit: Option<i32>,
}

// =============================================================================
// HANDLER: SEARCH EVENTS
// =============================================================================

/// Advanced search with multiple filters.
/// Includes venue_website from venues table via LEFT JOIN.
///
/// # Endpoint
/// `GET /api/events/search?q=jazz&outdoor=true&limit=20`
async fn search_events(
    State(pool): State<PgPool>,
    Query(params): Query<SearchQuery>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let limit = params.limit.unwrap_or(50).min(100);
    let offset = params.offset.unwrap_or(0);

    // Build dynamic WHERE clauses
    let mut conditions = vec!["e.start_time >= NOW()".to_string()];
    let mut bind_index = 1;

    // Text search
    if let Some(ref q) = params.q {
        conditions.push(format!(
            "(e.title ILIKE ${} OR e.description ILIKE ${})",
            bind_index, bind_index + 1
        ));
        bind_index += 2;
    }

    // Category filter (using array overlap)
    if let Some(ref _category) = params.category {
        conditions.push(format!("${} = ANY(e.categories)", bind_index));
        bind_index += 1;
    }

    // Venue filter
    if let Some(ref _venue) = params.venue {
        conditions.push(format!("e.venue ILIKE ${}", bind_index));
        bind_index += 1;
    }

    // Location filter
    if let Some(ref _location) = params.location {
        conditions.push(format!("e.location ILIKE ${}", bind_index));
        bind_index += 1;
    }

    // Date filters
    if let Some(ref _start_after) = params.start_after {
        conditions.push(format!("e.start_time >= ${}", bind_index));
        bind_index += 1;
    }

    if let Some(ref _start_before) = params.start_before {
        conditions.push(format!("e.start_time <= ${}", bind_index));
        bind_index += 1;
    }

    // Boolean filters
    if params.outdoor == Some(true) {
        conditions.push("e.outdoor = TRUE".to_string());
    }

    if params.family_friendly == Some(true) {
        conditions.push("e.family_friendly = TRUE".to_string());
    }

    // Price filter
    if let Some(ref _max_price) = params.max_price {
        conditions.push(format!(
            "(e.price_min IS NULL OR e.price_min <= ${})",
            bind_index
        ));
        bind_index += 1;
    }

    let where_clause = conditions.join(" AND ");

    let query = format!(
        r#"
        SELECT
            e.id, e.title, e.description, e.venue, e.venue_address, e.location,
            e.source_url, e.source_name, e.start_time, e.end_time, e.categories,
            e.price_min, e.price_max, e.outdoor, e.family_friendly, e.image_url,
            e.created_at, e.updated_at,
            v.website AS venue_website
        FROM events e
        LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
        WHERE {}
        ORDER BY e.start_time ASC
        LIMIT ${} OFFSET ${}
        "#,
        where_clause, bind_index, bind_index + 1
    );

    // Build and execute query with bindings
    let mut query_builder = sqlx::query_as::<_, Event>(&query);

    if let Some(ref q) = params.q {
        let pattern = format!("%{}%", q);
        query_builder = query_builder.bind(pattern.clone()).bind(pattern);
    }

    if let Some(ref category) = params.category {
        query_builder = query_builder.bind(category);
    }

    if let Some(ref venue) = params.venue {
        query_builder = query_builder.bind(format!("%{}%", venue));
    }

    if let Some(ref location) = params.location {
        query_builder = query_builder.bind(format!("%{}%", location));
    }

    if let Some(ref start_after) = params.start_after {
        query_builder = query_builder.bind(start_after);
    }

    if let Some(ref start_before) = params.start_before {
        query_builder = query_builder.bind(start_before);
    }

    if let Some(ref max_price) = params.max_price {
        query_builder = query_builder.bind(max_price);
    }

    query_builder = query_builder.bind(limit).bind(offset);

    let events = query_builder
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Search error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(events))
}