<p align="center">
  <img src="./Locate918.png" alt="Locate918" width="360">
</p>

# Locate918

An AI-powered event aggregator for the Tulsa (918) area that pulls from multiple public sources, uses an LLM to normalize and summarize event information, and matches users to events through natural language preferences.

Live site: **https://locate918.com**

## Current Status

The site is deployed and publicly accessible, with the frontend, backend, LLM service, and Supabase-backed data layer all running in production.

The product is currently positioned as an **open beta**. Event details are aggregated from multiple public sources, so users should still verify final timing and venue details with the original organizer before attending.

## What the Site Does Today

- Aggregates upcoming Tulsa-area events from multiple public sources into one searchable experience
- Supports **natural-language Smart Search** for queries like `jazz this weekend` or `cheap family events`
- Includes **Tully**, a streaming AI assistant for conversational event discovery
- Shows events in both a **card feed** and an **interactive map**
- Uses **map clustering** and hover-to-highlight behavior to connect the list and the map
- Lets users browse by **This Week**, **All Events**, **Saved Events**, **Recommended**, and **By Venue**
- Supports **date-range filtering** and venue-specific browsing
- Uses **Supabase Auth** for sign up, sign in, and Google OAuth
- Includes a multi-step **onboarding flow** that captures user interests, location, travel radius, budget, and family-friendly preferences
- Generates **personalized recommendations** from saved preferences and interaction history
- Lets signed-in users **save and unsave events**
- Tracks user interactions to continuously update category preference weights
- Lets users edit their profile preferences after onboarding
- Enriches events with **venue websites**, **venue priority**, and **map coordinates** when available
- Suppresses low-trust aggregator links in the UI and prefers direct venue/canonical links when possible
- Supports place-aware chat tooling for nearby recommendations beyond events

## Recently Added / Expanded Features

Compared with the earlier project phase, the app now includes several shipped features that were not reflected in the old README:

- **Production deployment** on `locate918.com`
- **Authentication and user accounts** with Supabase
- **Saved events** and bookmark management
- **Personalized recommendations** powered by onboarding preferences and interaction scoring
- **Profile editing** for location, radius, budget, and family-friendly settings
- **Venue-first browsing** with venue selection and event counts
- **Interactive map clustering** with category-colored pins
- **Streaming AI chat responses** from Tully
- **Production CI/CD checks and health-check-based deployment flow**

## Architecture

```text
Users
  |
  +-- Frontend: React app
  |     - deployed at locate918.com
  |
  +-- Rust API (Axum)
  |     - event, user, venue, saved-event, and recommendation endpoints
  |
  +-- Python LLM Service (FastAPI + Gemini)
  |     - smart search, chat, normalization, interaction scoring
  |
  +-- Supabase
        - PostgreSQL data store
        - authentication
```

## Tech Stack

| Layer | Tech |
| --- | --- |
| Frontend | React, Tailwind CSS, Leaflet, Supabase JS |
| Backend API | Rust, Axum, SQLx, PostgreSQL |
| AI Service | Python, FastAPI, Gemini |
| Data | Supabase PostgreSQL + Supabase Auth |
| Mapping | Leaflet + marker clustering |
| Scraping | Python scraper tooling with Playwright/Flask |
| Deployment | Vercel, Railway, Supabase |

## Repo Layout

```text
capstone/
|-- frontend/       React client
|-- backend/        Rust API
|-- llm-service/    FastAPI service for search/chat/normalization
|-- docs/           design notes, team docs, architecture docs
|-- Deployment.md   deployment notes
`-- README.md
```

## Running Locally

### Prerequisites

- Node.js 18+
- Rust
- Python 3.11+
- Access to the shared Supabase project secrets
- Gemini API key for the LLM service

### 1. Start the Rust backend

```bash
cd backend
cp .env.example .env
cargo run
```

Expected local URL: `http://localhost:3000`

### 2. Start the LLM service

```bash
cd llm-service
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8001
```

Expected local URL: `http://localhost:8001`

### 3. Start the frontend

```bash
cd frontend
npm install
cp .env.example .env
npm start
```

Expected local URL: `http://localhost:5173`

## Scraper Tool Guide

The Universal Scraper is a Flask web app that extracts events from any website using 18 different strategies.

### Setup

```bash
cd backend/src/scraper

python -m venv venv
.\venv\Scripts\Activate

# Install dependencies
pip install flask playwright httpx beautifulsoup4 python-dateutil python-dotenv

# Install browser for Playwright
playwright install chromium

# Run the scraper
python ScraperTool.py
```

**Open:** http://localhost:5000

**Note:** The scraper runs automatically using cron scheduler on Railway. The scraper itself can be accessed on **admin.locate918.com**.
Only the password is needed to access and can be found in Railway labeled ADMIN_PASSWORD.

## Environment Variables

### `backend/.env`

```env
DATABASE_URL=postgresql://...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=...
LLM_SERVICE_URL=http://localhost:8001
```

### `llm-service/.env`

```env
GEMINI_API_KEY=...
BACKEND_URL=http://localhost:3000
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=...
```

`SUPABASE_URL` and `SUPABASE_KEY` are used by the place-aware chat tools and may be omitted if that workflow is not being used locally.

### `frontend/.env`

```env
REACT_APP_BACKEND_URL=http://localhost:3000
REACT_APP_LLM_SERVICE_URL=http://localhost:8001
REACT_APP_SUPABASE_URL=https://<project>.supabase.co
REACT_APP_SUPABASE_ANON_KEY=...
REACT_APP_USE_MOCKS=false
```

## Key API Surface

### Rust backend

- `GET /api/events`
- `GET /api/events/search`
- `GET /api/events/:id`
- `GET /api/users/me`
- `GET /api/users/me/profile`
- `GET/POST/PUT /api/users/me/preferences`
- `GET/POST /api/users/me/interactions`
- `GET/POST/DELETE /api/users/me/saved-events`
- `GET /api/users/me/recommendations`
- `GET /api/venues`

### LLM service

- `GET /health`
- `POST /api/search`
- `POST /api/chat`
- `POST /api/normalize`
- `POST /api/interactions`

## Deployment

The current production stack is set up around:

- **Frontend** on Vercel
- **Rust backend** on Railway
- **LLM service** on Railway
- **Database and auth** on Supabase

The repo also includes:

- `frontend/vercel.json`
- `backend/Dockerfile`
- `llm-service/Dockerfile`
- GitHub Actions workflows under `.github/workflows/`

## Notes

- The app favors direct venue or canonical links over aggregator pages when possible.
- Venue coordinates are used for mapping when available; events without coordinates still appear in list results.
- Personalized recommendations depend on onboarding completion and accumulated preference weights.

---

## Team Roles

| Name | Role | Responsibilities |
|------|------|------------------|
| **Will** | Coordinator / Backend Lead | Rust backend, database, scraper tool, code review |
| **Ben** | AI Engineer | Python LLM service, Gemini integration, `/api/search` + `/api/chat` |
| **Skylar** | Data Engineer | Running scrapers, finding event sources, data quality |
| **Malachi** | Frontend Developer | React UI, search + chat interface |
| **Jordi** | Fullstack Developer | Cross-stack support, integration |

## Troubleshooting

### "PoolTimedOut" or connection errors
- Check `DATABASE_URL` in `.env` — password correct? No extra spaces?
- Make sure you're using the Supabase URL, not localhost

### "CORS error" in browser
- Backend running on port 3000?
- Frontend `.env` has `REACT_APP_BACKEND_URL=http://localhost:3000`?

### Frontend shows no events
1. Is backend running? Check http://localhost:3000/api/events
2. Check browser console (F12) for errors

### Scraper can't save to database
- Is backend running on port 3000?
- Check the scraper console for error messages

### Port already in use
```bash
# Windows - find what's using port 3000
netstat -ano | findstr :3000
taskkill /PID <pid> /F
```

---

## Database Access

**View events via API:**
```bash
curl http://localhost:3000/api/events?limit=10
```

**Count events (PowerShell):**
```powershell
((Invoke-WebRequest "http://localhost:3000/api/events?limit=1000").Content | ConvertFrom-Json).Count
```

**Supabase Dashboard:** Ask Will for access to view/edit data directly.

---

## Questions?

- **Backend/Database/Scraper:** Ask Will
- **AI/LLM Service:** Ask Ben
- **Data Sources:** Ask Skylar
- **Frontend:** Ask Malachi or Jordi

Let's build something great! 🚀