//! # Analytics Routes
//!
//! Dedicated, lightweight click tracking for venue-traffic measurement.
//!
//! This is deliberately decoupled from the ML interaction flow
//! (`POST /api/users/me/interactions` → LLM → preferences):
//! - It accepts **anonymous** traffic (no auth required).
//! - It is a single thin INSERT — no LLM call, no preference math.
//! - It never surfaces errors to the client; analytics must not break UX.

use axum::{
    extract::{Query, State},
    http::{header, HeaderMap, StatusCode},
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;

use crate::auth::AuthUser;

/// Click types we accept. Anything else is silently dropped.
const ALLOWED_CLICK_TYPES: [&str; 3] = ["outbound_ticket", "outbound_venue", "event_detail"];

pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/click", post(record_click))
        .route("/venues/traffic", get(venue_traffic))
}

#[derive(Deserialize)]
pub struct ClickPayload {
    /// Client-generated anonymous id (localStorage). Always present.
    pub anon_id: String,
    /// Stable per-click id; reconciliation key for future affiliate sub-ids.
    pub click_uid: uuid::Uuid,
    /// One of ALLOWED_CLICK_TYPES.
    pub click_type: String,
    #[serde(default)]
    pub provider: Option<String>,
    #[serde(default)]
    pub event_id: Option<uuid::Uuid>,
    #[serde(default)]
    pub venue_id: Option<i32>,
    #[serde(default)]
    pub destination_url: Option<String>,
    #[serde(default)]
    pub referrer: Option<String>,
}

/// POST /api/analytics/click
///
/// Anonymous-OK. `Option<AuthUser>` resolves to `None` when there is no valid
/// Authorization header, so logged-in clicks attach `user_id` and anonymous
/// clicks still record via `anon_id`. Always returns 204.
pub async fn record_click(
    State(pool): State<PgPool>,
    user: Option<AuthUser>,
    headers: HeaderMap,
    Json(payload): Json<ClickPayload>,
) -> StatusCode {
    // Drop junk click types without erroring.
    if !ALLOWED_CLICK_TYPES.contains(&payload.click_type.as_str()) {
        return StatusCode::NO_CONTENT;
    }

    let user_id = user.map(|u| u.user_id);

    // Capture (and bound) the user agent server-side.
    let user_agent = headers
        .get(header::USER_AGENT)
        .and_then(|v| v.to_str().ok())
        .map(|s| s.chars().take(512).collect::<String>());

    let provider = payload
        .provider
        .filter(|p| !p.is_empty())
        .unwrap_or_else(|| "unknown".to_string());

    let result = sqlx::query(
        "INSERT INTO analytics_clicks
            (anon_id, user_id, event_id, venue_id, click_type, provider,
             destination_url, click_uid, referrer, user_agent)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
    )
    .bind(&payload.anon_id)
    .bind(user_id)
    .bind(payload.event_id)
    .bind(payload.venue_id)
    .bind(&payload.click_type)
    .bind(&provider)
    .bind(&payload.destination_url)
    .bind(payload.click_uid)
    .bind(&payload.referrer)
    .bind(&user_agent)
    .execute(&pool)
    .await;

    if let Err(e) = result {
        // Log, but never tell the client — a failed beacon must not block nav.
        eprintln!("Failed to insert analytics click: {}", e);
    }

    StatusCode::NO_CONTENT
}

// =============================================================================
// VENUE TRAFFIC REPORT
// =============================================================================

#[derive(Deserialize)]
pub struct TrafficParams {
    /// Lookback window in days (default 30, clamped to 1..=365).
    #[serde(default)]
    pub days: Option<i32>,
}

#[derive(Serialize, sqlx::FromRow)]
pub struct VenueTraffic {
    pub venue_id: i32,
    pub name: String,
    pub total_clicks: i64,
    pub ticket_clicks: i64,
    pub venue_clicks: i64,
    pub detail_clicks: i64,
    pub unique_visitors: i64,
}

/// GET /api/analytics/venues/traffic?days=30
///
/// Per-venue click traffic leaderboard. Requires authentication (any logged-in
/// user) as a minimal gate — there is no admin role system yet.
pub async fn venue_traffic(
    State(pool): State<PgPool>,
    _auth: AuthUser,
    Query(params): Query<TrafficParams>,
) -> Result<Json<Vec<VenueTraffic>>, StatusCode> {
    let days = params.days.unwrap_or(30).clamp(1, 365);

    let rows = sqlx::query_as::<_, VenueTraffic>(
        "SELECT
            v.venue_id,
            v.name,
            count(*)                                                    AS total_clicks,
            count(*) FILTER (WHERE c.click_type = 'outbound_ticket')    AS ticket_clicks,
            count(*) FILTER (WHERE c.click_type = 'outbound_venue')     AS venue_clicks,
            count(*) FILTER (WHERE c.click_type = 'event_detail')       AS detail_clicks,
            count(DISTINCT c.anon_id)                                   AS unique_visitors
         FROM analytics_clicks c
         JOIN venues v ON v.venue_id = c.venue_id
         WHERE c.occurred_at >= now() - make_interval(days => $1)
         GROUP BY v.venue_id, v.name
         ORDER BY total_clicks DESC",
    )
    .bind(days)
    .fetch_all(&pool)
    .await
    .map_err(|e| {
        eprintln!("venue_traffic query failed: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(rows))
}