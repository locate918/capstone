//! # LLM Integration Service
//!
//! This module handles communication with the Python LLM microservice
//! which powers natural language event discovery using Google Gemini.
//!
//! ## Owner
//! Ben (AI Engineer) - Python service implementation
//! Will (Backend Lead) - Rust client code
//!
//! ## Architecture
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                        Chat Request Flow                        │
//! └─────────────────────────────────────────────────────────────────┘
//!
//!  User: "Any concerts this weekend?"
//!           │
//!           ▼
//!  ┌─────────────────┐
//!  │  Rust Backend   │  POST /api/chat
//!  │  (routes/chat)  │
//!  └────────┬────────┘
//!           │ HTTP
//!           ▼
//!  ┌─────────────────┐     ┌─────────────────┐
//!  │  Python LLM     │────▶│  Gemini API     │
//!  │  Service :8001  │◀────│  (external)     │
//!  └────────┬────────┘     └─────────────────┘
//!           │
//!           │ Returns: SearchParams or formatted response
//!           ▼
//!  ┌─────────────────┐
//!  │  Rust Backend   │
//!  │  (search DB)    │
//!  └────────┬────────┘
//!           │
//!           ▼
//!  ┌─────────────────┐
//!  │  Response to    │
//!  │  User           │
//!  └─────────────────┘
//! ```
//!
//! ## Environment Variables
//! ```text
//! LLM_SERVICE_URL=http://localhost:8001
//! ```
//!
//! ## Endpoints Called
//! | Python Endpoint | Purpose |
//! |-----------------|---------|
//! | POST /api/parse-intent | Convert natural language → search params |
//! | POST /api/chat | Generate conversational response |
//! | GET /health | Health check |

use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::env;

use crate::models::Event;

// =============================================================================
// CONFIGURATION
// =============================================================================

/// Get the LLM service URL from environment or default to localhost
fn get_llm_service_url() -> String {
    env::var("LLM_SERVICE_URL").unwrap_or_else(|_| "http://localhost:8001".to_string())
}

// =============================================================================
// DATA STRUCTURES
// =============================================================================

/// Parameters extracted from user's natural language query.
///
/// The Python LLM service returns this after parsing a message like
/// "Any jazz concerts downtown this Friday?"
///
/// # Example
/// ```json
/// {
///   "query": "jazz",
///   "category": "concerts",
///   "location": "downtown",
///   "date_from": "2026-01-24",
///   "price_max": 30.0,
///   "outdoor": false,
///   "family_friendly": true
/// }
/// ```
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SearchParams {
    /// Text to search for in event titles/descriptions
    pub query: Option<String>,

    /// Category filter (e.g., "concerts", "sports", "family")
    pub category: Option<String>,

    /// Start of date range (YYYY-MM-DD)
    pub date_from: Option<String>,

    /// End of date range (YYYY-MM-DD)
    pub date_to: Option<String>,

    /// Location filter (e.g., "downtown", "Broken Arrow")
    pub location: Option<String>,

    /// Maximum price filter
    pub price_max: Option<f64>,

    /// Only outdoor events
    pub outdoor: Option<bool>,

    /// Only family-friendly events
    pub family_friendly: Option<bool>,
}

// -----------------------------------------------------------------------------
// Request/Response types for Python service communication
// -----------------------------------------------------------------------------

#[derive(Debug, Serialize)]
struct ParseIntentRequest {
    message: String,
}

#[derive(Debug, Deserialize)]
struct ParseIntentResponse {
    params: SearchParams,
    #[allow(dead_code)]
    confidence: f32,
}

#[derive(Debug, Serialize)]
struct ChatRequest {
    message: String,
    user_id: Option<uuid::Uuid>,
    #[serde(skip_serializing_if = "Option::is_none")]
    events: Option<Vec<Event>>,
}

#[derive(Debug, Deserialize)]
struct ChatResponse {
    reply: String,
    #[allow(dead_code)]
    events: Vec<Event>,
    #[allow(dead_code)]
    search_params: Option<SearchParams>,
}

// =============================================================================
// ERROR TYPE
// =============================================================================

/// Errors that can occur when communicating with the LLM service.
#[derive(Debug, thiserror::Error)]
pub enum LlmError {
    #[error("HTTP request failed: {0}")]
    HttpError(#[from] reqwest::Error),

    #[error("LLM service returned error: {0}")]
    ServiceError(String),

    #[error("LLM service unavailable")]
    ServiceUnavailable,
}

// =============================================================================
// LLM CLIENT
// =============================================================================

/// Client for communicating with the Python LLM service.
///
/// # Example
/// ```rust
/// let client = LlmClient::new();
///
/// // Check if service is running
/// if client.health_check().await? {
///     // Parse user's natural language query
///     let params = client.parse_intent("Any jazz concerts this weekend?").await?;
///     println!("Category: {:?}", params.category);
/// }
/// ```
pub struct LlmClient {
    client: Client,
    base_url: String,
}

impl LlmClient {
    /// Create a new LLM client.
    ///
    /// Reads `LLM_SERVICE_URL` from environment, defaults to `http://localhost:8001`.
    pub fn new() -> Self {
        Self {
            client: Client::new(),
            base_url: get_llm_service_url(),
        }
    }

    /// Check if the LLM service is healthy and ready to accept requests.
    ///
    /// # Returns
    /// - `Ok(true)` if service is healthy
    /// - `Ok(false)` if service responded but isn't ready
    /// - `Err(LlmError)` if service is unreachable
    pub async fn health_check(&self) -> Result<bool, LlmError> {
        let url = format!("{}/health", self.base_url);
        let response = self.client.get(&url).send().await?;
        Ok(response.status().is_success())
    }

    /// Parse a natural language query into structured search parameters.
    ///
    /// # Arguments
    /// * `message` - User's natural language query
    ///
    /// # Returns
    /// * `Ok(SearchParams)` - Extracted search parameters
    /// * `Err(LlmError)` - If the service call fails
    ///
    /// # Example
    /// ```rust
    /// let params = client.parse_intent("Any jazz concerts downtown this Friday?").await?;
    /// // params.category = Some("concerts")
    /// // params.query = Some("jazz")
    /// // params.location = Some("downtown")
    /// // params.date_from = Some("2026-01-24")
    /// ```
    pub async fn parse_intent(&self, message: &str) -> Result<SearchParams, LlmError> {
        let url = format!("{}/api/parse-intent", self.base_url);

        let request = ParseIntentRequest {
            message: message.to_string(),
        };

        let response = self.client.post(&url).json(&request).send().await?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(LlmError::ServiceError(error_text));
        }

        let parsed: ParseIntentResponse = response.json().await?;
        Ok(parsed.params)
    }

    /// Generate a conversational response about events.
    ///
    /// Called AFTER searching the database with params from `parse_intent`.
    ///
    /// # Arguments
    /// * `message` - Original user query
    /// * `events` - Events found in the database
    /// * `user_id` - Optional user ID for personalization
    ///
    /// # Returns
    /// * `Ok(String)` - Conversational response from the LLM
    /// * `Err(LlmError)` - If the service call fails
    pub async fn generate_response(
        &self,
        message: &str,
        events: Vec<Event>,
        user_id: Option<uuid::Uuid>,
    ) -> Result<String, LlmError> {
        let url = format!("{}/api/chat", self.base_url);

        let request = ChatRequest {
            message: message.to_string(),
            user_id,
            events: Some(events),
        };

        let response = self.client.post(&url).json(&request).send().await?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(LlmError::ServiceError(error_text));
        }

        let chat_response: ChatResponse = response.json().await?;
        Ok(chat_response.reply)
    }
}

impl Default for LlmClient {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// CONVENIENCE FUNCTIONS
// =============================================================================

/// Parses a natural language query into structured search parameters.
///
/// Convenience function that creates a client and calls `parse_intent`.
///
/// # Example
/// ```rust
/// let params = parse_user_intent("What's happening this weekend?").await?;
/// ```
pub async fn parse_user_intent(message: &str) -> Result<SearchParams, LlmError> {
    let client = LlmClient::new();
    client.parse_intent(message).await
}

/// Processes a chat message and returns a conversational response with events.
///
/// This is the main entry point called by `routes/chat.rs`.
///
/// # Flow
/// 1. Parse user intent to get search params
/// 2. Search database with those params
/// 3. Pass events to LLM for formatting
/// 4. Return conversational response + events
///
/// # Arguments
/// * `user_id` - User's UUID (for personalization)
/// * `message` - User's chat message
/// * `pool` - Database connection pool
///
/// # Returns
/// * `Ok((String, Vec<Event>))` - (LLM response, matching events)
/// * `Err(...)` - If any step fails
pub async fn process_chat_message(
    user_id: uuid::Uuid,
    message: &str,
    pool: &sqlx::PgPool,
) -> Result<(String, Vec<Event>), Box<dyn std::error::Error + Send + Sync>> {
    let client = LlmClient::new();

    // Step 1: Parse intent to get search parameters
    let params = client.parse_intent(message).await?;

    // Step 2: Search database with extracted parameters
    let events = search_events_with_params(&params, pool).await?;

    // Step 3: Generate conversational response
    let reply = client
        .generate_response(message, events.clone(), Some(user_id))
        .await?;

    Ok((reply, events))
}

// =============================================================================
// DATABASE QUERY HELPER
// =============================================================================

/// All columns to select from events table (matches Event struct)
const EVENT_COLUMNS: &str = r#"
    id, title, description, venue, venue_address, location,
    source_url, source_name, start_time, end_time, categories,
    price_min, price_max, outdoor, family_friendly, image_url,
    created_at, updated_at
"#;

/// Search events using the extracted parameters.
///
/// Builds a dynamic query based on which parameters are present.
/// Matches the logic in `routes/events.rs` search_events handler.
async fn search_events_with_params(
    params: &SearchParams,
    pool: &sqlx::PgPool,
) -> Result<Vec<Event>, sqlx::Error> {
    // Build dynamic WHERE conditions
    let mut conditions: Vec<String> = vec![];

    // Text search in title/description
    if let Some(ref q) = params.query {
        conditions.push(format!(
            "(title ILIKE '%{}%' OR description ILIKE '%{}%')",
            q.replace('\'', "''"),
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

    // Date range filters
    if let Some(ref date_from) = params.date_from {
        conditions.push(format!("start_time >= '{}'", date_from));
    } else {
        // Default: only future events
        conditions.push("start_time >= NOW()".to_string());
    }

    if let Some(ref date_to) = params.date_to {
        conditions.push(format!("start_time <= '{}'", date_to));
    }

    // Location filter
    if let Some(ref loc) = params.location {
        conditions.push(format!(
            "location ILIKE '%{}%'",
            loc.replace('\'', "''")
        ));
    }

    // Price filter
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

    // Build and execute query
    let query = format!(
        "SELECT {} FROM events {} ORDER BY start_time ASC LIMIT 20",
        EVENT_COLUMNS, where_clause
    );

    sqlx::query_as::<_, Event>(&query)
        .fetch_all(pool)
        .await
}