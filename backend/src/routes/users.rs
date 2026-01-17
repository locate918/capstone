use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{
    CreateUser, CreateUserInteraction, CreateUserPreference,
    User, UserPreference, UserInteraction, UserProfile, UserInteractionWithEvent,
};

pub fn routes() -> Router<PgPool> {
    Router::new()
        .route("/", post(create_user))
        .route("/:id", get(get_user))
        .route("/:id/profile", get(get_user_profile))
        .route("/:id/preferences", get(get_preferences).post(add_preference))
        .route("/:id/interactions", get(get_interactions).post(add_interaction))
}

async fn create_user(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateUser>,
) -> Result<(StatusCode, Json<User>), StatusCode> {
    let id = Uuid::new_v4();
    let created_at = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO users (id, email, name, location_preference, created_at)
        VALUES ($1, $2, $3, $4, $5)
        "#,
    )
        .bind(&id)
        .bind(&payload.email)
        .bind(&payload.name)
        .bind(&payload.location_preference)
        .bind(&created_at)
        .execute(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let user = User {
        id,
        email: payload.email,
        name: payload.name,
        location_preference: payload.location_preference,
        created_at,
    };

    Ok((StatusCode::CREATED, Json(user)))
}

async fn get_user(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<User>, StatusCode> {
    let user = sqlx::query_as::<_, User>(
        "SELECT id, email, name, location_preference, created_at FROM users WHERE id = $1"
    )
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    match user {
        Some(u) => Ok(Json(u)),
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn get_user_profile(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<UserProfile>, StatusCode> {
    let user = sqlx::query_as::<_, User>(
        "SELECT id, email, name, location_preference, created_at FROM users WHERE id = $1"
    )
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    let preferences = sqlx::query_as::<_, UserPreference>(
        "SELECT id, user_id, category, weight, created_at FROM user_preferences WHERE user_id = $1"
    )
        .bind(id)
        .fetch_all(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let recent_interactions = sqlx::query_as::<_, UserInteractionWithEvent>(
        r#"
        SELECT ui.interaction_type, e.title as event_title, e.category as event_category, ui.created_at
        FROM user_interactions ui
        JOIN events e ON ui.event_id = e.id
        WHERE ui.user_id = $1
        ORDER BY ui.created_at DESC
        LIMIT 20
        "#
    )
        .bind(id)
        .fetch_all(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(UserProfile {
        user,
        preferences,
        recent_interactions,
    }))
}

async fn get_preferences(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<UserPreference>>, StatusCode> {
    let preferences = sqlx::query_as::<_, UserPreference>(
        "SELECT id, user_id, category, weight, created_at FROM user_preferences WHERE user_id = $1"
    )
        .bind(id)
        .fetch_all(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(preferences))
}

async fn add_preference(
    State(pool): State<PgPool>,
    Path(user_id): Path<Uuid>,
    Json(payload): Json<CreateUserPreference>,
) -> Result<(StatusCode, Json<UserPreference>), StatusCode> {
    let id = Uuid::new_v4();
    let created_at = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO user_preferences (id, user_id, category, weight, created_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, category) DO UPDATE SET weight = $4
        "#,
    )
        .bind(&id)
        .bind(&user_id)
        .bind(&payload.category)
        .bind(&payload.weight)
        .bind(&created_at)
        .execute(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let preference = UserPreference {
        id,
        user_id,
        category: payload.category,
        weight: payload.weight,
        created_at,
    };

    Ok((StatusCode::CREATED, Json(preference)))
}

async fn get_interactions(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<UserInteraction>>, StatusCode> {
    let interactions = sqlx::query_as::<_, UserInteraction>(
        "SELECT id, user_id, event_id, interaction_type, created_at FROM user_interactions WHERE user_id = $1 ORDER BY created_at DESC"
    )
        .bind(id)
        .fetch_all(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(interactions))
}

async fn add_interaction(
    State(pool): State<PgPool>,
    Path(user_id): Path<Uuid>,
    Json(payload): Json<CreateUserInteraction>,
) -> Result<(StatusCode, Json<UserInteraction>), StatusCode> {
    let id = Uuid::new_v4();
    let created_at = chrono::Utc::now();

    sqlx::query(
        r#"
        INSERT INTO user_interactions (id, user_id, event_id, interaction_type, created_at)
        VALUES ($1, $2, $3, $4, $5)
        "#,
    )
        .bind(&id)
        .bind(&user_id)
        .bind(&payload.event_id)
        .bind(&payload.interaction_type)
        .bind(&created_at)
        .execute(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let interaction = UserInteraction {
        id,
        user_id,
        event_id: payload.event_id,
        interaction_type: payload.interaction_type,
        created_at,
    };

    Ok((StatusCode::CREATED, Json(interaction)))
}