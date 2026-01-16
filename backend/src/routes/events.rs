use axum::{
    extract::State,
    http::StatusCode,
    routing::get,
    Json, Router,
};
use sqlx::PgPool;

use crate::models::Event;

pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/", get(list_events))
}

async fn list_events(
    State(pool): State<PgPool>,
) -> Result<Json<Vec<Event>>, StatusCode> {
    let events = sqlx::query_as::<_, Event>(
        "SELECT id, title, description, location, venue, source_url, start_time, end_time, category, created_at FROM events"
    )
        .fetch_all(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(events))
}