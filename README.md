<p align="center">
  <img src="./Locate918.png" alt="locate 918" width="400">
</p>

# Locate918 - Event Discovery Aggregator

An AI-powered event aggregator for the Tulsa (918) area that pulls from multiple public sources, uses an LLM to normalize and summarize event information, and matches users to events through natural language preferences.

---

## Quick Start

**Get the database password from a team member, then:**

```bash
# 1. Clone the repo
git clone https://github.com/locate918/capstone.git
cd capstone

# 2. Start the backend
cd backend
cp .env.example .env  # Then add the real password
cargo run

# 3. Start the frontend (new terminal)
cd frontend
cp .env.example .env
npm install
npm start

# 4. Open http://localhost:5173
```

**No Docker needed!** We use a shared Supabase database.

---

## Table of Contents

- [Project Overview](#project-overview)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Team Roles](#team-roles)
- [Getting Started](#getting-started)
- [Scraper Tool Guide](#scraper-tool-guide)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)
- [Running the Full Stack](#running-the-full-stack)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

**Problem:** Event discovery is fragmented. People miss events because information is scattered across multiple platforms (Eventbrite, Facebook, venue websites), each optimized for promoters rather than attendees.

**Solution:** A unified platform that:
1. Aggregates events from multiple public sources using our Universal Scraper
2. Uses AI (Google Gemini) to normalize and summarize event data
3. Offers **two ways to search**: Smart Search (quick) and Chat with **Tully** (conversational)
4. Answers contextual questions (weather, directions, venue info)
5. Links back to original sources, driving traffic to organizers

---

## How It Works

### Two Ways to Discover Events

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

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                │
│                                                                             │
│    ┌───────────────────────────┐     ┌───────────────────────────┐        │
│    │      SMART SEARCH         │     │     CHAT WITH TULLY       │        │
│    │  "concerts under $30"     │     │  "what's fun this weekend" │        │
│    └─────────────┬─────────────┘     └─────────────┬─────────────┘        │
│                  │                                 │                       │
│                  ▼                                 ▼                       │
│         React Frontend (:5173)              LLM Service (:8001)           │
│                  │                                 │                       │
│                  └─────────────┬─────────────────┘                        │
│                                ▼                                           │
│                    ┌─────────────────────┐                                │
│                    │  Rust Backend (:3000)│                                │
│                    └──────────┬──────────┘                                │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        SUPABASE (PostgreSQL)                               │
│                   db.kpihjwzqtwqlschmtekx.supabase.co                     │
│                                                                           │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │   events    │  │    users    │  │ preferences │  │   venues    │    │
│   │  (270+)     │  │  (accounts) │  │  (explicit) │  │  (metadata) │    │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌───────────────────────────────┼───────────────────────────────────────────┐
│                    SCRAPER TOOL (localhost:5000)                           │
│                                                                           │
│    ┌─────────────────────────────────────────────────────────────┐       │
│    │  Universal Scraper - 18 extraction strategies               │       │
│    │  • EventCalendarApp API    • Simpleview/VisitTulsa API     │       │
│    │  • Timely API              • BOK Center API                 │       │
│    │  • Schema.org/JSON-LD      • Eventbrite, Ticketmaster      │       │
│    │  • Stubwire, Dice.fm       • Generic HTML parsing          │       │
│    └─────────────────────────────────────────────────────────────┘       │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Port | Owner |
|-----------|------------|------|-------|
| Backend API | Rust (Axum) | 3000 | Will |
| Database | Supabase (PostgreSQL) | - | Team (cloud) |
| LLM Service | Python (FastAPI) + Gemini | 8001 | Ben |
| Scraper Tool | Python (Flask) + Playwright | 5000 | Will/Skylar |
| Frontend | React | 5173 | Malachi/Jordi |

---

## Team Roles

| Name | Role | Responsibilities |
|------|------|------------------|
| **Will** | Coordinator / Backend Lead | Rust backend, database, scraper tool, code review |
| **Ben** | AI Engineer | Python LLM service, Gemini integration, `/api/search` + `/api/chat` |
| **Skylar** | Data Engineer | Running scrapers, finding event sources, data quality |
| **Malachi** | Frontend Developer | React UI, search + chat interface |
| **Jordi** | Fullstack Developer | Cross-stack support, integration |

---

## Getting Started

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Git | Version control | https://git-scm.com/downloads |
| Rust | Backend | https://rustup.rs |
| Python 3.11+ | LLM Service + Scraper | https://www.python.org/downloads |
| Node.js 18+ | Frontend | https://nodejs.org |

**Note:** Docker is optional — we use Supabase for the shared database.

### Clone the Repository

```bash
git clone https://github.com/locate918/capstone.git
cd capstone
```

---

### Database Setup (Supabase)

We use a **shared Supabase database** — the whole team connects to the same data!

1. **Get the database password** from Will or another team member
2. Add it to your `backend/.env` file (see Environment Variables below)

That's it! No Docker, no local database setup.

---

### Rust Backend Setup

```bash
cd backend

# Create environment file
cp .env.example .env

# Edit .env and add the real password (get from team)
notepad .env   # Windows
nano .env      # Mac/Linux

# Build and run
cargo build
cargo run
```

**Verify:** http://localhost:3000/api/events should return events JSON.

---

### Python LLM Service Setup

```bash
cd llm-service

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate   # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit and add the Gemini API key (get from Ben)

# Run the service
uvicorn app.main:app --reload --port 8001
```

**Verify:** http://localhost:8001/ should return `{"status": "online"}`

---

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file (if not exists)
cp .env.example .env

# Run development server
npm start
```

**Verify:** http://localhost:5173 should show the app with events.

---

## Scraper Tool Guide

The Universal Scraper is a Flask web app that extracts events from any website using 18 different strategies.

### Setup

```bash
cd backend/src/scraper

# Install dependencies
pip install flask playwright httpx beautifulsoup4 python-dateutil python-dotenv

# Install browser for Playwright
playwright install chromium

# Run the scraper
python ScraperTool.py
```

**Open:** http://localhost:5000

### Features

- ✅ **Smart Extraction:** Auto-detects site type (Eventbrite, Timely, JSON-LD, etc.)
- ✅ **robots.txt Compliance:** Won't scrape sites that disallow it
- ✅ **Direct API Access:** Uses APIs when available (faster, more reliable)
- ✅ **Direct Database Save:** Sends events straight to Supabase

### Supported Platforms

| Platform | Method | Events |
|----------|--------|--------|
| VisitTulsa/Simpleview | REST API | 300+ |
| EventCalendarApp | Direct API | varies |
| Timely | Direct API | varies |
| BOK Center | AJAX API | ~50 |
| Eventbrite | Schema.org/HTML | varies |
| Ticketmaster | HTML parsing | varies |
| Most venue sites | Generic extraction | varies |

### Usage

1. Open http://localhost:5000
2. Enter a URL (e.g., `https://www.visittulsa.com/events/`)
3. Enter source name (e.g., `Visit Tulsa`)
4. Click **Scrape**
5. Review events in the table
6. Click **💾 Save to Database**

### Good Sources to Scrape

```
https://www.visittulsa.com/events/         # City calendar (300+ events)
https://www.bokcenter.com/events           # BOK Center shows
https://www.cainsballroom.com/events       # Cain's Ballroom concerts
https://www.guthriegreen.com/events        # Outdoor events
https://www.tulsapac.com/events            # Performing arts
https://www.philbrook.org/events           # Museum events
```

---

## API Endpoints

### Rust Backend (`:3000`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List events (default 100, max 1000) |
| GET | `/api/events?limit=500` | List with custom limit |
| POST | `/api/events` | Create event (scraper uses this) |
| GET | `/api/events/:id` | Get event by ID |
| GET | `/api/events/search` | Search with filters |

**Search Parameters:**
```
GET /api/events/search?q=jazz&category=concerts&price_max=30
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Text search in title/description |
| `category` | string | Filter by category |
| `start_date` | ISO date | Start of date range |
| `end_date` | ISO date | End of date range |
| `price_max` | number | Maximum price |
| `outdoor` | boolean | Only outdoor events |
| `family_friendly` | boolean | Only family-friendly |
| `limit` | integer | Max results (default 50) |

### Python LLM Service (`:8001`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/search` | Parse natural language → search params |
| POST | `/chat` | Chat with Tully |
| POST | `/normalize` | Raw HTML → structured events |

---

## Environment Variables

### `backend/.env`
```
DATABASE_URL=postgresql://postgres:PASSWORD_HERE@db.kpihjwzqtwqlschmtekx.supabase.co:5432/postgres
LLM_SERVICE_URL=http://localhost:8001
```
> **Get the password from Will or another team member**

### `llm-service/.env`
```
GEMINI_API_KEY=your_gemini_api_key_here
BACKEND_URL=http://localhost:3000
```
> **Get the Gemini API key from Ben** or create your own at https://makersuite.google.com/app/apikey

### `frontend/.env`
```
PORT=5173
REACT_APP_BACKEND_URL=http://localhost:3000
REACT_APP_USE_MOCKS=false
```

---

## Running the Full Stack

Open 3-4 terminal windows:

**Terminal 1 — Rust Backend:**
```bash
cd backend
cargo run
# Runs on http://localhost:3000
```

**Terminal 2 — LLM Service:**
```bash
cd llm-service
.\venv\Scripts\Activate   # Windows (or: source venv/bin/activate)
uvicorn app.main:app --reload --port 8001
# Runs on http://localhost:8001
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm start
# Runs on http://localhost:5173
```

**Terminal 4 — Scraper (when needed):**
```bash
cd backend/src/scraper
python ScraperTool.py
# Runs on http://localhost:5000
```

---

## Project Structure

```
locate918/
├── backend/                      # Rust API Server
│   ├── src/
│   │   ├── main.rs
│   │   ├── routes/
│   │   │   ├── events.rs        # GET/POST /api/events, /search
│   │   │   └── users.rs
│   │   └── models/
│   ├── src/scraper/
│   │   └── ScraperTool.py       # Universal event scraper
│   ├── migrations/
│   ├── .env.example
│   └── Cargo.toml
│
├── llm-service/                  # Python LLM Service
│   ├── app/
│   │   ├── main.py
│   │   ├── models/schemas.py
│   │   ├── routes/
│   │   │   ├── search.py
│   │   │   ├── chat.py
│   │   │   └── normalize.py
│   │   ├── services/gemini.py
│   │   └── tools/definitions.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                     # React App
│   ├── src/
│   │   ├── components/
│   │   ├── services/api.js
│   │   └── App.js
│   ├── .env.example
│   └── package.json
│
└── README.md
```

---

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