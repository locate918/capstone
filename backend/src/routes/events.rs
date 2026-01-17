use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::get,
    Json, Router,
};
use serde::Deserialize;
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{Event, CreateEvent};

pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/", get(list_events).post(create_event))
        .route("/search", get(search_events))
        .route("/:id", get(get_event))
}

async fn list_events(
    State(pool): State<PgPool>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let events = sqlx::query_as::<_, Event>(
        "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events ORDER BY start_time ASC"
    )
        .fetch_all(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(events))
}

async fn get_event(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Event>, StatusCode> {
    let event = sqlx::query_as::<_, Event>(
        "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events WHERE id = $1"
    )
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    match event {
        Some(e) => Ok(Json(e)),
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn create_event(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateEvent>,
) -> Result<(StatusCode, Json<Event>), StatusCode> {
    let id = Uuid::new_v4();
    let created_at = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO events (id, title, description, location, venue, source_url, start_time, end_time, category, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        "#,
    )
        .bind(&id)
        .bind(&payload.title)
        .bind(&payload.description)
        .bind(&payload.location)
        .bind(&payload.venue)
        .bind(&payload.source_url)
        .bind(&payload.start_time)
        .bind(&payload.end_time)
        .bind(&payload.category)
        .bind(&created_at)
        .execute(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let event = Event {
        id,
        title: payload.title,
        description: payload.description,
        location: payload.location,
        venue: payload.venue,
        source_url: payload.source_url,
        start_time: payload.start_time,
        end_time: payload.end_time,
        category: payload.category,
        created_at,
    };

    Ok((StatusCode::CREATED, Json(event)))
}

#[derive(Deserialize)]
pub struct SearchQuery {
    q: Option<String>,
    category: Option<String>,
}

async fn search_events(
    State(pool): State<PgPool>,
    Query(params): Query<SearchQuery>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let events = match (&params.q, &params.category) {
        (Some(q), Some(cat)) => {
            let search = format!("%{}%", q);
            sqlx::query_as::<_, Event>(
                "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events WHERE (title ILIKE $1 OR description ILIKE $1) AND category = $2 ORDER BY start_time ASC"
            )
                .bind(&search)
                .bind(cat)
                .fetch_all(&pool)
                .await
        }
        (Some(q), None) => {
            let search = format!("%{}%", q);
            sqlx::query_as::<_, Event>(
                "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events WHERE title ILIKE $1 OR description ILIKE $1 ORDER BY start_time ASC"
            )
                .bind(&search)
                .fetch_all(&pool)
                .await
        }
        (None, Some(cat)) => {
            sqlx::query_as::<_, Event>(
                "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events WHERE category = $1 ORDER BY start_time ASC"
            )
                .bind(cat)
                .fetch_all(&pool)
                .await
        }
        (None, None) => {
            sqlx::query_as::<_, Event>(
                "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events ORDER BY start_time ASC"
            )
                .fetch_all(&pool)
                .await
        }
    }
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(events))
}