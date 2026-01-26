//! # Events Routes
//!
//! This module handles all event-related API endpoints.
//! Events are the core data type for Locate918 - they represent
//! local happenings that users want to discover.
//!
//! ## Endpoints
//! - `GET  /api/events`         - List all events (sorted by start time)
//! - `POST /api/events`         - Create a new event
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
use serde::Deserialize;
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{Event, CreateEvent};

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
// HANDLER: LIST ALL EVENTS
// =============================================================================

/// Returns all upcoming events, sorted by start time.
///
/// # Endpoint
/// `GET /api/events`
async fn list_events(
    State(pool): State<PgPool>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let events = sqlx::query_as::<_, Event>(
        r#"
        SELECT id, title, description, venue, venue_address, location,
               source_url, source_name, start_time, end_time, categories,
               price_min, price_max, outdoor, family_friendly, image_url,
               created_at, updated_at
        FROM events
        WHERE start_time >= NOW()
        ORDER BY start_time ASC
        LIMIT 100
        "#
    )
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
///
/// # Endpoint
/// `GET /api/events/:id`
async fn get_event(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Event>, StatusCode> {
    let event = sqlx::query_as::<_, Event>(
        r#"
        SELECT id, title, description, venue, venue_address, location,
               source_url, source_name, start_time, end_time, categories,
               price_min, price_max, outdoor, family_friendly, image_url,
               created_at, updated_at
        FROM events
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

    match event {
        Some(e) => Ok(Json(e)),
        None => Err(StatusCode::NOT_FOUND),
    }
}

// =============================================================================
// HANDLER: CREATE EVENT
// =============================================================================

/// Creates a new event in the database.
///
/// # Endpoint
/// `POST /api/events`
async fn create_event(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateEvent>,
) -> Result<(StatusCode, Json<Event>), StatusCode> {
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO events (
            id, title, description, venue, venue_address, location,
            source_url, source_name, start_time, end_time, categories,
            price_min, price_max, outdoor, family_friendly, image_url,
            created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        "#,
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

    let event = Event {
        id,
        title: payload.title,
        description: payload.description,
        venue: payload.venue,
        venue_address: payload.venue_address,
        location: payload.location,
        source_url: payload.source_url,
        source_name: payload.source_name,
        start_time: payload.start_time,
        end_time: payload.end_time,
        categories: payload.categories,
        price_min: payload.price_min,
        price_max: payload.price_max,
        outdoor: payload.outdoor,
        family_friendly: payload.family_friendly,
        image_url: payload.image_url,
        created_at: now,
        updated_at: now,
    };

    Ok((StatusCode::CREATED, Json(event)))
}

// =============================================================================
// SEARCH QUERY PARAMETERS
// =============================================================================

/// Query parameters for the search endpoint.
///
/// All fields are optional, allowing flexible search combinations.
///
/// # Examples
/// - `/search?q=jazz` - Text search
/// - `/search?category=concerts` - Filter by category
/// - `/search?outdoor=true&family_friendly=true` - Filter by attributes
/// - `/search?price_max=25` - Filter by price
/// - `/search?start_date=2026-01-25&end_date=2026-01-26` - Date range
#[derive(Debug, Deserialize)]
pub struct SearchQuery {
    /// Text to search for in event title and description
    pub q: Option<String>,

    /// Category to filter by (matches any category in the array)
    pub category: Option<String>,

    /// Start of date range (ISO 8601 format)
    pub start_date: Option<DateTime<Utc>>,

    /// End of date range (ISO 8601 format)
    pub end_date: Option<DateTime<Utc>>,

    /// Filter by location
    pub location: Option<String>,

    /// Maximum price filter
    pub price_max: Option<f64>,

    /// Only show outdoor events
    pub outdoor: Option<bool>,

    /// Only show family-friendly events
    pub family_friendly: Option<bool>,

    /// Maximum number of results (default: 50)
    pub limit: Option<i32>,
}

// =============================================================================
// HANDLER: SEARCH EVENTS
// =============================================================================

/// Searches events with multiple filter options.
///
/// # Endpoint
/// `GET /api/events/search`
///
/// # Query Parameters
/// - `q` - Text search in title/description
/// - `category` - Filter by category
/// - `start_date` - Start of date range
/// - `end_date` - End of date range
/// - `location` - Filter by location
/// - `price_max` - Maximum price
/// - `outdoor` - Only outdoor events (true/false)
/// - `family_friendly` - Only family-friendly events (true/false)
/// - `limit` - Max results (default 50)
///
/// This endpoint is called by the LLM's `search_events` tool.
async fn search_events(
    State(pool): State<PgPool>,
    Query(params): Query<SearchQuery>,
) -> Result<Json<Vec<Event>>, StatusCode> {

    // Build dynamic query
    let mut conditions: Vec<String> = vec![];
    let limit = params.limit.unwrap_or(50).min(100);

    // Text search
    if let Some(ref q) = params.q {
        conditions.push(format!(
            "(title ILIKE '%{}%' OR description ILIKE '%{}%')",
            q.replace('\'', "''"), // Basic SQL injection prevention
            q.replace('\'', "''")
        ));
    }

    // Category filter (check if category is in the categories array)
    if let Some(ref cat) = params.category {
        conditions.push(format!(
            "'{}' = ANY(categories)",
            cat.replace('\'', "''")
        ));
    }

    // Date range
    if let Some(start) = params.start_date {
        conditions.push(format!("start_time >= '{}'", start.to_rfc3339()));
    } else {
        // Default: only future events
        conditions.push("start_time >= NOW()".to_string());
    }

    if let Some(end) = params.end_date {
        conditions.push(format!("start_time <= '{}'", end.to_rfc3339()));
    }

    // Location filter
    if let Some(ref loc) = params.location {
        conditions.push(format!(
            "location ILIKE '%{}%'",
            loc.replace('\'', "''")
        ));
    }

    // Price filter (check if at least one price is within budget)
    if let Some(max_price) = params.price_max {
        conditions.push(format!(
            "(price_min IS NULL OR price_min <= {})",
            max_price
        ));
    }

    // Outdoor filter
    if let Some(outdoor) = params.outdoor {
        conditions.push(format!("outdoor = {}", outdoor));
    }

    // Family-friendly filter
    if let Some(ff) = params.family_friendly {
        conditions.push(format!("family_friendly = {}", ff));
    }

    // Build WHERE clause
    let where_clause = if conditions.is_empty() {
        "WHERE start_time >= NOW()".to_string()
    } else {
        format!("WHERE {}", conditions.join(" AND "))
    };

    // Execute query
    let query = format!(
        r#"
        SELECT id, title, description, venue, venue_address, location,
               source_url, source_name, start_time, end_time, categories,
               price_min, price_max, outdoor, family_friendly, image_url,
               created_at, updated_at
        FROM events
        {}
        ORDER BY start_time ASC
        LIMIT {}
        "#,
        where_clause, limit
    );

    let events = sqlx::query_as::<_, Event>(&query)
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(events))
}