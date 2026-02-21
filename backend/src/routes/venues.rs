//! # Venues Routes
//!
//! This module handles venue-related API endpoints.
//! Venues are populated by the scraper and automatically enriched with
//! address, website, and coordinates via Google Places API.
//!
//! ## Endpoints
//! - `GET  /api/venues`              - List all venues
//! - `POST /api/venues`              - Create or update a venue
//! - `GET  /api/venues/:id`          - Get a single venue
//! - `GET  /api/venues/missing`      - Get venues missing website URLs
//! - `PATCH /api/venues/:id`         - Update venue (add website, etc.)

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::get,
    Json,
    Router,
};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

// =============================================================================
// MODELS
// =============================================================================

#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct Venue {
    pub id: Uuid,
    pub name: String,
    pub address: Option<String>,
    pub city: Option<String>,
    pub capacity: Option<i32>,
    pub venue_type: Option<String>,
    pub noise_level: Option<String>,
    pub parking_info: Option<String>,
    pub accessibility_info: Option<String>,
    pub website: Option<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct CreateVenue {
    pub name: String,
    pub address: Option<String>,
    pub city: Option<String>,
    pub website: Option<String>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateVenue {
    pub address: Option<String>,
    pub city: Option<String>,
    pub capacity: Option<i32>,
    pub venue_type: Option<String>,
    pub noise_level: Option<String>,
    pub parking_info: Option<String>,
    pub accessibility_info: Option<String>,
    pub website: Option<String>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    pub limit: Option<i32>,
    pub missing_website: Option<bool>,
}

// =============================================================================
// ROUTE DEFINITIONS
// =============================================================================

pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/", get(list_venues).post(create_venue))
        .route("/missing", get(list_missing_websites))
        .route("/:id", get(get_venue).patch(update_venue))
}

// =============================================================================
// HANDLER: LIST ALL VENUES
// =============================================================================

async fn list_venues(
    State(pool): State<PgPool>,
    Query(params): Query<ListQuery>,
) -> Result<Json<Vec<Venue>>, StatusCode> {
    let limit = params.limit.unwrap_or(500).min(1000);

    let venues = if params.missing_website.unwrap_or(false) {
        sqlx::query_as::<_, Venue>(
            r#"
            SELECT id, name, address, city, capacity, venue_type, noise_level,
                   parking_info, accessibility_info, website, created_at,
                   latitude, longitude
            FROM venues
            WHERE website IS NULL OR website = ''
            ORDER BY name ASC
            LIMIT $1
            "#
        )
            .bind(limit)
            .fetch_all(&pool)
            .await
    } else {
        sqlx::query_as::<_, Venue>(
            r#"
            SELECT id, name, address, city, capacity, venue_type, noise_level,
                   parking_info, accessibility_info, website, created_at,
                   latitude, longitude
            FROM venues
            ORDER BY name ASC
            LIMIT $1
            "#
        )
            .bind(limit)
            .fetch_all(&pool)
            .await
    }
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(venues))
}

// =============================================================================
// HANDLER: LIST VENUES MISSING WEBSITE
// =============================================================================

async fn list_missing_websites(
    State(pool): State<PgPool>,
) -> Result<Json<Vec<Venue>>, StatusCode> {
    let venues = sqlx::query_as::<_, Venue>(
        r#"
        SELECT id, name, address, city, capacity, venue_type, noise_level,
               parking_info, accessibility_info, website, created_at,
               latitude, longitude
        FROM venues
        WHERE website IS NULL OR website = ''
        ORDER BY name ASC
        "#
    )
        .fetch_all(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(venues))
}

// =============================================================================
// HANDLER: GET SINGLE VENUE
// =============================================================================

async fn get_venue(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Venue>, StatusCode> {
    let venue = sqlx::query_as::<_, Venue>(
        r#"
        SELECT id, name, address, city, capacity, venue_type, noise_level,
               parking_info, accessibility_info, website, created_at,
               latitude, longitude
        FROM venues
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

    match venue {
        Some(v) => Ok(Json(v)),
        None => Err(StatusCode::NOT_FOUND),
    }
}

// =============================================================================
// HANDLER: CREATE VENUE (UPSERT BY NAME)
// =============================================================================

/// Creates a venue if it doesn't exist, or fills in missing fields on existing.
/// This is called by the scraper to register venues it discovers.
/// On existing venues, fills any NULL fields with incoming data (never overwrites).
async fn create_venue(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateVenue>,
) -> Result<(StatusCode, Json<Venue>), StatusCode> {
    // Check if venue already exists by name (case-insensitive)
    let existing = sqlx::query_as::<_, Venue>(
        r#"
        SELECT id, name, address, city, capacity, venue_type, noise_level,
               parking_info, accessibility_info, website, created_at,
               latitude, longitude
        FROM venues
        WHERE LOWER(name) = LOWER($1)
        "#
    )
        .bind(&payload.name)
        .fetch_optional(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    if let Some(venue) = existing {
        // Venue exists — fill in any missing fields (COALESCE keeps existing values)
        let needs_update =
            (venue.website.is_none() && payload.website.is_some()) ||
                (venue.address.is_none() && payload.address.is_some()) ||
                (venue.latitude.is_none() && payload.latitude.is_some());

        if needs_update {
            sqlx::query(
                r#"
                UPDATE venues SET
                    address = COALESCE(address, $2),
                    city = COALESCE(city, $3),
                    website = COALESCE(website, $4),
                    latitude = COALESCE(latitude, $5),
                    longitude = COALESCE(longitude, $6)
                WHERE id = $1
                "#
            )
                .bind(&venue.id)
                .bind(&payload.address)
                .bind(&payload.city)
                .bind(&payload.website)
                .bind(&payload.latitude)
                .bind(&payload.longitude)
                .execute(&pool)
                .await
                .map_err(|e| {
                    eprintln!("Database error: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?;

            // Fetch updated venue
            let updated = sqlx::query_as::<_, Venue>(
                r#"
                SELECT id, name, address, city, capacity, venue_type, noise_level,
                       parking_info, accessibility_info, website, created_at,
                       latitude, longitude
                FROM venues
                WHERE id = $1
                "#
            )
                .bind(&venue.id)
                .fetch_one(&pool)
                .await
                .map_err(|e| {
                    eprintln!("Database error: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?;

            return Ok((StatusCode::OK, Json(updated)));
        }

        // Nothing to update
        return Ok((StatusCode::OK, Json(venue)));
    }

    // Create new venue
    let id = Uuid::new_v4();
    let now = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO venues (id, name, address, city, website, latitude, longitude, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        "#
    )
        .bind(&id)
        .bind(&payload.name)
        .bind(&payload.address)
        .bind(&payload.city)
        .bind(&payload.website)
        .bind(&payload.latitude)
        .bind(&payload.longitude)
        .bind(&now)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let venue = Venue {
        id,
        name: payload.name,
        address: payload.address,
        city: payload.city,
        capacity: None,
        venue_type: None,
        noise_level: None,
        parking_info: None,
        accessibility_info: None,
        website: payload.website,
        created_at: now,
        latitude: payload.latitude,
        longitude: payload.longitude,
    };

    Ok((StatusCode::CREATED, Json(venue)))
}

// =============================================================================
// HANDLER: UPDATE VENUE
// =============================================================================

/// Updates a venue's details. Uses COALESCE to only fill NULL fields.
async fn update_venue(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
    Json(payload): Json<UpdateVenue>,
) -> Result<Json<Venue>, StatusCode> {
    sqlx::query(
        r#"
        UPDATE venues
        SET address = COALESCE($2, address),
            city = COALESCE($3, city),
            capacity = COALESCE($4, capacity),
            venue_type = COALESCE($5, venue_type),
            noise_level = COALESCE($6, noise_level),
            parking_info = COALESCE($7, parking_info),
            accessibility_info = COALESCE($8, accessibility_info),
            website = COALESCE($9, website),
            latitude = COALESCE($10, latitude),
            longitude = COALESCE($11, longitude)
        WHERE id = $1
        "#
    )
        .bind(&id)
        .bind(&payload.address)
        .bind(&payload.city)
        .bind(&payload.capacity)
        .bind(&payload.venue_type)
        .bind(&payload.noise_level)
        .bind(&payload.parking_info)
        .bind(&payload.accessibility_info)
        .bind(&payload.website)
        .bind(&payload.latitude)
        .bind(&payload.longitude)
        .execute(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Fetch and return updated venue
    let venue = sqlx::query_as::<_, Venue>(
        r#"
        SELECT id, name, address, city, capacity, venue_type, noise_level,
               parking_info, accessibility_info, website, created_at,
               latitude, longitude
        FROM venues
        WHERE id = $1
        "#
    )
        .bind(id)
        .fetch_one(&pool)
        .await
        .map_err(|e| {
            eprintln!("Database error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(venue))
}