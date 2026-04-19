//! # Chat Endpoint
//!
//! This module provides the natural language interface for event discovery.
//! Instead of using search filters, users can ask questions naturally:
//! - "What's happening this weekend?"
//! - "Any live music downtown tonight?"
//! - "Find me something fun to do with kids"
//!
//! ## Owner
//! Ben (AI Engineer)
//!
//! ## Endpoint
//! `POST /api/chat`
//!
//! ## How It Works
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                         Request Flow                            │
//! └─────────────────────────────────────────────────────────────────┘
//!
//! 1. User sends message
//!    POST /api/chat
//!    { "message": "Any concerts this weekend?", "user_id": "..." }
//!
//! 2. Fetch user profile (optional, for personalization)
//!    - Preferences (likes music, dislikes sports)
//!    - Recent interactions (viewed jazz events)
//!    - Location preference (downtown)
//!
//! 3. Send to LLM (Gemini) with context
//!    - System prompt (how to behave)
//!    - User profile (personalization)
//!    - Available tools (search_events, etc.)
//!    - User message
//!
//! 4. LLM decides what to do
//!    - May call search_events(category="music", date="this weekend")
//!    - May ask clarifying questions
//!    - May respond directly if no search needed
//!
//! 5. Execute any tool calls
//!    - Run the actual database queries
//!    - Return results to LLM
//!
//! 6. LLM formats final response
//!    "I found 3 concerts this weekend! Here's what's happening..."
//!
//! 7. Return response to user
//!    { "reply": "I found 3 concerts...", "events": [...] }
//! ```
//!
//! ## Request Format
//! ```json
//! {
//!   "message": "What's happening this weekend?",
//!   "user_id": "94c99eb0-21f3-4f7e-afee-f533b964a2d4"  // Optional
//! }
//! ```
//!
//! ## Response Format
//! ```json
//! {
//!   "reply": "I found 3 great events this weekend! 🎵\n\n**Friday:**\n- Jazz Night at Blue Note (8 PM)...",
//!   "events": [
//!     {
//!       "id": "...",
//!       "title": "Jazz Night at Blue Note",
//!       "start_time": "2026-01-24T20:00:00Z",
//!       ...
//!     }
//!   ]
//! }
//! ```
//!
//! ## Personalization
//! If `user_id` is provided, the response will be personalized:
//! - Events matching liked categories are highlighted
//! - Events in disliked categories are deprioritized
//! - User's location preference is considered
//! - Recent activity informs recommendations
//!
//! ## Example Interactions
//!
//! ### Simple Query
//! ```text
//! User: "What's happening tonight?"
//! Bot: "Here's what's happening in Tulsa tonight:
//!       - Jazz at the Blue Note (8 PM) - Live music downtown
//!       - Trivia Night at McNellie's (7 PM) - Test your knowledge!
//!       - Late Night Comedy (10 PM) - Stand-up at the Loony Bin"
//! ```
//!
//! ### Personalized Query
//! ```text
//! User (who likes music, dislikes sports): "What should I do this weekend?"
//! Bot: "Based on your interests, here are my top picks:
//!       🎵 Friday: Jazz Night at Blue Note - Right up your alley!
//!       🍔 Saturday: Food Truck Festival - Great variety downtown
//!       I noticed there's also a basketball game, but I know that's
//!       not really your thing. Want more music recommendations?"
//! ```
//!
//! ### Clarifying Question
//! ```text
//! User: "Find me something fun"
//! Bot: "I'd love to help! To give you the best recommendations:
//!       - Are you looking for something today or this weekend?
//!       - Any particular vibe? (Chill, energetic, family-friendly)
//!       - Indoor or outdoor?"
//! ```
//!
//! ## Implementation Status
//! 🚧 **NOT YET IMPLEMENTED** - Ben to build this out
//!
//! ## Dependencies
//! - `services::llm` - LLM integration functions
//! - `models::Event` - Event data structure
//! - `models::UserProfile` - User preferences and history

// =============================================================================
// IMPORTS (uncomment when implementing)
// =============================================================================

// use axum::{
//     extract::State,
//     http::StatusCode,
//     routing::post,
//     Json, Router,
// };
// use serde::{Deserialize, Serialize};
// use sqlx::PgPool;
// use uuid::Uuid;
//
// use crate::models::Event;
// use crate::services::llm;

// =============================================================================
// REQUEST/RESPONSE TYPES
// =============================================================================

// /// Incoming chat request from the frontend.
// ///
// /// # Fields
// /// - `message`: The user's natural language query (required)
// /// - `user_id`: User's UUID for personalization (optional)
// ///
// /// # Example
// /// ```json
// /// {
// ///   "message": "What concerts are happening this weekend?",
// ///   "user_id": "94c99eb0-21f3-4f7e-afee-f533b964a2d4"
// /// }
// /// ```
// #[derive(Deserialize)]
// pub struct ChatRequest {
//     /// The user's natural language message
//     pub message: String,
//
//     /// Optional user ID for personalized recommendations
//     /// If provided, we fetch their profile and use it for context
//     pub user_id: Option<Uuid>,
// }

// /// Response from the chat endpoint.
// ///
// /// # Fields
// /// - `reply`: The conversational response from the LLM
// /// - `events`: Array of events that match the query (may be empty)
// ///
// /// # Why Both?
// /// - `reply` is for display in the chat UI
// /// - `events` allows the frontend to render event cards/links
// ///
// /// # Example
// /// ```json
// /// {
// ///   "reply": "I found 3 concerts this weekend! 🎵\n\n1. Jazz Night...",
// ///   "events": [
// ///     { "id": "...", "title": "Jazz Night", ... },
// ///     { "id": "...", "title": "Rock Festival", ... }
// ///   ]
// /// }
// /// ```
// #[derive(Serialize)]
// pub struct ChatResponse {
//     /// Conversational reply from the LLM
//     pub reply: String,
//
//     /// Events matching the query (for frontend to display as cards)
//     pub events: Vec<Event>,
// }

// =============================================================================
// ROUTE DEFINITIONS
// =============================================================================

// /// Creates the router for chat endpoints.
// ///
// /// # Routes
// /// - `POST /` -> `chat()` - Process a chat message
// ///
// /// # Future Routes
// /// - `GET /history` - Get chat history for a user
// /// - `DELETE /history` - Clear chat history
// pub fn routes() -> Router<PgPool> {
//     Router::new()
//         .route("/", post(chat))
// }

// =============================================================================
// HANDLER: CHAT
// =============================================================================

// /// Processes a natural language chat message and returns event recommendations.
// ///
// /// # Endpoint
// /// `POST /api/chat`
// ///
// /// # Request Body
// /// ```json
// /// {
// ///   "message": "What's happening this weekend?",
// ///   "user_id": "94c99eb0-..."  // optional
// /// }
// /// ```
// ///
// /// # Returns
// /// - `200 OK` with ChatResponse containing reply and events
// /// - `500 Internal Server Error` if LLM or database fails
// ///
// /// # Implementation Steps
// /// 1. Extract user profile if user_id provided
// /// 2. Call LLM service with message and context
// /// 3. Return formatted response with matching events
// async fn chat(
//     State(pool): State<PgPool>,
//     Json(payload): Json<ChatRequest>,
// ) -> Result<Json<ChatResponse>, StatusCode> {
//
//     // Step 1: Fetch user profile for personalization (if user_id provided)
//     let user_profile = if let Some(user_id) = payload.user_id {
//         // Fetch profile using existing endpoint logic
//         // This gives us preferences and recent interactions
//         fetch_user_profile(&pool, user_id).await.ok()
//     } else {
//         None
//     };
//
//     // Step 2: Process the message with LLM
//     // This handles the full conversation loop:
//     // - Sending to Gemini
//     // - Executing any tool calls (searches)
//     // - Formatting the response
//     let (reply, events) = llm::process_chat_message(
//         payload.user_id.unwrap_or_default(),
//         &payload.message,
//         &pool,
//     )
//     .await
//     .map_err(|e| {
//         eprintln!("LLM error: {}", e);
//         StatusCode::INTERNAL_SERVER_ERROR
//     })?;
//
//     // Step 3: Return the response
//     Ok(Json(ChatResponse { reply, events }))
// }

// /// Helper function to fetch user profile for personalization.
// async fn fetch_user_profile(
//     pool: &PgPool,
//     user_id: Uuid,
// ) -> Result<crate::models::UserProfile, sqlx::Error> {
//     // Reuse the profile query logic from users.rs
//     // This is a simplified version - in production, consider
//     // extracting this to a shared service
//
//     let user = sqlx::query_as::<_, crate::models::User>(
//         "SELECT id, email, name, location_preference, created_at FROM users WHERE id = $1"
//     )
//     .bind(user_id)
//     .fetch_one(pool)
//     .await?;
//
//     let preferences = sqlx::query_as::<_, crate::models::UserPreference>(
//         "SELECT id, user_id, category, weight, created_at FROM user_preferences WHERE user_id = $1"
//     )
//     .bind(user_id)
//     .fetch_all(pool)
//     .await?;
//
//     let recent_interactions = sqlx::query_as::<_, crate::models::UserInteractionWithEvent>(
//         r#"
//         SELECT ui.interaction_type, e.title as event_title, e.category as event_category, ui.created_at
//         FROM user_interactions ui
//         JOIN events e ON ui.event_id = e.id
//         WHERE ui.user_id = $1
//         ORDER BY ui.created_at DESC
//         LIMIT 20
//         "#
//     )
//     .bind(user_id)
//     .fetch_all(pool)
//     .await?;
//
//     Ok(crate::models::UserProfile {
//         user,
//         preferences,
//         recent_interactions,
//     })
// }

// =============================================================================
// PLACEHOLDER - Ben to implement
// =============================================================================

// When ready to implement:
// 1. Uncomment the imports and types above
// 2. Uncomment the routes() function
// 3. Uncomment the chat() handler
// 4. Implement the LLM service functions in services/llm.rs
// 5. Uncomment the route registration in routes/mod.rs:
//    .nest("/chat", chat::routes())
// 6. Test with:
//    curl -X POST http://localhost:3000/api/chat \
//      -H "Content-Type: application/json" \
//      -d '{"message": "What events are happening this weekend?"}'
