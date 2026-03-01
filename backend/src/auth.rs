//! # Authentication Module
//!
//! Validates Supabase JWTs by calling Supabase's auth endpoint.
//!
//! ## How It Works
//! 1. Frontend signs in via Supabase Auth (email/password or Google OAuth)
//! 2. Frontend sends the JWT in `Authorization: Bearer <token>` header
//! 3. This module sends the token to Supabase's `/auth/v1/user` endpoint
//! 4. Supabase validates the token and returns the user info
//! 5. We extract the user UUID and make it available via the `AuthUser` extractor
//!
//! ## Why This Approach?
//! Supabase migrated to ES256 (ECC P-256) signing keys. Rather than managing
//! public keys and crypto locally, we let Supabase validate its own tokens.
//! The small latency cost is negligible for our use case.
//!
//! ## Usage in Handlers
//! ```rust
//! // Required auth - returns 401 if no valid token
//! async fn my_handler(auth: AuthUser) -> impl IntoResponse {
//!     let user_id = auth.user_id;
//!     // ...
//! }
//!
//! // Optional auth - works for both logged-in and anonymous users
//! async fn public_handler(auth: OptionalAuthUser) -> impl IntoResponse {
//!     if let Some(user_id) = auth.user_id {
//!         // personalized response
//!     } else {
//!         // anonymous response
//!     }
//! }
//! ```
//!
//! ## Environment Variables
//! ```text
//! SUPABASE_URL=https://kpihjwzqtwqlschmtekx.supabase.co
//! SUPABASE_ANON_KEY=eyJhbGciOiJI...  (the public anon key)
//! ```
//!
//! ## Owner
//! Will (Coordinator/Backend Lead)

use axum::{
    async_trait,
    extract::FromRequestParts,
    http::{header, request::Parts, StatusCode},
};
use serde::Deserialize;
use uuid::Uuid;

// =============================================================================
// SUPABASE USER RESPONSE
// =============================================================================

/// The user object returned by Supabase's `/auth/v1/user` endpoint.
/// We only need the `id` field.
#[derive(Debug, Deserialize)]
struct SupabaseUser {
    id: Uuid,
}

// =============================================================================
// AUTH EXTRACTOR (Required)
// =============================================================================

/// Extracts and validates the authenticated user via Supabase's auth API.
///
/// Returns `401 Unauthorized` if:
/// - No `Authorization` header present
/// - Header doesn't start with `Bearer `
/// - Token is invalid, expired, or revoked
///
/// Returns `500 Internal Server Error` if:
/// - `SUPABASE_URL` environment variable is not set
/// - Supabase auth endpoint is unreachable
#[derive(Debug, Clone)]
pub struct AuthUser {
    /// The authenticated user's UUID (matches auth.users.id and public.users.id)
    pub user_id: Uuid,
}

#[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for AuthUser {
    type Rejection = StatusCode;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        // 1. Extract the Authorization header
        let auth_header = parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|v| v.to_str().ok())
            .ok_or(StatusCode::UNAUTHORIZED)?;

        // 2. Strip "Bearer " prefix
        let token = auth_header
            .strip_prefix("Bearer ")
            .ok_or(StatusCode::UNAUTHORIZED)?;

        // 3. Validate via Supabase
        let user_id = validate_with_supabase(token).await?;

        Ok(AuthUser { user_id })
    }
}

// =============================================================================
// AUTH EXTRACTOR (Optional)
// =============================================================================

/// Like `AuthUser`, but doesn't reject the request if no token is present.
///
/// Use this for endpoints that work for both anonymous and authenticated users
/// (e.g., chat that optionally personalizes if logged in).
#[derive(Debug, Clone)]
pub struct OptionalAuthUser {
    /// The user's UUID, or None if not authenticated
    pub user_id: Option<Uuid>,
}

#[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for OptionalAuthUser {
    type Rejection = StatusCode;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let user_id = match parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|v| v.to_str().ok())
            .and_then(|h| h.strip_prefix("Bearer "))
        {
            Some(token) => validate_with_supabase(token).await.ok(),
            None => None,
        };

        Ok(OptionalAuthUser { user_id })
    }
}

// =============================================================================
// SUPABASE TOKEN VALIDATION
// =============================================================================

/// Validates a Supabase JWT by calling the Supabase auth API.
///
/// Sends the token to `SUPABASE_URL/auth/v1/user` which returns the
/// authenticated user if the token is valid, or an error if not.
async fn validate_with_supabase(token: &str) -> Result<Uuid, StatusCode> {
    let supabase_url = std::env::var("SUPABASE_URL").map_err(|_| {
        eprintln!("SUPABASE_URL not set in environment");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let anon_key = std::env::var("SUPABASE_ANON_KEY").map_err(|_| {
        eprintln!("SUPABASE_ANON_KEY not set in environment");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/auth/v1/user", supabase_url))
        .header("Authorization", format!("Bearer {}", token))
        .header("apikey", anon_key)
        .send()
        .await
        .map_err(|e| {
            eprintln!("Supabase auth request failed: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    if !response.status().is_success() {
        eprintln!("Supabase token validation failed: {}", response.status());
        return Err(StatusCode::UNAUTHORIZED);
    }

    let user: SupabaseUser = response.json().await.map_err(|e| {
        eprintln!("Failed to parse Supabase user response: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(user.id)
}