//! # Locate918 Backend - Main Entry Point
//!
//! Initializes the database connection, runs migrations, sets up
//! CORS (Cross-Origin Resource Sharing), and starts the HTTP server.

// =============================================================================
// MODULE DECLARATIONS
// =============================================================================

mod auth; // JWT authentication (Supabase Auth integration)
mod db; // Database utilities
mod models; // Data structures (Event, User, UserPreference, etc.)
mod routes; // API endpoint handlers (events, users, chat)

// =============================================================================
// IMPORTS
// =============================================================================

use axum::http::{header, HeaderValue, Method};
use axum::routing::get;
use axum::Json;
use axum::Router;
use serde::Serialize;
use sqlx::postgres::PgPoolOptions;
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;

#[derive(Serialize)]
struct ServiceMetadata {
    status: &'static str,
    service: &'static str,
    version: String,
    git_sha: String,
}

async fn health_check() -> Json<ServiceMetadata> {
    Json(ServiceMetadata {
        status: "ok",
        service: "backend",
        version: std::env::var("APP_VERSION")
            .unwrap_or_else(|_| env!("CARGO_PKG_VERSION").to_string()),
        git_sha: std::env::var("RAILWAY_GIT_COMMIT_SHA")
            .or_else(|_| std::env::var("GITHUB_SHA"))
            .unwrap_or_else(|_| "dev".to_string()),
    })
}

async fn version_check() -> Json<ServiceMetadata> {
    Json(ServiceMetadata {
        status: "ok",
        service: "backend",
        version: std::env::var("APP_VERSION")
            .unwrap_or_else(|_| env!("CARGO_PKG_VERSION").to_string()),
        git_sha: std::env::var("RAILWAY_GIT_COMMIT_SHA")
            .or_else(|_| std::env::var("GITHUB_SHA"))
            .unwrap_or_else(|_| "dev".to_string()),
    })
}

// =============================================================================
// MAIN FUNCTION
// =============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // STEP 1: Load Environment Variables
    dotenvy::dotenv().ok();

    // Verify auth config is present (warn, don't crash — events still work without it)
    if std::env::var("SUPABASE_URL").is_err() || std::env::var("SUPABASE_ANON_KEY").is_err() {
        eprintln!("⚠️  SUPABASE_URL or SUPABASE_ANON_KEY not set — authenticated user endpoints will return 500");
        eprintln!("   Set these in your .env file");
    }

    // STEP 2: Get Database URL
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    // STEP 3: Create Database Connection Pool
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    // STEP 4: Run Database Migrations
    //sqlx::migrate!("./migrations").run(&pool).await?;

    // STEP 5: Configure CORS
    // Allow both local dev and production frontend origins.
    let cors = CorsLayer::new()
        .allow_origin([
            "http://localhost:5173".parse::<HeaderValue>().unwrap(),
            "http://localhost:3001".parse::<HeaderValue>().unwrap(),
            "https://admin.locate918.com"
                .parse::<HeaderValue>()
                .unwrap(),
            "https://locate918.com".parse::<HeaderValue>().unwrap(),
            "https://www.locate918.com".parse::<HeaderValue>().unwrap(),
        ])
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PUT,
            Method::DELETE,
            Method::OPTIONS,
        ])
        .allow_headers([header::CONTENT_TYPE, header::AUTHORIZATION]);

    // STEP 6: Build the Application Router
    let app = Router::new()
        .route("/health", get(health_check))
        .route("/version", get(version_check))
        .nest("/api", routes::create_routes())
        .layer(cors)
        .with_state(pool);

    // STEP 7: Define Server Address
    // Read PORT from environment (Railway sets this automatically).
    // Bind to 0.0.0.0 so the container is reachable externally.
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "3000".to_string())
        .parse()
        .expect("PORT must be a number");
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!("Server running on http://{}", addr);

    // STEP 8: Start the Server
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn health_endpoint_returns_build_metadata() {
        let Json(payload) = health_check().await;
        assert_eq!(payload.status, "ok");
        assert_eq!(payload.service, "backend");
        assert_eq!(payload.version, env!("CARGO_PKG_VERSION").to_string());
        assert!(!payload.git_sha.is_empty());
    }

    #[tokio::test]
    async fn version_endpoint_returns_build_metadata() {
        let Json(payload) = version_check().await;
        assert_eq!(payload.status, "ok");
        assert_eq!(payload.service, "backend");
        assert_eq!(payload.version, env!("CARGO_PKG_VERSION").to_string());
        assert!(!payload.git_sha.is_empty());
    }
}
