// Chat Endpoint
// Owner: Ben (AI Engineer)
//
// POST /api/chat
//
// Request body:
// {
//     "message": "What's happening this weekend?"
// }
//
// Response body:
// {
//     "reply": "I found 3 events this weekend...",
//     "events": [...]
// }
//
// use axum::{
//     extract::State,
//     http::StatusCode,
//     routing::post,
//     Json, Router,
// };
// use serde::{Deserialize, Serialize};
// use sqlx::PgPool;
//
// #[derive(Deserialize)]
// pub struct ChatRequest {
//     pub message: String,
// }
//
// #[derive(Serialize)]
// pub struct ChatResponse {
//     pub reply: String,
//     pub events: Vec<crate::models::Event>,
// }
//
// pub fn routes() -> Router<PgPool> {
//     Router::new()
//         .route("/", post(chat))
// }
//
// async fn chat(
//     State(pool): State<PgPool>,
//     Json(payload): Json<ChatRequest>,
// ) -> Result<Json<ChatResponse>, StatusCode> {
//     todo!()
// }