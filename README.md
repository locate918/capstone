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
3. Offers **two ways to search**: Smart Search (quick) and Chat with **Tully** (conversational)
4. Answers contextual questions (weather, directions, venue info)
5. Links back to original sources, driving traffic to organizers

---

## How It Works

### Two Ways to Discover Events

Users can choose how they want to find events:

#### 🔍 Smart Search (Quick)
For users who know what they want. Type a natural language query, get instant results.

```
"rock concerts this weekend under $30"
```
→ Returns a list of matching events immediately. No conversation, just results.

#### 💬 Chat with Tully (Conversational)
For exploration and discovery. Our AI assistant helps you find the perfect event.

```
User: "I'm new to Tulsa with my family. What should we do this weekend?"

Tully: "Welcome to Tulsa! Here are some great family activities this weekend:

🎪 Tulsa State Fair - Saturday 10am at Expo Square
   Perfect for all ages! Rides, food, and live entertainment. $15/person.

🦁 Tulsa Zoo - Open daily 9am-5pm  
   The new elephant exhibit is amazing! $12 adults, $8 kids.

The weather looks great—sunny and 72°F. Would you like directions to any of these?"
```

Both interfaces use the same AI backend and event database.

### Two Separate Systems

| System | Purpose | When It Runs | Owner |
|--------|---------|--------------|-------|
| **Data Pipeline** | Scrape, normalize, store events | Background (cron job) | Skylar |
| **User Interface** | Smart Search + Chat via AI + tools | On-demand per request | Ben |

They share the **database**—that's the connection point.

### Smart Search Flow

```
1. User: "rock concerts this weekend under $30"
                    │
                    ▼
2. /api/search parses query with lightweight AI
                    │
                    ▼
3. Extracts: category=concerts, genre=rock, 
             date=weekend, price_max=30
                    │
                    ▼
4. Queries PostgreSQL database
                    │
                    ▼
5. Returns JSON array of matching events
```

**Characteristics:** Fast (~200ms), single request/response, no conversation.

### Chat Flow (Tully)

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

**Characteristics:** Multi-turn conversation, can ask follow-ups, more personalized.

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
│                              USER INTERFACES                                │
│                                                                             │
│    ┌───────────────────────────┐     ┌───────────────────────────┐        │
│    │      SMART SEARCH         │     │     CHAT WITH TULLY       │        │
│    │  "concerts under $30"     │     │  "what's fun this weekend" │        │
│    │                           │     │                           │        │
│    │  Quick • One request      │     │  Conversational • Follow-ups│       │
│    └─────────────┬─────────────┘     └─────────────┬─────────────┘        │
│                  │                                 │                       │
│                  ▼                                 ▼                       │
│            /api/search                       /api/chat                     │
│           (lightweight)                    (full Gemini)                   │
│                  │                                 │                       │
│                  └─────────────┬─────────────────┘                        │
│                                │                                           │
│                                ▼                                           │
│                    ┌─────────────────────┐                                │
│                    │   search_events()   │                                │
│                    │   Database Query    │                                │
│                    └──────────┬──────────┘                                │
│                               │                                           │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           POSTGRESQL DATABASE                              │
│                                                                           │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │   events    │  │    users    │  │ preferences │  │ interactions│    │
│   │ (50+ sources)│  │  (accounts) │  │  (explicit) │  │  (implicit) │    │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌───────────────────────────────┼───────────────────────────────────────────┐
│                         DATA PIPELINE (Background)                         │
│                                                                           │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐              │
│    │ Eventbrite  │     │   Venue     │     │    City     │              │
│    │    API      │     │  Websites   │     │  Calendars  │              │
│    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘              │
│           │                   │                   │                      │
│           └───────────────────┼───────────────────┘                      │
│                               │                                          │
│                               ▼                                          │
│                    ┌─────────────────────┐                               │
│                    │   Scraper Service   │                               │
│                    │     (Skylar)        │                               │
│                    └──────────┬──────────┘                               │
│                               │                                          │
│                               ▼                                          │
│                    ┌─────────────────────┐                               │
│                    │   /api/normalize    │                               │
│                    │   (LLM cleans data) │                               │
│                    └─────────────────────┘                               │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Owner |
|-----------|------------|-------|
| Backend API | Rust (Axum framework) | Will |
| Database | PostgreSQL | Will |
| LLM Service | Python (FastAPI) + Google Gemini | Ben |
| Event Scrapers | Rust (in backend) or Python (standalone) | Skylar |
| Frontend | React / JavaScript | Malachi / Jordi |

---

## Team Roles

| Name | Role | Responsibilities |
|------|------|------------------|
| **Will** | Coordinator / Backend Lead | Rust backend, database, API endpoints, code review |
| **Ben** | AI Engineer | Python LLM service, Gemini integration, **`/api/search` + `/api/chat`**, tool calling |
| **Skylar** | Data Engineer | Web scrapers, API integrations (Eventbrite, etc.), **cron scheduling** |
| **Malachi** | Frontend Developer | React UI, **search bar + chat interface**, user experience |
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
   pip install fastapi uvicorn google-generativeai pydantic python-dotenv httpx
   ```

4. **Create environment file** (`llm-service/.env`):
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   BACKEND_URL=http://localhost:3000
   ```
   
   Get your API key at: https://makersuite.google.com/app/apikey

5. **Run the service:**
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

6. **Verify:** Open http://localhost:8001/health

---

### Frontend Setup

**Required for:** Malachi, Jordi

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
│   │   │   ├── events.rs      # GET/POST /api/events + /api/events/search
│   │   │   ├── users.rs       # User accounts + preferences
│   │   │   └── chat.rs        # Forwards to LLM service
│   │   ├── models/
│   │   │   └── mod.rs         # Event, User, UserPreference structs
│   │   ├── services/
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
│       │   ├── search.py      # /api/search (quick search)
│       │   ├── chat.py        # /api/chat (Tully conversation)
│       │   └── normalize.py   # /api/normalize for scrapers
│       ├── services/
│       │   └── gemini.py      # Gemini API integration
│       └── tools/
│           └── definitions.py # Tool schemas for Gemini
│
├── frontend/                   # React App (Malachi, Jordi)
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBar.jsx      # Smart search input
│   │   │   ├── ChatInterface.jsx  # Chat with Tully
│   │   │   ├── EventCard.jsx      # Event display
│   │   │   └── EventList.jsx      # Results grid
│   │   ├── pages/
│   │   └── App.jsx
│   └── package.json
│
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md
│   ├── TASKS.md
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
| GET | `/api/events` | List all upcoming events |
| POST | `/api/events` | Create an event (scrapers use this) |
| GET | `/api/events/:id` | Get event by ID |
| GET | `/api/events/search` | Search with filters (see below) |
| POST | `/api/users` | Create user |
| GET | `/api/users/:id` | Get user |
| GET | `/api/users/:id/profile` | Full profile for AI personalization |
| GET | `/api/users/:id/preferences` | Get category preferences |
| POST | `/api/users/:id/preferences` | Add/update preference |
| PUT | `/api/users/:id/preferences` | Update settings (location, budget) |
| POST | `/api/users/:id/interactions` | Log interaction (click/save/dismiss) |

#### Search Parameters

```
GET /api/events/search?q=jazz&category=concerts&price_max=30&outdoor=true
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Text search in title/description |
| `category` | string | Filter by category |
| `start_date` | ISO date | Start of date range |
| `end_date` | ISO date | End of date range |
| `location` | string | Area filter (Downtown, Broken Arrow) |
| `price_max` | number | Maximum price |
| `outdoor` | boolean | Only outdoor events |
| `family_friendly` | boolean | Only family-friendly events |
| `limit` | integer | Max results (default 50) |

### Python LLM Service (`:8001`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/search` | **Smart Search** — Query → Parse → Results |
| POST | `/api/chat` | **Chat with Tully** — Full conversation with tools |
| POST | `/api/normalize` | Raw HTML → LLM → Normalized Event objects |

### API Contracts (Ben ↔ Malachi/Jordi)

#### Smart Search

**Request:**
```json
POST /api/search
{
  "query": "rock concerts this weekend under $30"
}
```

**Response:**
```json
{
  "events": [
    {
      "id": "uuid",
      "title": "Rock Night at Cain's",
      "venue": "Cain's Ballroom",
      "start_time": "2026-02-01T20:00:00Z",
      "price_min": 15,
      "price_max": 25,
      "image_url": "https://...",
      "source_url": "https://..."
    }
  ],
  "parsed": {
    "category": "concerts",
    "genre": "rock",
    "date_range": "this weekend",
    "price_max": 30
  }
}
```

#### Chat with Tully

**Request:**
```json
POST /api/chat
{
  "user_id": "uuid",
  "message": "What family events are happening this weekend?",
  "conversation_id": "uuid"
}
```

**Response:**
```json
{
  "message": "Here are some great family events this weekend! 🎪\n\n**Tulsa State Fair**...",
  "events": [...],
  "conversation_id": "uuid"
}
```

---

## Development Tasks by Role

### Ben (AI Engineer) — `/api/search` + `/api/chat`

**Your files:**
- `llm-service/app/routes/search.py` — Smart search (lightweight)
- `llm-service/app/routes/chat.py` — Chat with Tully (full Gemini)
- `llm-service/app/routes/normalize.py` — Normalize scraped data
- `llm-service/app/services/gemini.py` — Gemini integration
- `llm-service/app/tools/definitions.py` — Tool schemas

**Tasks:**
1. **`/api/search`** — Parse natural language query, extract parameters, query backend, return results
2. **`/api/chat`** — Full Gemini conversation with tool calling
3. **`search_events` tool execution** — When Gemini calls this, query `/api/events/search`
4. **`/api/normalize`** — Take raw HTML from scrapers, extract Event objects
5. **Pass user preferences** — Include in system prompt for personalization

**Smart Search (lightweight):**
```python
async def search(query: str):
    # 1. Use Gemini Flash to parse query
    parsed = await gemini_flash.parse(query)
    # Returns: {category: "concerts", price_max: 30, ...}
    
    # 2. Query backend
    events = await httpx.get(f"{BACKEND_URL}/api/events/search", params=parsed)
    
    # 3. Return results
    return {"events": events, "parsed": parsed}
```

**Chat with Tully (full conversation):**
```python
async def chat(message: str, user_id: str, conversation_id: str):
    # 1. Get user preferences
    prefs = await get_user_profile(user_id)
    
    # 2. Send to Gemini Pro with tools
    response = await gemini_pro.generate(
        messages=conversation_history,
        tools=tool_definitions,
        system=f"You are Tully, a friendly Tulsa event guide. User prefs: {prefs}"
    )
    
    # 3. Handle tool calls
    if response.tool_calls:
        results = await execute_tool(response.tool_calls[0])
        final = await gemini_pro.continue_with_results(results)
        return final
    
    return response
```

---

### Skylar (Data Engineer) — Event Scrapers

**Your files:**
- `scrapers/` folder (Python) OR `backend/src/scraper/` (Rust)

**Tasks:**
1. **API Integrations** (no scraping needed):
   - Eventbrite API — Sign up, fetch Tulsa events
   - Bandsintown API — Fetch concerts
   - (Optional) Ticketmaster API

2. **Scrapers for local sites**:
   - Visit Tulsa (visittulsa.com/events)
   - Cain's Ballroom (cainsballroom.com)
   - Tulsa World calendar
   
3. **Send to normalize** — Raw HTML → `POST /api/normalize` → Clean Event objects

4. **Cron scheduling** — Run scrapers every few hours

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

See `docs/EVENT_SOURCES.md` for full list of 50+ sources to target.

---

### Malachi & Jordi (Frontend) — React UI

**Your files:**
- Everything in `frontend/`

**Key components:**
1. **SearchBar.jsx** — Smart search input, calls `/api/search`
2. **ChatInterface.jsx** — Chat with Tully, calls `/api/chat`
3. **EventCard.jsx** — Display event with save/dismiss buttons
4. **EventList.jsx** — Results grid/list

**Tasks:**
1. Build search bar UI that calls `/api/search`
2. Build chat UI that calls `/api/chat`
3. Display events returned in responses
4. Track interactions (clicks, saves) via `/api/users/:id/interactions`
5. User preferences form

---

### Will (Coordinator) — Rust Backend

**Current status:** ✅ Core API complete

**Done:**
- [x] Events CRUD + search endpoint
- [x] Users + preferences + interactions
- [x] Database schema with all fields

**Remaining:**
- [ ] Review and merge team PRs
- [ ] Help with integration issues
- [ ] Production deployment

---

## User Preferences & Machine Learning

### Phase 1: Explicit Preferences (MVP)

User sets in profile:
```json
{
  "favorite_categories": ["concerts", "comedy"],
  "price_max": 50,
  "location_preference": "downtown",
  "radius_miles": 10,
  "family_friendly_only": false
}
```

Passed to Gemini in system prompt — Tully naturally factors them into responses.

### Phase 2: Behavior Tracking (MVP)

Log interactions:
```sql
INSERT INTO user_interactions (user_id, event_id, interaction_type, event_category, event_venue)
VALUES ($1, $2, 'clicked', 'concerts', 'Cain''s Ballroom');
```

Interaction types: `clicked`, `saved`, `dismissed`, `attended`

### Phase 3: ML Recommendations (Future)

- Analyze patterns in interaction data
- Build taste profiles / embeddings
- "Users who liked X also liked Y"
- Tully uses history to personalize:
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

### "PoolTimedOut" error
Database just started — wait 5 seconds and try again.

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
| Gemini Flash (search parsing) | ~$0.001 per query |
| Gemini Pro (chat) | ~$0.01 per conversation |
| Gemini (normalization ~500 events/week) | $5-15/week |
| 1000 user searches/month | ~$1-5/month |
| 1000 chat conversations/month | ~$10-20/month |
| **Total MVP** | **~$30-50/month** |

---

## Monetization Ideas

- **Sponsored Events** — Local businesses pay for featured placement
- **Premium Features** — Advanced filters, calendar sync, notifications
- **Affiliate Links** — Commission on ticket sales

---

## Questions?

- **Rust/Backend help:** Ask Will
- **Python/AI help:** Ask Ben
- **Scraper strategy:** Ask Skylar
- **Frontend:** Ask Malachi or Jordi

Let's build something great! 🚀
