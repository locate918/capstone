//! # Locate918 Backend - Main Entry Point
//!
//! This is the main entry point for the Locate918 API server.
//! It initializes the database connection, runs migrations, sets up
//! CORS (Cross-Origin Resource Sharing), and starts the HTTP server.
//!
//! ## Architecture Overview
//! - Framework: Axum (async web framework for Rust)
//! - Database: PostgreSQL (via SQLx)
//! - Runtime: Tokio (async runtime)

// =============================================================================
// MODULE DECLARATIONS
// =============================================================================
// These declare submodules that contain different parts of our application.
// Each module is a separate file or folder in the src/ directory.

mod db;          // Database utilities (future: connection helpers, queries)
mod models;      // Data structures (Event, User, UserPreference, etc.)
mod routes;      // API endpoint handlers (events, users, chat)
mod scraper;     // Web scraping for event data (Skylar's domain)


// =============================================================================
// IMPORTS
// =============================================================================

use axum::Router;                         // Axum's router for defining API routes
use sqlx::postgres::PgPoolOptions;        // PostgreSQL connection pool configuration
use std::net::SocketAddr;                 // IP address + port representation
use tower_http::cors::{Any, CorsLayer};   // CORS middleware for cross-origin requests

// =============================================================================
// MAIN FUNCTION
// =============================================================================

/// The main entry point for our application.
///
/// #[tokio::main] is a macro that sets up the Tokio async runtime.
/// This allows us to use async/await throughout our application.
///
/// Returns Result<(), Box<dyn std::error::Error>> which means:
/// - Ok(()) on success (empty tuple = nothing to return)
/// - Err(...) on failure (any error type that implements std::error::Error)
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {

    // -------------------------------------------------------------------------
    // STEP 1: Load Environment Variables
    // -------------------------------------------------------------------------
    // dotenvy loads variables from the .env file into the environment.
    // .ok() ignores errors (if .env doesn't exist, we continue anyway).
    // This is where DATABASE_URL and other secrets are stored.
    dotenvy::dotenv().ok();

    // -------------------------------------------------------------------------
    // STEP 2: Get Database URL
    // -------------------------------------------------------------------------
    // Read DATABASE_URL from environment variables.
    // .expect() will panic with this message if the variable isn't set.
    // Example: "postgres://postgres:password@localhost:5432/locate918"
    let database_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must be set");

    // -------------------------------------------------------------------------
    // STEP 3: Create Database Connection Pool
    // -------------------------------------------------------------------------
    // A connection pool maintains multiple database connections that can be
    // reused across requests. This is more efficient than creating a new
    // connection for each request.
    // 
    // max_connections(5) = keep up to 5 connections open at once
    // .connect() = actually establish the connection (async, so we await it)
    // ? = if this fails, return the error immediately
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    // -------------------------------------------------------------------------
    // STEP 4: Run Database Migrations
    // -------------------------------------------------------------------------
    // Migrations are SQL scripts that set up or modify the database schema.
    // sqlx::migrate!() is a macro that embeds migration files at compile time.
    // It looks in ./migrations folder for .sql files and runs them in order.
    // This ensures the database schema matches what our code expects.
    sqlx::migrate!("./migrations").run(&pool).await?;

    // -------------------------------------------------------------------------
    // STEP 5: Configure CORS (Cross-Origin Resource Sharing)
    // -------------------------------------------------------------------------
    // CORS controls which websites can make requests to our API.
    // For development, we allow everything (Any). In production, you'd
    // restrict this to only your frontend's domain.
    //
    // - allow_origin(Any): Accept requests from any website
    // - allow_methods(Any): Accept any HTTP method (GET, POST, PUT, DELETE, etc.)
    // - allow_headers(Any): Accept any HTTP headers
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // -------------------------------------------------------------------------
    // STEP 6: Build the Application Router
    // -------------------------------------------------------------------------
    // Router is Axum's way of mapping URLs to handler functions.
    //
    // .nest("/api", routes::create_routes())
    //   - All routes from create_routes() will be prefixed with /api
    //   - Example: /events becomes /api/events
    //
    // .layer(cors)
    //   - Apply the CORS middleware to all routes
    //
    // .with_state(pool)
    //   - Make the database pool available to all route handlers
    //   - Handlers can then use State<PgPool> to access the database
    let app = Router::new()
        .nest("/api", routes::create_routes())
        .layer(cors)
        .with_state(pool);

    // -------------------------------------------------------------------------
    // STEP 7: Define Server Address
    // -------------------------------------------------------------------------
    // SocketAddr combines an IP address and port number.
    // [127, 0, 0, 1] = localhost (only accessible from this machine)
    // 3000 = port number
    // 
    // To make it accessible from other machines, use [0, 0, 0, 0]
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    println!("Server running on http://{}", addr);

    // -------------------------------------------------------------------------
    // STEP 8: Start the Server
    // -------------------------------------------------------------------------
    // TcpListener binds to the address and listens for incoming connections.
    // axum::serve() starts handling requests using our app router.
    // .await? blocks until the server shuts down (or errors).
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    // If we get here, the server shut down cleanly
    Ok(())
}