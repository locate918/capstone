mod events;

use axum::Router;
use sqlx::PgPool;

pub fn create_routes() -> Router<PgPool> {
    Router::new()
        .nest("/events", events::routes())
}