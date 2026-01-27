# Locate918 Task Assignments

## Team Roles

| Member | Role | Primary Responsibilities |
|--------|------|-------------------------|
| **Will** | Coordinator / Backend Lead | Database, Rust API, integration, code review |
| **Ben** | AI/LLM Engineer | Python LLM service, Gemini integration, `/api/search`, `/api/chat`, `/api/normalize` |
| **Skylar** | Data Engineer | Scrapers, API integrations, cron scheduling |
| **Malachi** | Frontend Developer | React UI, search bar, chat interface |
| **Jordi** | Fullstack / QA | Integration testing, CI/CD, cross-stack support |

---

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐
│  Smart Search   │     │  Chat (Tully)   │
│  "concerts $30" │     │  "what's fun?"  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
   POST /api/search        POST /api/chat
   (Gemini Flash)          (Gemini Pro + Tools)
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Rust Backend :3000 │
          │  /api/events/search │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │     PostgreSQL      │
          └─────────────────────┘
```

---

## Current Sprint Status

### ✅ Will (Backend Lead) - COMPLETE

| Task | Status |
|------|--------|
| Set up PostgreSQL database | ✅ Done |
| Create database schema with migrations | ✅ Done |
| Implement Events CRUD endpoints | ✅ Done |
| Implement Users/Preferences/Interactions endpoints | ✅ Done |
| Implement `/api/events/search` with all filters | ✅ Done |
| Update `services/llm.rs` for new schema | ✅ Done |

**Remaining:**
- [ ] Review and merge team PRs
- [ ] Set up production deployment
- [ ] Help with integration issues

---

### 🔄 Ben (AI/LLM Engineer) - IN PROGRESS

#### Priority 1: `/api/normalize` (Enables Skylar)

Scrapers need this endpoint to clean raw data before storing.

```python
# llm-service/app/routes/normalize.py

@app.post("/api/normalize")
async def normalize(request: NormalizeRequest):
    """
    Input: Raw HTML/text from scraper
    Output: Clean Event JSON matching database schema
    """
    prompt = f"""
    Extract event information from this content. Return JSON with:
    - title (required)
    - description
    - venue, venue_address, location
    - start_time (ISO 8601), end_time
    - categories (array, e.g., ["concerts", "rock"])
    - price_min, price_max (numbers or null)
    - outdoor (boolean)
    - family_friendly (boolean)
    - image_url
    
    Content:
    {request.raw_content}
    """
    
    response = await gemini.generate(prompt)
    events = parse_json(response.text)
    
    # POST each event to Rust backend
    for event in events:
        event["source_url"] = request.source_url
        event["source_name"] = request.source_name
        await httpx.post("http://localhost:3000/api/events", json=event)
    
    return {"count": len(events), "events": events}
```

#### Priority 2: `/api/search` (Smart Search)

Quick query → parse → results. No conversation.

```python
# llm-service/app/routes/search.py

@app.post("/api/search")
async def smart_search(request: SearchRequest):
    """
    Input: Natural language query
    Output: Events + parsed parameters
    """
    # 1. Parse query with Gemini Flash (fast, cheap)
    parse_prompt = f"""
    Extract search parameters from this query. Return JSON:
    {{
      "category": "concerts" | "sports" | "family" | "comedy" | "nightlife" | null,
      "query": "text to search" | null,
      "start_date": "YYYY-MM-DD" | null,
      "end_date": "YYYY-MM-DD" | null,
      "location": "Downtown" | "Broken Arrow" | null,
      "price_max": number | null,
      "outdoor": boolean | null,
      "family_friendly": boolean | null
    }}
    
    Query: "{request.query}"
    Current date: {datetime.now().isoformat()}
    """
    
    parsed = await gemini_flash.generate(parse_prompt)
    params = json.loads(parsed.text)
    
    # 2. Query Rust backend
    events = await httpx.get(
        "http://localhost:3000/api/events/search",
        params={k: v for k, v in params.items() if v is not None}
    )
    
    # 3. Return results
    return {
        "events": events.json(),
        "parsed": params
    }
```

#### Priority 3: `/api/chat` (Chat with Tully)

Full conversational AI with tool calling.

```python
# llm-service/app/routes/chat.py

SYSTEM_PROMPT = """
You are Tully, a friendly and knowledgeable guide to events in Tulsa, Oklahoma.

Your personality:
- Warm, enthusiastic, and helpful
- You love Tulsa and know it well
- You give personalized recommendations based on user preferences

You have access to a search_events tool to find events. Use it when users ask about events.
For weather, directions, or general questions, use your knowledge or say you'd need to look that up.

User preferences: {preferences}
"""

SEARCH_EVENTS_TOOL = {
    "name": "search_events",
    "description": "Search for events in Tulsa area",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["concerts", "sports", "family", "comedy", "nightlife"]},
            "query": {"type": "string", "description": "Text to search for"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
            "price_max": {"type": "number"},
            "outdoor": {"type": "boolean"},
            "family_friendly": {"type": "boolean"}
        }
    }
}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 1. Get user profile for personalization
    profile = None
    if request.user_id:
        profile = await httpx.get(
            f"http://localhost:3000/api/users/{request.user_id}/profile"
        )
    
    # 2. Build system prompt with preferences
    system = SYSTEM_PROMPT.format(
        preferences=json.dumps(profile.json()) if profile else "None provided"
    )
    
    # 3. Send to Gemini Pro with tools
    response = await gemini_pro.generate(
        system=system,
        messages=[{"role": "user", "content": request.message}],
        tools=[SEARCH_EVENTS_TOOL]
    )
    
    # 4. Handle tool calls
    events = []
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call.name == "search_events":
                result = await httpx.get(
                    "http://localhost:3000/api/events/search",
                    params=tool_call.arguments
                )
                events = result.json()
                
                # Continue conversation with results
                response = await gemini_pro.continue_with_tool_result(
                    tool_call_id=tool_call.id,
                    result=json.dumps(events)
                )
    
    return {
        "message": response.text,
        "events": events,
        "conversation_id": request.conversation_id or str(uuid.uuid4())
    }
```

#### Checklist

- [ ] Set up FastAPI project in `llm-service/`
- [ ] Install dependencies: `fastapi`, `uvicorn`, `google-generativeai`, `httpx`, `pydantic`
- [ ] Get Gemini API key from [Google AI Studio](https://aistudio.google.com/)
- [ ] Implement `/api/normalize` endpoint
- [ ] Implement `/api/search` endpoint
- [ ] Implement `/api/chat` endpoint with tool calling
- [ ] Test with Skylar's scrapers
- [ ] Test with Malachi's frontend

---

### 🔄 Skylar (Data Engineer) - WAITING ON BEN

**Blocked by:** `/api/normalize` endpoint

#### Priority 1: Eventbrite API Integration

```python
# scrapers/eventbrite.py

import httpx
import os

EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_API_KEY")
LLM_SERVICE_URL = "http://localhost:8001"

async def fetch_tulsa_events():
    """Fetch events from Eventbrite API"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.eventbriteapi.com/v3/events/search/",
            params={
                "location.address": "Tulsa, OK",
                "location.within": "25mi",
                "expand": "venue"
            },
            headers={"Authorization": f"Bearer {EVENTBRITE_API_KEY}"}
        )
        
        data = response.json()
        
        for event in data.get("events", []):
            # Send to normalize endpoint
            await client.post(
                f"{LLM_SERVICE_URL}/api/normalize",
                json={
                    "raw_content": str(event),  # or format as needed
                    "source_url": event.get("url"),
                    "source_name": "Eventbrite"
                }
            )

if __name__ == "__main__":
    import asyncio
    asyncio.run(fetch_tulsa_events())
```

#### Priority 2: Visit Tulsa Scraper

```python
# scrapers/visit_tulsa.py

import httpx
from bs4 import BeautifulSoup

async def scrape_visit_tulsa():
    """Scrape events from Visit Tulsa website"""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://www.visittulsa.com/events/")
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find event elements (adjust selectors as needed)
        events = soup.select(".event-item")
        
        for event in events:
            html_content = str(event)
            source_url = event.select_one("a")["href"]
            
            # Send to normalize endpoint
            await client.post(
                "http://localhost:8001/api/normalize",
                json={
                    "raw_content": html_content,
                    "source_url": source_url,
                    "source_name": "Visit Tulsa"
                }
            )
```

#### Priority 3: Cron Scheduling

```python
# scrapers/scheduler.py

import schedule
import time
import asyncio

from eventbrite import fetch_tulsa_events
from visit_tulsa import scrape_visit_tulsa
from cains import scrape_cains_ballroom

def run_eventbrite():
    asyncio.run(fetch_tulsa_events())

def run_scrapers():
    asyncio.run(scrape_visit_tulsa())
    asyncio.run(scrape_cains_ballroom())

# Schedule jobs
schedule.every(6).hours.do(run_eventbrite)   # APIs: every 6 hours
schedule.every(4).hours.do(run_scrapers)      # Scrapers: every 4 hours

if __name__ == "__main__":
    print("Starting scheduler...")
    while True:
        schedule.run_pending()
        time.sleep(60)
```

#### Checklist

- [ ] Sign up for [Eventbrite API](https://www.eventbrite.com/platform/api)
- [ ] Sign up for [Bandsintown API](https://artists.bandsintown.com/support/api-installation)
- [ ] Build Eventbrite integration
- [ ] Build Visit Tulsa scraper
- [ ] Build Cain's Ballroom scraper
- [ ] Set up cron scheduling
- [ ] Test end-to-end with `/api/normalize`
- [ ] Monitor for duplicates (source_url constraint handles this)

---

### 🔄 Malachi (Frontend) - CAN START NOW

Can mock API responses while waiting for Ben.

#### Components to Build

1. **SearchBar.jsx** - Smart search input
2. **ChatInterface.jsx** - Chat with Tully
3. **EventCard.jsx** - Event display
4. **EventList.jsx** - Results grid
5. **PreferencesForm.jsx** - User settings

#### Mock Data for Development

```javascript
// src/mocks/events.js

export const mockEvents = [
  {
    id: "1",
    title: "Jazz Night at Cain's",
    venue: "Cain's Ballroom",
    venue_address: "423 N Main St, Tulsa, OK",
    start_time: "2026-02-01T20:00:00Z",
    categories: ["concerts", "jazz"],
    price_min: 15,
    price_max: 25,
    outdoor: false,
    family_friendly: false,
    image_url: "https://picsum.photos/400/200",
    source_url: "https://cainsballroom.com/event/123"
  },
  // Add more mock events...
];

export const mockSearchResponse = {
  events: mockEvents,
  parsed: {
    category: "concerts",
    date_range: "this weekend"
  }
};

export const mockChatResponse = {
  message: "I found some great concerts this weekend! 🎵\n\n**Jazz Night at Cain's** - Friday at 8pm, $15-25",
  events: mockEvents,
  conversation_id: "abc123"
};
```

#### API Service

```javascript
// src/services/api.js

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8001";
const USE_MOCKS = process.env.REACT_APP_USE_MOCKS === "true";

import { mockSearchResponse, mockChatResponse } from "../mocks/events";

export async function smartSearch(query) {
  if (USE_MOCKS) return mockSearchResponse;
  
  const response = await fetch(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query })
  });
  return response.json();
}

export async function chat(message, userId, conversationId) {
  if (USE_MOCKS) return mockChatResponse;
  
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, user_id: userId, conversation_id: conversationId })
  });
  return response.json();
}
```

#### Checklist

- [ ] Set up React project with Tailwind
- [ ] Create mock data for development
- [ ] Build SearchBar component
- [ ] Build ChatInterface component
- [ ] Build EventCard component
- [ ] Build EventList component
- [ ] Connect to real API when Ben is ready
- [ ] Mobile responsive layout
- [ ] User preferences form

---

### 🔄 Jordi (Fullstack / QA)

- [ ] Set up CI/CD pipeline with GitHub Actions
- [ ] Write integration tests for API endpoints
- [ ] Test scraper → normalize → database flow
- [ ] Test frontend → API integration
- [ ] Help with cross-stack issues
- [ ] Documentation review

---

## API Contracts

### Smart Search

```
POST http://localhost:8001/api/search

Request:
{
  "query": "rock concerts this weekend under $30"
}

Response:
{
  "events": [
    {
      "id": "uuid",
      "title": "Rock Night at Cain's",
      "venue": "Cain's Ballroom",
      "start_time": "2026-02-01T20:00:00Z",
      "categories": ["concerts", "rock"],
      "price_min": 15,
      "price_max": 25,
      "image_url": "https://...",
      "source_url": "https://..."
    }
  ],
  "parsed": {
    "category": "concerts",
    "price_max": 30,
    "start_date": "2026-01-31",
    "end_date": "2026-02-02"
  }
}
```

### Chat with Tully

```
POST http://localhost:8001/api/chat

Request:
{
  "user_id": "uuid",
  "message": "What family events are happening this weekend?",
  "conversation_id": "uuid"  // optional
}

Response:
{
  "message": "Here are some great family events this weekend! 🎪\n\n**Tulsa Zoo** - ...",
  "events": [...],
  "conversation_id": "uuid"
}
```

### Normalize (Scrapers → LLM)

```
POST http://localhost:8001/api/normalize

Request:
{
  "raw_content": "<div class='event'>Jazz Night...</div>",
  "source_url": "https://example.com/event/123",
  "source_name": "Visit Tulsa"
}

Response:
{
  "count": 1,
  "events": [
    {
      "title": "Jazz Night",
      "venue": "The Colony",
      "start_time": "2026-02-01T20:00:00Z",
      "categories": ["concerts", "jazz"],
      "price_min": 10,
      "price_max": 10
    }
  ]
}
```

### Events (Direct Database)

```
GET http://localhost:3000/api/events/search?category=concerts&price_max=30&family_friendly=true

Response:
[
  {
    "id": "uuid",
    "title": "...",
    ...
  }
]
```

---

## Dependency Chain

```
Ben (/api/normalize) ──► Skylar (scrapers) ──► Database ◄── Ben (/api/search, /api/chat)
                                                   │
                                                   ▼
                                            Malachi (frontend)
```

**Key insight:** Malachi can work in parallel with mocks. Skylar is blocked until Ben finishes `/api/normalize`.

---

## Environment Variables

### Backend (`backend/.env`)
```
DATABASE_URL=postgres://postgres:password@localhost:5432/locate918
LLM_SERVICE_URL=http://localhost:8001
```

### LLM Service (`llm-service/.env`)
```
GEMINI_API_KEY=your_key_here
BACKEND_URL=http://localhost:3000
```

### Frontend (`frontend/.env`)
```
REACT_APP_API_URL=http://localhost:8001
REACT_APP_USE_MOCKS=true
```

---

## Questions?

- **Backend/Database:** Ask Will
- **AI/LLM endpoints:** Ask Ben
- **Scrapers:** Ask Skylar
- **Frontend:** Ask Malachi
- **Integration/QA:** Ask Jordi
- **Everything else:** Ask in Discord