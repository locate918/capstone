# Task Assignments

## Overview

Skylar has two core systems that share a database:

1. **Data Pipeline** - Collects and normalizes events (background)
2. **Chat Interface** - AI-powered user interaction (on-demand)

---

## Skylar's Tasks (Data Pipeline)

### Sprint 1-2: API Integrations

- [ ] **Eventbrite API**
  - Sign up for API key
  - Fetch Tulsa-area events
  - Map response to Event schema
  - Store directly (already JSON)

- [ ] **Bandsintown API**
  - Sign up for API key
  - Fetch concerts by Tulsa venue list
  - Map to Event schema
  - Store directly

- [ ] **Ticketmaster API** (optional)
  - Covers major venues (BOK Center, etc.)

### Sprint 2-3: Local Site Scrapers

- [ ] **Visit Tulsa** (visittulsa.com/events)
  - Scrape event listings
  - Extract: name, date, venue, description, link
  - Send raw HTML to `/api/normalize`

- [ ] **Cain's Ballroom** (cainsballroom.com)
  - Scrape show calendar
  - Send to `/api/normalize`

- [ ] **Tulsa World Calendar** (tulsaworld.com/calendar)
  - Scrape events
  - Send to `/api/normalize`

### Sprint 3: Scheduling

- [ ] **Cron Job Setup**
  - Run API fetches every 6 hours
  - Run scrapers every 12 hours
  - Use Tokio scheduled tasks or system cron

- [ ] **Error Handling**
  - Log failed scrapes
  - Retry logic
  - Alert on repeated failures

### Scraper Template

```rust
async fn scrape_source(source: &str) -> Result<Vec<RawEvent>> {
    // 1. Fetch HTML
    let html = reqwest::get(source).await?.text().await?;
    
    // 2. Send to normalize endpoint
    let events = client
        .post("/api/normalize")
        .json(&NormalizeRequest { 
            raw_html: html, 
            source_url: source.to_string(),
            source_name: "Visit Tulsa".to_string()
        })
        .send()
        .await?
        .json::<Vec<Event>>()
        .await?;
    
    // 3. Store in database
    for event in events {
        db.insert_event(event).await?;
    }
    
    Ok(())
}
```

---

## Ben's Tasks (Chat Interface)

### Sprint 2-3: Normalize Endpoint

- [ ] **POST /api/normalize**
  - Receives raw HTML + source info
  - Sends to Claude/Gemini with prompt
  - Returns normalized Event objects

```rust
async fn normalize(payload: NormalizeRequest) -> Json<Vec<Event>> {
    let prompt = format!(
        "Extract events from this HTML. Return JSON array with fields: 
        name, description, venue_name, venue_address, start_time, 
        end_time, category, price_min, price_max, outdoor, family_friendly.
        
        Source: {}
        HTML: {}",
        payload.source_name,
        payload.raw_html
    );
    
    let response = llm_client.complete(prompt).await?;
    let events: Vec<Event> = serde_json::from_str(&response)?;
    
    Json(events)
}
```

### Sprint 4: Chat Endpoint

- [ ] **POST /api/chat**
  - Receives user message + userId
  - Loads user preferences
  - Sends to Claude with tool definitions
  - Handles tool calls (search_events)
  - Returns formatted response

- [ ] **Tool: search_events**
  - Query PostgreSQL with filters
  - Return matching events to Claude

```rust
// Tool definition sent to Claude
let tools = vec![
    Tool {
        name: "search_events",
        description: "Search local Tulsa events",
        input_schema: json!({
            "type": "object",
            "properties": {
                "category": { "type": "string" },
                "startDate": { "type": "string" },
                "endDate": { "type": "string" },
                "priceMax": { "type": "number" },
                "outdoor": { "type": "boolean" }
            }
        })
    }
];
```

### Sprint 5-6: User Preferences

- [ ] **User Preferences Table**
  ```sql
  CREATE TABLE user_preferences (
      user_id UUID PRIMARY KEY,
      favorite_categories TEXT[],
      price_range_min DECIMAL,
      price_range_max DECIMAL,
      location TEXT,
      radius_miles INT,
      family_friendly_only BOOLEAN
  );
  ```

- [ ] **Interactions Table**
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

- [ ] **GET/PUT /api/users/:id/preferences**
- [ ] **POST /api/users/:id/interactions**
- [ ] **Tool: get_user_preferences**
  - Returns user's preferences + recent interactions
  - Claude uses for personalized responses

---

## Shared: Database Schema

### Events Table
```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(500) NOT NULL,
    description TEXT,
    venue_name VARCHAR(255),
    venue_address TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    categories TEXT[],
    price_min DECIMAL,
    price_max DECIMAL,
    source_url TEXT NOT NULL,
    source_name VARCHAR(100),
    outdoor BOOLEAN DEFAULT false,
    family_friendly BOOLEAN DEFAULT false,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(source_url)  -- Prevent duplicates
);

CREATE INDEX idx_events_start_time ON events(start_time);
CREATE INDEX idx_events_categories ON events USING GIN(categories);
```

---

## Frontend Tasks (TBD)

### Sprint 5-6: Chat UI

- [ ] **ChatInterface component**
  - Message input
  - Message history display
  - Event card rendering in responses

- [ ] **EventCard component**
  - Name, date, venue, price
  - Save/dismiss buttons
  - Link to source

- [ ] **PreferencesForm component**
  - Category checkboxes
  - Price range slider
  - Location input

---

## MVP Checklist

### Data Pipeline (Skylar)
- [ ] Eventbrite API working
- [ ] 2+ scrapers working
- [ ] Cron job running
- [ ] Events populating database

### Chat Interface (Ben)
- [ ] `/api/normalize` working
- [ ] `/api/chat` working with tool calls
- [ ] `search_events` returns results
- [ ] User preferences stored and passed to AI

### Frontend
- [ ] Chat interface functional
- [ ] Events display correctly
- [ ] Preferences can be set

---

## Dependencies

```
Skylar depends on:
  - Ben's /api/normalize endpoint (to clean scraped data)
  - Database schema (shared)

Ben depends on:
  - Database populated with events (to have data to search)
  - Event schema finalized (to build queries)

Frontend depends on:
  - /api/chat working (to display responses)
  - Event schema (to render cards)
```

### Suggested Order

1. **Week 1:** Finalize Event schema, set up database
2. **Week 2:** Ben builds `/api/normalize`, Skylar builds first scraper
3. **Week 3:** Skylar sends data to normalize, events in DB
4. **Week 4:** Ben builds `/api/chat` with tools
5. **Week 5:** Frontend chat UI
6. **Week 6:** User preferences, polish
