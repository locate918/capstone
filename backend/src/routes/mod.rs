mod events;
mod chat;
mod users;

use axum::Router;
use sqlx::PgPool;

pub fn create_routes() -> Router<PgPool> {
    Router::new()
        .nest("/events", events::routes())
        .nest("/users", users::routes())
    // .nest("/chat", chat::routes())  // Uncomment when Ben implements
}