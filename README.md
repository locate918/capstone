<p align="center">
  <img src="./Locate918.png" alt="locate 918" width="400">
</p>



# Locate918 - Event Discovery Aggregator

An AI-powered event aggregator for the Tulsa (918) area that pulls from multiple public sources, uses an LLM to normalize and summarize event information, and matches users to events through natural language preferences.

---

## Table of Contents

- [Project Overview](#project-overview)
- [How It Works](#how-it-works)
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
- [User Preferences & Machine Learning](#user-preferences--machine-learning)
- [Environment Variables](#environment-variables)
- [Running the Full Stack](#running-the-full-stack)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

**Problem:** Event discovery is fragmented. People miss events because information is scattered across multiple platforms (Eventbrite, Facebook, venue websites), each optimized for promoters rather than attendees.

**Solution:** A unified platform that:
1. Aggregates events from multiple public sources
2. Uses AI (Google Gemini) to normalize and summarize event data
3. Lets users search with natural language via an **AI chat interface**
4. Answers contextual questions (weather, directions, venue info)
5. Links back to original sources, driving traffic to organizers

---

## How It Works

### The AI Interface

Users don't browse lists—they **chat**. The AI is the search interface:

> "What concerts are happening this weekend?"  
> "Any free family events near downtown?"  
> "Will it rain Saturday?"  
> "How do I get to Gathering Place?"

The AI calls **our custom tools** to search the event database, then uses web search for contextual info (weather, directions), and responds conversationally.

### Two Separate Systems

| System | Purpose | When It Runs | Owner |
|--------|---------|--------------|-------|
| **Data Pipeline** | Scrape, normalize, store events | Background (cron job) | Skylar |
| **Chat Interface** | User queries via AI + tools | On-demand per request | Ben |

They share the **database**—that's the connection point.

### Chat Flow

```
1. User: "What concerts are happening this weekend?"
                    │
                    ▼
2. /api/chat sends message to Gemini with tool definitions
                    │
                    ▼
3. Gemini calls: search_events({
     category: "concerts",
     startDate: "2026-01-30",
     endDate: "2026-02-01"
   })
                    │
                    ▼
4. Our backend executes query against PostgreSQL
                    │
                    ▼
5. Returns results to Gemini
                    │
                    ▼
6. Gemini formats response:
   "I found 3 concerts this weekend! Friday night, 
   Band X is playing at Cain's Ballroom..."
                    │
                    ▼
7. User sees friendly response with event details
```

### Weather, Directions, Venue Info

For contextual questions beyond events, the AI uses **web search** or built-in knowledge—we don't need to build custom tools for everything:

- "Will it rain Saturday?" → AI uses web search
- "How do I get to Gathering Place?" → AI uses web search
- "Is Cain's Ballroom loud?" → AI uses built-in knowledge

We only build **one custom tool** for MVP: `search_events`. Everything else comes free.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE (Background)                          │
│                                                                             │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                 │
│    │ Eventbrite  │     │   Venue     │     │    City     │                 │
│    │    API      │     │  Websites   │     │  Calendars  │                 │
│    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                 │
│           │                   │                   │                         │
│           └───────────────────┼───────────────────┘                         │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │   Scraper Service   │                                  │
│                    │     (Skylar)        │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │   /api/normalize    │                                  │
│                    │   (LLM cleans data) │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │     PostgreSQL      │◀──────────────────────┐         │
│                    │     Database        │                       │         │
│                    └─────────────────────┘                       │         │
│                                                                  │         │
└──────────────────────────────────────────────────────────────────┼─────────┘
                                                                   │
┌──────────────────────────────────────────────────────────────────┼─────────┐
│                         CHAT INTERFACE (On-Demand)               │         │
│                                                                  │         │
│    ┌─────────────┐     ┌─────────────────────┐                  │         │
│    │    User     │     │   RUST BACKEND      │                  │         │
│    │   Message   │────▶│   (Axum) :3000      │                  │         │
│    └─────────────┘     │                     │                  │         │
│                        │  • /api/chat        │                  │         │
│                        │  • /api/events      │                  │         │
│                        │  • /api/users       │                  │         │
│                        └──────────┬──────────┘                  │         │
│                                   │                             │         │
│                                   ▼                             │         │
│                        ┌─────────────────────┐                  │         │
│                        │   Python LLM        │                  │         │
│                        │   Service :8001     │                  │         │
│                        │                     │                  │         │
│                        │  Gemini + Tools:    │                  │         │
│                        │  • search_events    │──────────────────┘         │
│                        │  • get_preferences  │                            │
│                        └──────────┬──────────┘                            │
│                                   │                                       │
│                                   ▼                                       │
│                        ┌─────────────────────┐                            │
│                        │   Formatted         │                            │
│                        │   Response to User  │                            │
│                        └─────────────────────┘                            │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Owner |
|-----------|------------|-------|
| Backend API | Rust (Axum framework) | Will |
| Database | PostgreSQL | Will |
| LLM Service | Python (FastAPI) + Google Gemini | Ben |
| Event Scrapers | Rust (in backend) or Python (standalone) | Skylar |
| Frontend | React / JavaScript | Malachi |
| FullStack/QA | Rust, Python, React | Jordi |

---

## Team Roles

| Name | Role | Responsibilities |
|------|------|------------------|
| **Will** | Coordinator / Backend Lead | Rust backend, database, API endpoints, code review |
| **Ben** | AI Engineer | Python LLM service, Gemini integration, **chat with tool calling**, natural language processing |
| **Skylar** | Data Engineer | Web scrapers, data ingestion pipeline, **cron scheduling** |
| **Malachi** | Frontend Developer | React UI, **chat interface**, user experience |
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

**Required for:** Malachi

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
│       │   ├── chat.py        # /api/chat with tool calling
│       │   └── normalize.py   # /api/normalize for scrapers
│       ├── services/
│       │   └── gemini.py      # Gemini API integration
│       └── tools/
│           └── definitions.py # Tool schemas for Gemini
│
├── frontend/                   # React App (Malachi)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── EventCard.jsx
│   │   │   └── PreferencesForm.jsx
│   │   ├── pages/
│   │   └── App.jsx
│   └── package.json
│
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md
│   └── EVENT_SOURCES.md
│
└── scrapers/                   # Standalone scrapers (Skylar, if Python)
    ├── eventbrite.py
    ├── visit_tulsa.py
    └── cains.py
```

---

## API Endpoints

### Rust Backend (`:3000`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List all events |
| POST | `/api/events` | Create an event |
| GET | `/api/events/:id` | Get event by ID |
| GET | `/api/events/search?q=&category=&startDate=&endDate=` | Search events |
| POST | `/api/users` | Create user |
| GET | `/api/users/:id` | Get user |
| GET | `/api/users/:id/preferences` | Get user preferences |
| PUT | `/api/users/:id/preferences` | Update preferences |
| POST | `/api/users/:id/interactions` | Record interaction (click/save/dismiss) |
| POST | `/api/chat` | Forwards to LLM service |

### Python LLM Service (`:8001`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/chat` | **Main endpoint** — User message → Gemini with tools → Response |
| POST | `/api/normalize` | Raw HTML → LLM → Normalized Event objects |

### Tool Definitions (Used by Gemini)

```python
tools = [
    {
        "name": "search_events",
        "description": "Search local Tulsa events by category, date, location",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string", "enum": ["concerts", "sports", "family", "nightlife", "comedy", "all"]},
                "startDate": {"type": "string", "format": "date"},
                "endDate": {"type": "string", "format": "date"},
                "priceMax": {"type": "number"},
                "outdoor": {"type": "boolean"},
                "familyFriendly": {"type": "boolean"}
            }
        }
    },
    {
        "name": "get_user_preferences",
        "description": "Get user's saved preferences and interaction history",
        "parameters": {
            "type": "object",
            "properties": {
                "userId": {"type": "string"}
            }
        }
    }
]
```

When Gemini calls a tool, Ben's service executes it (queries DB via Rust backend) and returns results to Gemini for formatting.

---

## Development Tasks by Role

### Ben (AI Engineer) — Python LLM Service

**Your files:**
- `llm-service/app/routes/chat.py` — Main chat endpoint with tool calling
- `llm-service/app/routes/normalize.py` — Normalize scraped data
- `llm-service/app/services/gemini.py` — Gemini integration
- `llm-service/app/tools/definitions.py` — Tool schemas

**Tasks:**
1. **`/api/chat` with tool calling** — Send user message + tools to Gemini, handle tool calls, return response
2. **`search_events` tool execution** — When Gemini calls this, query the Rust backend's `/api/events/search`
3. **`/api/normalize`** — Take raw HTML from scrapers, use Gemini to extract Event objects
4. **Pass user preferences** — Include in system prompt so Gemini personalizes responses

**Key concept:** Gemini is the interface. It decides when to call `search_events`. Your code executes the tool and returns results to Gemini.

```python
# Simplified flow
async def chat(message: str, user_id: str):
    # 1. Get user preferences
    prefs = await get_user_preferences(user_id)
    
    # 2. Send to Gemini with tools
    response = gemini.generate(
        messages=[{"role": "user", "content": message}],
        tools=tool_definitions,
        system=f"User preferences: {prefs}"
    )
    
    # 3. If Gemini wants to call a tool
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        if tool_call.name == "search_events":
            # Execute against our database
            events = await search_events(tool_call.arguments)
            # Send results back to Gemini
            final = gemini.generate(
                messages=[...previous..., {"role": "tool", "content": events}]
            )
            return final.text
    
    return response.text
```

---

### Skylar (Data Engineer) — Event Scrapers

**Your files:**
- `scrapers/` folder (Python) OR `backend/src/scraper/` (Rust)

**Tasks:**
1. **API Integrations** (no scraping needed):
   - Eventbrite API — Sign up, fetch Tulsa events, store directly
   - Bandsintown API — Fetch concerts
   - (Optional) Ticketmaster API

2. **Scrapers for local sites**:
   - Visit Tulsa (visittulsa.com/events)
   - Cain's Ballroom (cainsballroom.com)
   - Tulsa World calendar
   
3. **Send to normalize** — Raw HTML → `POST /api/normalize` → Clean Event objects

4. **Cron scheduling** — Run scrapers every few hours automatically

**Scraper template (Python):**
```python
import requests

def scrape_visit_tulsa():
    # 1. Fetch HTML
    html = requests.get("https://visittulsa.com/events").text
    
    # 2. Send to normalize endpoint
    response = requests.post(
        "http://localhost:8001/api/normalize",
        json={
            "raw_html": html,
            "source_url": "https://visittulsa.com/events",
            "source_name": "Visit Tulsa"
        }
    )
    events = response.json()
    
    # 3. Store each event
    for event in events:
        requests.post("http://localhost:3000/api/events", json=event)

# Run with cron or schedule library
```

See `docs/EVENT_SOURCES.md` for full list of sources to target.

---

### Malachi (Frontend) — React UI

**Your files:**
- Everything in `frontend/`

**Key components:**
1. **ChatInterface.jsx** — Message input, history, event cards in responses
2. **EventCard.jsx** — Display event with save/dismiss buttons
3. **PreferencesForm.jsx** — Set favorite categories, price range, location

**Tasks:**
1. Build chat UI that calls `/api/chat`
2. Display events returned in responses
3. Track interactions (clicks, saves) via `/api/users/:id/interactions`

---

### Will (Coordinator) — Rust Backend

**Current status:** Core API complete.

**Remaining:**
1. Add `/api/events/search` endpoint with filters (category, date range, etc.)
2. Ensure events endpoint returns data in format Ben's tools expect
3. Review PRs, help team integrate

---

## User Preferences & Machine Learning

### Phase 1: Explicit Preferences (MVP)

User sets in profile:
```json
{
  "favorite_categories": ["concerts", "comedy"],
  "price_range_max": 50,
  "location": "downtown",
  "radius_miles": 10,
  "family_friendly_only": false
}
```

Passed to Gemini in system prompt — it naturally factors them into responses.

### Phase 2: Behavior Tracking (MVP)

Log interactions:
```sql
CREATE TABLE interactions (
    id UUID PRIMARY KEY,
    user_id UUID,
    event_id UUID,
    action VARCHAR(20),  -- 'clicked', 'saved', 'dismissed'
    event_category TEXT,
    event_venue TEXT,
    created_at TIMESTAMP
);
```

### Phase 3: ML Recommendations (Future)

- Analyze patterns in interaction data
- Build taste profiles / embeddings
- "Users who liked X also liked Y"
- Gemini uses `get_user_preferences` tool to personalize:
  > "Based on your history, you like rock shows at Cain's—there's one Friday you might enjoy."

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
BACKEND_URL=http://localhost:3000
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
pip install -r requirements.txt
```

### Port already in use
```bash
# Find what's using the port (macOS/Linux)
lsof -i :3000

# Windows
netstat -ano | findstr :3000
```

---

## Cost Estimates

| Item | Cost |
|------|------|
| Gemini API (normalization ~500 events/week) | $5-15/week |
| Gemini API (chat queries) | ~$0.001-0.01 per query |
| 1000 user chats/month | ~$10-20/month |
| **Total MVP** | ~$30-50/month |

---

## Questions?

- **Rust help:** Ask Will
- **Python/AI help:** Ask Ben
- **Scraper strategy:** Ask Skylar
- **Frontend:** Ask Malachi

Let's build something great! 🚀
