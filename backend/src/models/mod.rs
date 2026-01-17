use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

// ============ EVENTS ============

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct Event {
    pub id: Uuid,
    pub title: String,
    pub description: Option<String>,
    pub location: Option<String>,
    pub venue: Option<String>,
    pub source_url: String,
    pub start_time: DateTime<Utc>,
    pub end_time: Option<DateTime<Utc>>,
    pub category: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateEvent {
    pub title: String,
    pub description: Option<String>,
    pub location: Option<String>,
    pub venue: Option<String>,
    pub source_url: String,
    pub start_time: DateTime<Utc>,
    pub end_time: Option<DateTime<Utc>>,
    pub category: Option<String>,
}

// ============ USERS ============

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct User {
    pub id: Uuid,
    pub email: String,
    pub name: Option<String>,
    pub location_preference: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateUser {
    pub email: String,
    pub name: Option<String>,
    pub location_preference: Option<String>,
}

// ============ USER PREFERENCES ============

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct UserPreference {
    pub id: Uuid,
    pub user_id: Uuid,
    pub category: String,
    pub weight: i32,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateUserPreference {
    pub category: String,
    pub weight: i32,
}

// ============ USER INTERACTIONS ============

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct UserInteraction {
    pub id: Uuid,
    pub user_id: Uuid,
    pub event_id: Uuid,
    pub interaction_type: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateUserInteraction {
    pub event_id: Uuid,
    pub interaction_type: String,
}

// ============ USER PROFILE (for LLM context) ============

#[derive(Debug, Serialize)]
pub struct UserProfile {
    pub user: User,
    pub preferences: Vec<UserPreference>,
    pub recent_interactions: Vec<UserInteractionWithEvent>,
}

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct UserInteractionWithEvent {
    pub interaction_type: String,
    pub event_title: String,
    pub event_category: Option<String>,
    pub created_at: DateTime<Utc>,
}