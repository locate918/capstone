# Locate918 Task Assignments

## Team Roles

| Member | Role | Primary Responsibilities |
|--------|------|-------------------------|
| **Will** | Coordinator / Backend Lead | Database, Rust API, integration, code review |
| **Ben** | AI/LLM Engineer | Chat endpoint, search endpoint, Gemini integration |
| **Skylar** | Data Engineer | Scrapers, API integrations, cron jobs |
| **Jordi** | Frontend Developer | React UI, search bar, chat interface |
| **Malachi** | Full Stack / Business | Features, UX, monetization |

---

## Current Sprint Tasks

### Will (Backend Lead)
- [x] Set up PostgreSQL database
- [x] Create database schema with migrations
- [x] Implement Events CRUD endpoints
- [x] Implement Users/Preferences endpoints
- [x] Implement `/api/events/search` endpoint
- [ ] Review and merge team PRs
- [ ] Set up production deployment

### Ben (AI/LLM Engineer)
- [ ] **Implement `/api/search`** - Smart search endpoint
  - Parse natural language query with Gemini Flash
  - Extract parameters (category, date, price, etc.)
  - Call existing search endpoint
  - Return formatted results
- [ ] **Implement `/api/chat`** - Chat with Tully
  - Set up Gemini Pro with tool calling
  - Define `search_events` tool
  - Handle multi-turn conversation
  - Integrate user preferences into system prompt
- [ ] Create `services/gemini.rs` client

### Skylar (Data Engineer)
- [ ] **Eventbrite API integration**
  - Sign up for API key
  - Fetch Tulsa area events
  - POST to `/api/events`
- [ ] **Build 2-3 local scrapers**
  - Visit Tulsa events page
  - Cain's Ballroom calendar
  - Tulsa World events
- [ ] **Set up cron scheduling**
  - Eventbrite: every 6 hours
  - Local scrapers: every 4 hours
- [ ] Test data pipeline end-to-end

### Jordi (Frontend)
- [ ] Set up React project with Tailwind
- [ ] **Smart Search Bar component**
  - Input field with search icon
  - Calls `/api/search`
  - Displays results as cards
- [ ] **Chat Interface component**
  - Message list
  - Input field
  - Calls `/api/chat`
  - Typing indicator
- [ ] Event card component
- [ ] Mobile responsive layout

### Malachi (Full Stack / Business)
- [ ] Logo and branding finalization
- [ ] Sponsored events feature design
- [ ] User onboarding flow
- [ ] Help with frontend/backend as needed

---

## API Contract

### Smart Search (Ben → Jordi)

**Request:**
```
POST /api/search
Content-Type: application/json

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

### Chat (Ben → Jordi)

**Request:**
```
POST /api/chat
Content-Type: application/json

{
  "user_id": "uuid",
  "message": "What family events are happening this weekend?",
  "conversation_id": "uuid"  // optional, for multi-turn
}
```

**Response:**
```json
{
  "message": "Here are some great family events this weekend:\n\n🎪 **Tulsa State Fair**...",
  "events": [...],  // referenced events
  "conversation_id": "uuid"
}
```

### Events (Skylar → Database)

**Request:**
```
POST /api/events
Content-Type: application/json

{
  "title": "Concert Name",
  "source_url": "https://original-source.com/event",
  "source_name": "Eventbrite",
  "start_time": "2026-02-01T20:00:00Z",
  "venue": "Venue Name",
  "venue_address": "123 Main St, Tulsa, OK",
  "location": "Downtown Tulsa",
  "categories": ["concerts", "rock"],
  "price_min": 15.00,
  "price_max": 25.00,
  "outdoor": false,
  "family_friendly": false,
  "image_url": "https://..."
}
```

---

## Dependencies

```
Skylar (scrapers) ──► Database ◄── Ben (AI endpoints)
                          │
                          ▼
                   Jordi (frontend)
```

- **Jordi** needs Ben's endpoints to be defined (can mock initially)
- **Ben** needs database populated (can use test data initially)
- **Skylar** needs nothing—can start immediately

---

## Getting Started

### Ben - AI Endpoints

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/)
2. Add to `.env`: `GEMINI_API_KEY=your_key`
3. Create `src/services/gemini.rs`:

```rust
use reqwest::Client;
use serde::{Deserialize, Serialize};

pub struct GeminiClient {
    client: Client,
    api_key: String,
}

impl GeminiClient {
    pub fn new(api_key: String) -> Self {
        Self {
            client: Client::new(),
            api_key,
        }
    }

    pub async fn chat(&self, messages: Vec<Message>, tools: Vec<Tool>) -> Result<Response, Error> {
        // Implementation here
    }
}
```

4. Implement `/api/search` in `src/routes/search.rs`
5. Implement `/api/chat` in `src/routes/chat.rs`

### Skylar - Scrapers

1. Sign up for [Eventbrite API](https://www.eventbrite.com/platform/api)
2. Create `src/scraper/eventbrite.rs`:

```rust
pub async fn fetch_tulsa_events() -> Result<Vec<CreateEvent>, Error> {
    let client = reqwest::Client::new();
    let response = client
        .get("https://www.eventbriteapi.com/v3/events/search/")
        .query(&[
            ("location.address", "Tulsa, OK"),
            ("location.within", "25mi"),
        ])
        .bearer_auth(&api_key)
        .send()
        .await?;
    
    // Parse and convert to CreateEvent structs
}
```

3. Create scraper for Visit Tulsa (HTML parsing)
4. Set up cron job to run scrapers

### Jordi - Frontend

1. Create React app:
```bash
npx create-react-app frontend
cd frontend
npm install tailwindcss axios
```

2. Create components:
   - `SearchBar.jsx` - Smart search input
   - `ChatInterface.jsx` - Tully chat
   - `EventCard.jsx` - Event display
   - `EventList.jsx` - Results grid

3. Mock API responses while waiting for Ben

---

## Questions?

Ask in Discord or tag the relevant person in GitHub issues.
