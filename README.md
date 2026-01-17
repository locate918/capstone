# Locate918 - Event Discovery Aggregator

An AI-powered event aggregator for the Tulsa (918) area that pulls from multiple public sources, uses an LLM to normalize and summarize event information, and matches users to events through natural language preferences.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Team Roles](#team-roles)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Database Setup](#database-setup)
  - [Rust Backend Setup](#rust-backend-setup)
  - [Python LLM Service Setup](#python-llm-service-setup)
  - [Frontend Setup](#frontend-setup)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Development Tasks by Role](#development-tasks-by-role)
- [Environment Variables](#environment-variables)
- [Running the Full Stack](#running-the-full-stack)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

**Problem:** Event discovery is fragmented. People miss events because information is scattered across multiple platforms (Eventbrite, Facebook, venue websites), each optimized for promoters rather than attendees.

**Solution:** A unified platform that:
1. Aggregates events from multiple public sources
2. Uses AI (Google Gemini) to normalize and summarize event data
3. Lets users search with natural language ("What's happening downtown this weekend?")
4. Links back to original sources, driving traffic to organizers

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOCATE918 ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ Eventbrite  │     │   Venue     │     │    City     │
    │    API      │     │  Websites   │     │  Calendars  │
    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   RUST BACKEND      │
                    │   (Axum) :3000      │
                    │                     │
                    │  • /api/events      │
                    │  • /api/users       │
                    │  • /api/chat        │
                    │  • Scraper module   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
    │   PostgreSQL    │ │ Python LLM  │ │  React Frontend │
    │   Database      │ │ Service     │ │                 │
    │                 │ │ :8001       │ │                 │
    └─────────────────┘ └──────┬──────┘ └─────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Google Gemini     │
                    │       API           │
                    └─────────────────────┘
```

---

## Tech Stack

| Component | Technology | Owner |
|-----------|------------|-------|
| Backend API | Rust (Axum framework) | Will |
| Database | PostgreSQL | Will |
| LLM Service | Python (FastAPI) + Google Gemini | Ben |
| Event Scrapers | Rust (in backend) or Python (standalone) | Skylar |
| Frontend | React / JavaScript | TBD |

---

## Team Roles

| Name | Role | Responsibilities |
|------|------|------------------|
| **Will** | Coordinator / Backend Lead | Rust backend, database, API endpoints, code review |
| **Ben** | AI Engineer | Python LLM service, Gemini integration, natural language processing |
| **Skylar** | Data Engineer | Web scrapers, data ingestion pipeline, event normalization |
| **Malachi** | Frontend Developer | React UI, user experience |
| **Jordi** | Fullstack Developer | Cross-stack support, integration, features as needed |

---

## Getting Started

### Prerequisites

Install these tools (all platforms):

| Tool | Purpose | Install |
|------|---------|---------|
| Git | Version control | https://git-scm.com/downloads |
| Docker | Run PostgreSQL | https://www.docker.com/products/docker-desktop |
| Rust | Backend (Will, Skylar if using Rust) | https://rustup.rs |
| Python 3.11+ | LLM Service (Ben) | https://www.python.org/downloads |
| Node.js 18+ | Frontend | https://nodejs.org |

### Clone the Repository

```bash
git clone https://github.com/BentNail86/locate918.git
cd locate918
```

---

### Database Setup

**All team members** need the database running to work on the project.

```bash
# Start PostgreSQL in Docker
docker run --name locate918-db \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=locate918 \
  -p 5432:5432 \
  -d postgres:16
```

**Windows PowerShell:**
```powershell
docker run --name locate918-db -e POSTGRES_PASSWORD=password -e POSTGRES_DB=locate918 -p 5432:5432 -d postgres:16
```

**Verify it's running:**
```bash
docker ps
```

**Stop/Start later:**
```bash
docker stop locate918-db
docker start locate918-db
```

---

### Rust Backend Setup

**Required for:** Will, Skylar (if writing scrapers in Rust)

1. **Install Rust** (if not already):
   ```bash
   # macOS/Linux
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   
   # Windows: Download from https://rustup.rs
   ```

2. **Navigate to backend:**
   ```bash
   cd backend
   ```

3. **Create environment file:**
   ```bash
   # macOS/Linux
   cp .env.example .env
   
   # Windows PowerShell
   Copy-Item .env.example .env
   ```
   
   Or create `backend/.env` manually:
   ```
   DATABASE_URL=postgres://postgres:password@localhost:5432/locate918
   LLM_SERVICE_URL=http://localhost:8001
   ```

4. **Build and run:**
   ```bash
   cargo build
   cargo run
   ```

5. **Verify:** Open http://localhost:3000/api/events — should return `[]`

---

### Python LLM Service Setup

**Required for:** Ben

1. **Navigate to LLM service:**
   ```bash
   cd llm-service
   ```

2. **Create virtual environment:**
   ```bash
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   
   # Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate
   ```

3. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn google-generativeai pydantic python-dotenv
   ```

4. **Create environment file** (`llm-service/.env`):
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   
   Get your API key at: https://makersuite.google.com/app/apikey

5. **Run the service:**
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

6. **Verify:** Open http://localhost:8001/health

---

### Frontend Setup

**Required for:** Frontend developer

1. **Navigate to frontend:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

4. **Verify:** Open http://localhost:5173

---

## Project Structure

```
locate918/
├── backend/                    # Rust API Server (Will)
│   ├── src/
│   │   ├── main.rs            # Entry point
│   │   ├── routes/
│   │   │   ├── mod.rs         # Route registration
│   │   │   ├── events.rs      # GET/POST /api/events
│   │   │   ├── users.rs       # GET/POST /api/users
│   │   │   └── chat.rs        # POST /api/chat (calls LLM service)
│   │   ├── models/
│   │   │   └── mod.rs         # Event, User, UserPreference structs
│   │   ├── services/
│   │   │   ├── mod.rs
│   │   │   └── llm.rs         # HTTP client for Python LLM service
│   │   ├── scraper/
│   │   │   └── mod.rs         # Event scrapers (Skylar)
│   │   └── db/
│   │       └── mod.rs         # Database utilities
│   ├── migrations/
│   │   └── 001_initial.sql    # Database schema
│   ├── Cargo.toml
│   └── .env
│
├── llm-service/                # Python LLM Service (Ben)
│   └── app/
│       ├── main.py            # FastAPI entry point
│       ├── models/
│       │   └── schemas.py     # Pydantic models
│       ├── routes/
│       │   └── chat.py        # /api/parse-intent, /api/chat
│       └── services/
│           └── gemini.py      # Gemini API integration
│
├── frontend/                   # React App
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── App.jsx
│   └── package.json
│
└── docs/                       # Documentation
```

---

## API Endpoints

### Rust Backend (`:3000`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List all events |
| POST | `/api/events` | Create an event |
| GET | `/api/events/:id` | Get event by ID |
| GET | `/api/events/search?q=&category=` | Search events |
| POST | `/api/users` | Create user |
| GET | `/api/users/:id` | Get user |
| GET | `/api/users/:id/profile` | Get full profile (for LLM) |
| POST | `/api/users/:id/preferences` | Add preference |
| POST | `/api/users/:id/interactions` | Record interaction |
| POST | `/api/chat` | Natural language search (coming soon) |

### Python LLM Service (`:8001`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/parse-intent` | Natural language → search params |
| POST | `/api/chat` | Generate conversational response |
| POST | `/api/normalize` | Normalize scraped event data |

---

## Development Tasks by Role

### Ben (AI Engineer) — Python LLM Service

**Your files:**
- `llm-service/app/models/schemas.py` — Pydantic models
- `llm-service/app/routes/chat.py` — API endpoints
- `llm-service/app/services/gemini.py` — Gemini integration

**Tasks:**
1. Implement `parse_user_intent()` — Convert "jazz concerts this weekend" → `{category: "music", query: "jazz", date_from: "..."}`
2. Implement `generate_chat_response()` — Take events + message, return friendly response
3. Implement `normalize_events()` — Clean up messy scraped data

**Language:** Python (FastAPI + google-generativeai)

---

### Skylar (Data Engineer) — Event Scrapers

**Your files:**
- `backend/src/scraper/mod.rs` (if Rust)
- OR create `scrapers/` folder at project root (if Python)

**Tasks:**
1. Build scrapers for 2-3 event sources (Eventbrite, local venues, city calendar)
2. Store events via `POST /api/events` or directly in database
3. Optionally call `/api/normalize` to clean data with LLM

**Language:** Your choice!
- **Rust** — Work in `backend/src/scraper/`. Will can help map your logic to Rust.
- **Python** — Create a separate `scrapers/` folder. Use `requests` + `beautifulsoup4`.

---

### Frontend Developer — React UI

**Your files:**
- Everything in `frontend/`

**Tasks:**
1. Event list/search page
2. Event detail page
3. Chat interface for natural language search
4. User preferences page

**Language:** JavaScript/React

---

### Will (Coordinator) — Rust Backend

**Current status:** Core API complete. Ready for integration.

**Remaining:**
1. Uncomment chat routes when Ben's service is ready
2. Review PRs, help team with Rust questions
3. Deploy when ready

---

## Environment Variables

### `backend/.env`
```
DATABASE_URL=postgres://postgres:password@localhost:5432/locate918
LLM_SERVICE_URL=http://localhost:8001
```

### `llm-service/.env`
```
GEMINI_API_KEY=your_key_here
```

---

## Running the Full Stack

**Terminal 1 — Database:**
```bash
docker start locate918-db
```

**Terminal 2 — Rust Backend:**
```bash
cd backend
cargo run
```

**Terminal 3 — Python LLM Service:**
```bash
cd llm-service
source venv/bin/activate  # Windows: .\venv\Scripts\Activate
uvicorn app.main:app --reload --port 8001
```

**Terminal 4 — Frontend:**
```bash
cd frontend
npm run dev
```

---

## Troubleshooting

### "Connection refused" on database
```bash
docker start locate918-db
```

### Rust build errors
```bash
rustup update
cargo clean
cargo build
```

### Python import errors
```bash
cd llm-service
source venv/bin/activate
pip install -r requirements.txt  # (if you create one)
```

### Port already in use
```bash
# Find what's using the port (macOS/Linux)
lsof -i :3000

# Windows
netstat -ano | findstr :3000
```

---

## Questions?

- **Rust help:** Ask Will
- **Python/AI help:** Ask Ben
- **Scraper strategy:** Ask Skylar

Let's build something great! 🚀
