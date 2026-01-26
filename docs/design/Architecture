# Locate918 Architecture

## Overview

Locate918 uses a **two-tier architecture**:

1. **Data Pipeline** - Background processes that collect, normalize, and store events
2. **User Interface** - Two ways to query: Smart Search (quick) and Chat (conversational)

Both interfaces query the same pre-populated database. The AI doesn't scrape the web per request—it queries our normalized data.

---

## System Diagram

```
                           ┌─────────────────────────────────────┐
                           │           USER INTERFACES           │
                           ├──────────────────┬──────────────────┤
                           │   Smart Search   │   Chat (Tully)   │
                           │   "concerts $30" │   "what's fun?"  │
                           └────────┬─────────┴────────┬─────────┘
                                    │                  │
                                    ▼                  ▼
                              /api/search         /api/chat
                              (lightweight)      (full Gemini)
                                    │                  │
                                    └────────┬─────────┘
                                             │
                                             ▼
                           ┌─────────────────────────────────────┐
                           │        search_events(params)        │
                           │         Database Query              │
                           └──────────────────┬──────────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              POSTGRESQL DATABASE                              │
├──────────────────┬──────────────────┬───────────────────┬───────────────────┤
│      events      │      users       │  user_preferences │ user_interactions │
│  (50+ sources)   │   (accounts)     │    (explicit)     │    (implicit)     │
└──────────────────┴──────────────────┴───────────────────┴───────────────────┘
                                              ▲
                                              │
                           ┌──────────────────┴──────────────────┐
                           │          DATA PIPELINE              │
                           │         (runs on cron)              │
                           ├─────────────────────────────────────┤
                           │  Eventbrite API  │  Local Scrapers  │
                           │  Bandsintown API │  (Visit Tulsa,   │
                           │  Ticketmaster    │   Cain's, etc)   │
                           └──────────────────┴──────────────────┘
```

---

## User Interfaces

### Smart Search (`/api/search`)

For users who know what they want. Quick, no conversation.

**Input:**
```
"rock concerts this weekend under $30"
```

**Process:**
1. Lightweight AI parses query → extracts: category=concerts, genre=rock, date=weekend, price_max=30
2. Builds database query
3. Returns JSON array of events

**Output:**
```json
[
  {"title": "Rock Night at Cain's", "price_max": 25, "start_time": "..."},
  {"title": "Indie Rock Showcase", "price_max": 20, "start_time": "..."}
]
```

**Characteristics:**
- Single request/response
- No conversation history
- Fast (~200ms)
- Uses smaller/cheaper AI model

---

### Chat Interface (`/api/chat`)

For exploration and discovery. Full conversational AI named **Tully**.

**Input:**
```
User: "I'm new to Tulsa with my family. What should we do this weekend?"
```

**Process:**
1. Full Gemini API with system prompt + user preferences
2. AI calls `search_events` tool (family_friendly=true, date=weekend)
3. AI may also use web search for weather, directions
4. Formats natural language response

**Output:**
```
"Welcome to Tulsa! Here are some great family activities this weekend:

🎪 **Tulsa State Fair** - Saturday 10am at Expo Square
   Perfect for all ages! Rides, food, and live entertainment. $15/person.

🦁 **Zoo Day** - Open daily 9am-5pm
   The Tulsa Zoo has a new elephant exhibit! $12 adults, $8 kids.

The weather looks great—sunny and 72°F. Would you like directions to any of these?"
```

**Characteristics:**
- Multi-turn conversation
- Maintains context
- Can ask clarifying questions
- Uses Gemini with tool calling
- More expensive but better UX for discovery

---

## Data Pipeline

Events are collected in the background, NOT triggered by user requests.

### Sources

**Structured APIs (clean JSON, no scraping):**
- Eventbrite API
- Bandsintown API
- Ticketmaster API

**Web Scrapers (for local sources without APIs):**
- Visit Tulsa
- Cain's Ballroom
- Tulsa World Events
- BOK Center
- Local venue websites

### Flow

```
Raw Data → /api/normalize → PostgreSQL
   │            │
   │            └── LLM extracts: title, date, venue, 
   │                categories, price, family_friendly, etc.
   │
   └── HTML from scraper OR JSON from API
```

### Schedule

| Source | Frequency | Method |
|--------|-----------|--------|
| Eventbrite | Every 6 hours | API |
| Bandsintown | Daily | API |
| Local venues | Every 4 hours | Scraper |
| Visit Tulsa | Daily | Scraper |

---

## Database Schema

### events
```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    venue TEXT,
    venue_address TEXT,
    location TEXT,              -- "Downtown Tulsa", "Broken Arrow"
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    categories TEXT[],          -- ['concerts', 'rock', 'live music']
    price_min DOUBLE PRECISION,
    price_max DOUBLE PRECISION,
    outdoor BOOLEAN DEFAULT FALSE,
    family_friendly BOOLEAN DEFAULT FALSE,
    source_url TEXT NOT NULL UNIQUE,
    source_name TEXT,           -- "Eventbrite", "Cain's Ballroom"
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    location_preference TEXT,
    radius_miles INTEGER,
    price_max DOUBLE PRECISION,
    family_friendly_only BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### user_preferences (explicit)
```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    category TEXT NOT NULL,
    weight INTEGER,  -- -5 (hate) to +5 (love)
    UNIQUE(user_id, category)
);
```

### user_interactions (implicit)
```sql
CREATE TABLE user_interactions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    event_id UUID REFERENCES events(id),
    interaction_type TEXT,  -- 'clicked', 'saved', 'dismissed'
    event_category TEXT,    -- denormalized for ML
    event_venue TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## AI Tool Definition

The AI calls this tool to query our database:

```javascript
{
  name: "search_events",
  description: "Search for local events in the Tulsa area",
  parameters: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "Text to search in title/description"
      },
      category: {
        type: "string",
        enum: ["concerts", "sports", "family", "nightlife", "comedy", "festivals", "theater", "food"]
      },
      start_date: {
        type: "string",
        description: "Start of date range (ISO 8601)"
      },
      end_date: {
        type: "string",
        description: "End of date range (ISO 8601)"
      },
      price_max: {
        type: "number",
        description: "Maximum ticket price"
      },
      outdoor: {
        type: "boolean",
        description: "Only outdoor events"
      },
      family_friendly: {
        type: "boolean",
        description: "Only family-friendly events"
      },
      location: {
        type: "string",
        description: "Area filter (Downtown, Broken Arrow, etc)"
      },
      limit: {
        type: "integer",
        description: "Max results to return (default 10)"
      }
    }
  }
}
```

---

## API Endpoints

### Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List upcoming events |
| GET | `/api/events/:id` | Get single event |
| POST | `/api/events` | Create event (scrapers use this) |
| GET | `/api/events/search` | Search with filters |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users` | Create user |
| GET | `/api/users/:id` | Get user |
| GET | `/api/users/:id/profile` | Full profile for AI |
| POST | `/api/users/:id/preferences` | Set category preference |
| PUT | `/api/users/:id/preferences` | Update settings |
| POST | `/api/users/:id/interactions` | Log interaction |

### AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search` | Smart search (quick) |
| POST | `/api/chat` | Chat with Tully |

---

## Personalization Phases

### Phase 1: Explicit Preferences (MVP)
- User sets favorite categories, price range, location in profile
- Passed to AI in system prompt
- AI naturally factors them into recommendations

### Phase 2: Behavior Tracking (MVP)
- Log clicks, saves, dismisses to `user_interactions`
- Build dataset for future ML

### Phase 3: ML Recommendations (Future)
- Analyze interaction patterns
- Build taste profiles / embeddings
- "Users who liked X also liked Y"
- AI calls `get_user_preferences` tool

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Rust + Axum |
| Database | PostgreSQL 16 |
| AI | Google Gemini API |
| Scraping | Rust (scraper crate) |
| Frontend | React + Tailwind (planned) |
| Hosting | TBD |

---

## Cost Estimates (MVP)

| Item | Monthly Cost |
|------|--------------|
| Gemini API (normalize ~500 events/week) | $5-15 |
| Gemini API (chat ~1000 queries/month) | $10-20 |
| PostgreSQL (managed) | $5-15 |
| **Total** | **~$30-50** |

### Cost Optimization
- Use Gemini Flash for search (cheaper)
- Use Gemini Pro for chat (better quality)
- Batch API for normalization (50% off)
- Prompt caching for repeated queries (90% off)
