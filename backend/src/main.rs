//! # Locate918 Backend - Main Entry Point
//!
//! Initializes the database connection, runs migrations, sets up
//! CORS (Cross-Origin Resource Sharing), and starts the HTTP server.

// =============================================================================
// MODULE DECLARATIONS
// =============================================================================

mod auth;        // JWT authentication (Supabase Auth integration)
mod db;          // Database utilities
mod models;      // Data structures (Event, User, UserPreference, etc.)
mod routes;      // API endpoint handlers (events, users, chat)

// =============================================================================
// IMPORTS
// =============================================================================

use axum::http::header;
use axum::Router;
use sqlx::postgres::PgPoolOptions;
use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};

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
    let database_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must be set");

    // STEP 3: Create Database Connection Pool
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    // STEP 4: Run Database Migrations
    sqlx::migrate!("./migrations").run(&pool).await?;

    // STEP 5: Configure CORS
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers([
            header::CONTENT_TYPE,
            header::AUTHORIZATION,
        ]);

    // STEP 6: Build the Application Router
    let app = Router::new()
        .nest("/api", routes::create_routes())
        .layer(cors)
        .with_state(pool);

    // STEP 7: Define Server Address
    /* let port: u16 = std::env::var("PORT")
       .unwrap_or_else(|_| "3000".to_string())
        .parse()
       .expect("PORT must be a number");
     let addr = SocketAddr::from(([0, 0, 0, 0], port)); */
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    println!("Server running on http://{}", addr);

    // STEP 8: Start the Server
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}