mod events;
mod chat;

use axum::Router;
use sqlx::PgPool;

pub fn create_routes() -> Router<PgPool> {
    Router::new()
        .nest("/events", events::routes())
    // .nest("/chat", chat::routes())  // Uncomment when Ben implements
}