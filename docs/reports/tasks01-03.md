# Locate918: Event Discovery Aggregator

**Senior Capstone Project - Spring 2026**

**Team Members:**
| Name | Role |
|------|------|
| Will | Coordinator / Backend Lead |
| Ben | AI Engineer |
| Skylar | Data Engineer |
| Malachi | Frontend Developer |
| Jordi | Fullstack Developer / QA |

**Date:** January 2026
**GitHub Repository:** https://github.com/BentNail86/locate918

---

# Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Project Timeline](#2-project-timeline)
3. [System Requirements](#3-system-requirements)
    - 3.1 Functional Requirements
    - 3.2 Non-Functional Requirements
4. [Architectural Design](#4-architectural-design)
5. [System Modeling (UML Diagrams)](#5-system-modeling-uml-diagrams)
    - 5.1 Use Case Diagram
    - 5.2 Class Diagram
    - 5.3 Sequence Diagram
    - 5.4 Activity Diagram

---

# 1. Problem Statement

Discovering local events is unnecessarily difficult. Event information is scattered across multiple platforms—Eventbrite, Facebook Events, venue websites, Instagram, and community boards—each optimized for promoters rather than attendees. Users must manually check numerous sources to find relevant events, often missing activities they would have attended simply because they didn't know about them.

Locate918 solves this problem by aggregating event data from multiple public sources into a unified platform. Using AI-powered natural language processing, the system normalizes inconsistent event data, generates concise summaries, and enables users to search conversationally (e.g., "What's happening downtown this weekend?"). The platform targets residents of the Tulsa (918) area who want a single, user-focused source for discovering local events. By linking back to original sources, Locate918 drives traffic to event organizers while providing users with a superior discovery experience.

*(148 words)*

---

# 2. Project Timeline

## 2.1 Gantt Chart Overview

```
JANUARY 2026
Week 1-2 (Jan 13-26)
├── All: Repository setup, documentation, problem statement
├── Will: Backend scaffolding begins
├── Skylar: Research event sources
├── Ben: Gemini API research
├── Malachi: Wireframes and mockups
└── Jordi: CI/CD setup, testing framework

FEBRUARY 2026
Week 3-4 (Jan 27 - Feb 9)
├── Will: Database schema, API endpoints
├── Skylar: Scraper architecture and prototype
├── Ben: Prompt prototyping
├── Malachi: React setup, UI components
└── Jordi: OpenAPI spec, integration tests begin

Week 5-6 (Feb 10-23)
├── Will: API refinement, code review support
├── Skylar: Integrate scrapers with database
├── Ben: LLM service module
├── Malachi: Connect UI to API
└── Jordi: Continue integration tests

Week 7-8 (Feb 24 - Mar 9)
├── Will: Support and review
├── Skylar: Additional scrapers, deduplication
├── Ben: Summarization, NL search
├── Malachi: Search UI, NL search UI
└── Jordi: Documentation

MARCH 2026
Week 9-10 (Mar 10-23)
├── Will: Support and review
├── Skylar: Polish scraper reliability
├── Ben: Prompt refinement
├── Malachi: UI polish
└── Jordi: Bug fixes, documentation

Week 11-12 (Mar 24 - Apr 6)
├── All: Integration testing
├── All: Feature freeze
└── All: Bug fixes only

APRIL 2026
Week 13-14 (Apr 7-24)
├── All: Final testing sprint
├── All: Documentation finalization
└── All: Presentation preparation

FINAL PRESENTATION: April 24, 2026
```

## 2.2 Milestone Deadlines

| Date | Milestone | Deliverable |
|------|-----------|-------------|
| Jan 23, 2026 | Problem Statement & Timeline | This document (Task 1) |
| Feb 7, 2026 | System Requirements Spec | Requirements document (Task 2) |
| Feb 14, 2026 | Backend API Demo | Working API endpoints |
| Feb 21, 2026 | Scraper Demo | Event ingestion pipeline |
| Mar 1, 2026 | Architecture Design Doc | UML diagrams (Task 3) |
| Mar 15, 2026 | Midcourse Presentation | Demo + slides (Task 4) |
| Mar 21, 2026 | LLM Integration Demo | Natural language search |
| Apr 10, 2026 | Feature Complete | All features implemented |
| Apr 24, 2026 | Final Presentation | Complete system demo |

## 2.3 Risk Mitigation

| Risk | Impact | Mitigation Strategy | Owner |
|------|--------|---------------------|-------|
| Backend delays block frontend | High | OpenAPI spec enables parallel work with mock data | Jordi |
| Event sources change or block scraping | Medium | Build 3-5 scrapers; only need 2 working | Skylar |
| LLM responses unpredictable | Medium | Start prompt engineering early; iterate | Ben |
| Integration issues | High | Weekly integration checkpoints | All |
| Scope creep | Medium | MVP first; stretch goals documented separately | Will |

---

# 3. System Requirements

## 3.1 Functional Requirements

### FR-1: Event Management

| ID | Requirement | Priority | Testable Criteria |
|----|-------------|----------|-------------------|
| FR-1.1 | The system shall store events with title, description, location, venue, date/time, category, and source URL | Must Have | Database contains all fields; API returns complete event objects |
| FR-1.2 | The system shall retrieve events sorted by date (soonest first) | Must Have | GET /api/events returns events in chronological order |
| FR-1.3 | The system shall retrieve a single event by unique identifier | Must Have | GET /api/events/:id returns correct event or 404 |
| FR-1.4 | The system shall search events by keyword (title/description) | Must Have | GET /api/events/search?q=jazz returns matching events |
| FR-1.5 | The system shall filter events by category | Must Have | GET /api/events/search?category=music returns only music events |

### FR-2: Event Ingestion (Scraping)

| ID | Requirement | Priority | Testable Criteria |
|----|-------------|----------|-------------------|
| FR-2.1 | The system shall scrape events from at least 2 public sources | Must Have | Events from multiple sources exist in database |
| FR-2.2 | The system shall store the original source URL for each event | Must Have | All events have valid source_url field |
| FR-2.3 | The system shall detect and prevent duplicate events | Should Have | Same event from multiple sources appears once |
| FR-2.4 | The system shall run scrapers on a configurable schedule | Should Have | Scrapers execute automatically at set intervals |

### FR-3: Natural Language Processing (LLM)

| ID | Requirement | Priority | Testable Criteria |
|----|-------------|----------|-------------------|
| FR-3.1 | The system shall parse natural language queries into structured search parameters | Must Have | "jazz this weekend" returns {category: music, date_from: Friday} |
| FR-3.2 | The system shall generate conversational responses about events | Must Have | Response reads naturally, mentions event details |
| FR-3.3 | The system shall normalize raw scraped data into consistent format | Should Have | Inconsistent date formats become ISO 8601 |
| FR-3.4 | The system shall categorize events based on content | Should Have | Events without category get assigned one |

### FR-4: User Management

| ID | Requirement | Priority | Testable Criteria |
|----|-------------|----------|-------------------|
| FR-4.1 | The system shall create user accounts with email | Must Have | POST /api/users creates user; email is unique |
| FR-4.2 | The system shall store user category preferences (likes/dislikes) | Must Have | Preferences stored with weight (-5 to +5) |
| FR-4.3 | The system shall record user interactions with events | Should Have | Views, saves, dismisses tracked per user |
| FR-4.4 | The system shall provide personalized recommendations | Could Have | Recommendations favor liked categories |

### FR-5: User Interface

| ID | Requirement | Priority | Testable Criteria |
|----|-------------|----------|-------------------|
| FR-5.1 | The system shall display a list of upcoming events | Must Have | Homepage shows events with title, date, venue |
| FR-5.2 | The system shall display event details on a dedicated page | Must Have | Clicking event shows full details + source link |
| FR-5.3 | The system shall provide a search interface | Must Have | Search bar accepts text input, returns results |
| FR-5.4 | The system shall provide a chat interface for natural language queries | Should Have | Chat input sends to LLM, displays response |

---

## 3.2 Non-Functional Requirements

### NFR-1: Performance

| ID | Requirement | Measurable Criteria |
|----|-------------|---------------------|
| NFR-1.1 | API response time shall be under 500ms for standard queries | 95th percentile response time < 500ms |
| NFR-1.2 | LLM response time shall be under 3 seconds | 95th percentile LLM response < 3s |
| NFR-1.3 | The system shall support at least 100 concurrent users | Load test with 100 users passes |
| NFR-1.4 | Database queries shall be optimized with appropriate indexes | Explain plans show index usage |

### NFR-2: Reliability

| ID | Requirement | Measurable Criteria |
|----|-------------|---------------------|
| NFR-2.1 | The system shall have 99% uptime during demo periods | Monitoring shows < 1% downtime |
| NFR-2.2 | Scraper failures shall not crash the main application | Backend remains responsive if scraper fails |
| NFR-2.3 | LLM service unavailability shall not block basic event browsing | Events display even if LLM is down |

### NFR-3: Security

| ID | Requirement | Measurable Criteria |
|----|-------------|---------------------|
| NFR-3.1 | API shall use parameterized queries to prevent SQL injection | Code review confirms no string concatenation in queries |
| NFR-3.2 | Sensitive configuration shall be stored in environment variables | No API keys in source code |
| NFR-3.3 | CORS shall be configured to allow only authorized origins | Production CORS restricts to frontend domain |

### NFR-4: Usability

| ID | Requirement | Measurable Criteria |
|----|-------------|---------------------|
| NFR-4.1 | UI shall be responsive on mobile and desktop | Works on screens 320px to 1920px wide |
| NFR-4.2 | Search results shall display within 1 second of submission | User testing confirms perceived responsiveness |
| NFR-4.3 | Error messages shall be user-friendly | No raw error codes shown to users |

### NFR-5: Maintainability

| ID | Requirement | Measurable Criteria |
|----|-------------|---------------------|
| NFR-5.1 | Code shall follow language-specific style guides | Linting passes with zero warnings |
| NFR-5.2 | All public functions shall have documentation comments | Documentation coverage > 80% |
| NFR-5.3 | System shall use modular architecture for easy extension | Adding new scraper requires < 100 lines |

### NFR-6: Ethical/Legal

| ID | Requirement | Measurable Criteria |
|----|-------------|---------------------|
| NFR-6.1 | System shall only scrape publicly available information | No login required to access scraped data |
| NFR-6.2 | System shall link to original sources, not reproduce full content | All events have source_url; descriptions are summaries |
| NFR-6.3 | System shall respect robots.txt directives | Scraper checks robots.txt before scraping |

---

# 4. Architectural Design

## 4.1 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LOCATE918 SYSTEM ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

                              EXTERNAL DATA SOURCES
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ Eventbrite  │     │   Venue     │     │    City     │
    │    API      │     │  Websites   │     │  Calendars  │
    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     RUST BACKEND (Axum) :3000                        │   │
│  │                                                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │   Routes    │  │   Models    │  │  Services   │  │  Scraper   │  │   │
│  │  │             │  │             │  │             │  │  Module    │  │   │
│  │  │ /api/events │  │ Event       │  │ LLM Client  │  │            │  │   │
│  │  │ /api/users  │  │ User        │  │ (HTTP)      │  │ Eventbrite │  │   │
│  │  │ /api/chat   │  │ Preference  │  │             │  │ Venues     │  │   │
│  │  └─────────────┘  └─────────────┘  └──────┬──────┘  └────────────┘  │   │
│  │                                           │                          │   │
│  └───────────────────────────────────────────┼──────────────────────────┘   │
│                                              │                               │
└──────────────────────────────────────────────┼───────────────────────────────┘
                                               │
              ┌────────────────────────────────┼────────────────┐
              │                                │                │
              ▼                                ▼                ▼
┌─────────────────────┐          ┌─────────────────────┐    ┌─────────────────┐
│     PostgreSQL      │          │   PYTHON LLM SVC    │    │ REACT FRONTEND  │
│     DATABASE        │          │   (FastAPI) :8001   │    │                 │
│                     │          │                     │    │  ┌───────────┐  │
│  ┌───────────────┐  │          │  ┌───────────────┐  │    │  │  Event    │  │
│  │    events     │  │          │  │ /parse-intent │  │    │  │  List     │  │
│  ├───────────────┤  │          │  │ /chat         │  │    │  ├───────────┤  │
│  │    users      │  │          │  │ /normalize    │  │    │  │  Search   │  │
│  ├───────────────┤  │          │  └───────┬───────┘  │    │  ├───────────┤  │
│  │  preferences  │  │          │          │          │    │  │  Chat     │  │
│  ├───────────────┤  │          │          ▼          │    │  └───────────┘  │
│  │ interactions  │  │          │  ┌───────────────┐  │    │                 │
│  └───────────────┘  │          │  │ Google Gemini │  │    │                 │
│                     │          │  │     API       │  │    │                 │
└─────────────────────┘          │  └───────────────┘  │    └─────────────────┘
                                 └─────────────────────┘
```

## 4.2 Component Descriptions

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| **Rust Backend** | Rust, Axum | REST API, business logic, database access, scraper orchestration |
| **PostgreSQL** | PostgreSQL 16 | Persistent storage for events, users, preferences, interactions |
| **Python LLM Service** | Python, FastAPI | Natural language processing, Gemini API integration |
| **React Frontend** | React, JavaScript | User interface, event display, search, chat |
| **Scraper Module** | Rust or Python | Event ingestion from external sources |

## 4.3 Data Flow

1. **Event Ingestion Flow:**
    - Scraper fetches data from external sources
    - Raw data sent to LLM service for normalization (optional)
    - Normalized events stored in PostgreSQL

2. **User Search Flow:**
    - User enters query in frontend
    - Frontend calls Rust backend `/api/chat`
    - Backend calls Python LLM service `/api/parse-intent`
    - LLM extracts search parameters
    - Backend queries PostgreSQL with parameters
    - Backend calls LLM service `/api/chat` with results
    - LLM generates conversational response
    - Response returned to frontend

3. **Basic Browse Flow:**
    - Frontend calls `/api/events`
    - Backend queries PostgreSQL
    - Events returned directly (no LLM needed)

---

# 5. System Modeling (UML Diagrams)

## 5.1 Use Case Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOCATE918 SYSTEM                                │
│                                                                              │
│    ┌──────────┐                                          ┌──────────────┐   │
│    │          │                                          │   External   │   │
│    │   User   │                                          │   Sources    │   │
│    │          │                                          │              │   │
│    └────┬─────┘                                          └──────┬───────┘   │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         ├───>│       Browse Events             │                │           │
│         │    └─────────────────────────────────┘                │           │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         ├───>│       Search Events             │                │           │
│         │    └─────────────────────────────────┘                │           │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         ├───>│    Natural Language Search      │◄───────────────┤           │
│         │    └─────────────────────────────────┘                │           │
│         │                    │                                  │           │
│         │                    │ <<includes>>                     │           │
│         │                    ▼                                  │           │
│         │    ┌─────────────────────────────────┐                │           │
│         │    │       Process with LLM          │                │           │
│         │    └─────────────────────────────────┘                │           │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         ├───>│       View Event Details        │                │           │
│         │    └─────────────────────────────────┘                │           │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         ├───>│      Create Account             │                │           │
│         │    └─────────────────────────────────┘                │           │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         ├───>│      Set Preferences            │                │           │
│         │    └─────────────────────────────────┘                │           │
│         │                                                       │           │
│         │    ┌─────────────────────────────────┐                │           │
│         └───>│      Save/Dismiss Event         │                │           │
│              └─────────────────────────────────┘                │           │
│                                                                 │           │
│                                                                 │           │
│    ┌──────────┐  ┌─────────────────────────────┐                │           │
│    │  Admin/  │─>│      Trigger Scraper        │◄───────────────┘           │
│    │  System  │  └─────────────────────────────┘                            │
│    └──────────┘                 │                                           │
│                                 │ <<includes>>                              │
│                                 ▼                                           │
│                  ┌─────────────────────────────┐                            │
│                  │    Normalize Event Data     │                            │
│                  └─────────────────────────────┘                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Use Case Descriptions

| Use Case | Actor | Description |
|----------|-------|-------------|
| Browse Events | User | View list of upcoming events without search |
| Search Events | User | Filter events by keyword or category |
| Natural Language Search | User | Ask questions like "What's happening this weekend?" |
| View Event Details | User | See full event information and link to source |
| Create Account | User | Register with email to enable personalization |
| Set Preferences | User | Indicate liked/disliked event categories |
| Save/Dismiss Event | User | Mark events as interested or not interested |
| Trigger Scraper | System | Initiate event collection from external sources |
| Normalize Event Data | System | Use LLM to standardize scraped data |
| Process with LLM | System | Parse natural language and generate responses |

---

## 5.2 Class Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLASS DIAGRAM                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────┐       ┌───────────────────────────┐
│          Event            │       │          User             │
├───────────────────────────┤       ├───────────────────────────┤
│ - id: UUID                │       │ - id: UUID                │
│ - title: String           │       │ - email: String           │
│ - description: String?    │       │ - name: String?           │
│ - location: String?       │       │ - location_preference: String? │
│ - venue: String?          │       │ - created_at: DateTime    │
│ - source_url: String      │       ├───────────────────────────┤
│ - start_time: DateTime    │       │ + create()                │
│ - end_time: DateTime?     │       │ + get_by_id()             │
│ - category: String?       │       │ + get_profile()           │
│ - created_at: DateTime    │       │ + add_preference()        │
├───────────────────────────┤       │ + record_interaction()    │
│ + create()                │       └───────────┬───────────────┘
│ + get_all()               │                   │
│ + get_by_id()             │                   │ 1
│ + search()                │                   │
└───────────────────────────┘                   │
                                                │
                                    ┌───────────┴───────────┐
                                    │                       │
                                    │ *                     │ *
                    ┌───────────────┴───────┐   ┌──────────┴────────────┐
                    │    UserPreference     │   │   UserInteraction     │
                    ├───────────────────────┤   ├───────────────────────┤
                    │ - id: UUID            │   │ - id: UUID            │
                    │ - user_id: UUID       │   │ - user_id: UUID       │
                    │ - category: String    │   │ - event_id: UUID      │
                    │ - weight: Integer     │   │ - interaction_type: String │
                    │ - created_at: DateTime│   │ - created_at: DateTime│
                    ├───────────────────────┤   ├───────────────────────┤
                    │ + create()            │   │ + create()            │
                    │ + update()            │   │ + get_by_user()       │
                    │ + get_by_user()       │   └───────────┬───────────┘
                    └───────────────────────┘               │
                                                           │ *
                                                           │
                                                           │ 1
                                            ┌──────────────┴──────────────┐
                                            │           Event             │
                                            │      (referenced above)     │
                                            └─────────────────────────────┘


┌───────────────────────────┐       ┌───────────────────────────┐
│       SearchParams        │       │       LlmClient           │
├───────────────────────────┤       ├───────────────────────────┤
│ - query: String?          │       │ - base_url: String        │
│ - category: String?       │       │ - client: HttpClient      │
│ - date_from: String?      │       ├───────────────────────────┤
│ - date_to: String?        │       │ + parse_intent()          │
│ - location: String?       │       │ + generate_response()     │
├───────────────────────────┤       │ + health_check()          │
│ + from_natural_language() │       └───────────────────────────┘
└───────────────────────────┘
```

### Class Relationships

| Relationship | Type | Description |
|--------------|------|-------------|
| User → UserPreference | One-to-Many | A user can have multiple category preferences |
| User → UserInteraction | One-to-Many | A user can have multiple event interactions |
| Event → UserInteraction | One-to-Many | An event can have interactions from multiple users |
| LlmClient → SearchParams | Creates | LLM client parses queries into SearchParams |

---

## 5.3 Sequence Diagram

### Natural Language Search Flow

```
┌──────┐          ┌──────────┐          ┌───────────┐          ┌──────────┐          ┌────────┐
│ User │          │ Frontend │          │  Backend  │          │ LLM Svc  │          │   DB   │
└──┬───┘          └────┬─────┘          └─────┬─────┘          └────┬─────┘          └───┬────┘
   │                   │                      │                     │                    │
   │  "jazz this       │                      │                     │                    │
   │   weekend"        │                      │                     │                    │
   │──────────────────>│                      │                     │                    │
   │                   │                      │                     │                    │
   │                   │  POST /api/chat      │                     │                    │
   │                   │  {message: "..."}    │                     │                    │
   │                   │─────────────────────>│                     │                    │
   │                   │                      │                     │                    │
   │                   │                      │  POST /parse-intent │                    │
   │                   │                      │  {message: "..."}   │                    │
   │                   │                      │────────────────────>│                    │
   │                   │                      │                     │                    │
   │                   │                      │                     │  Call Gemini API   │
   │                   │                      │                     │───────────────────>│
   │                   │                      │                     │<───────────────────│
   │                   │                      │                     │                    │
   │                   │                      │  {params: {         │                    │
   │                   │                      │    category: music, │                    │
   │                   │                      │    date_from: ...}} │                    │
   │                   │                      │<────────────────────│                    │
   │                   │                      │                     │                    │
   │                   │                      │  SELECT * FROM events                    │
   │                   │                      │  WHERE category = 'music'                │
   │                   │                      │  AND start_time >= ...                   │
   │                   │                      │─────────────────────────────────────────>│
   │                   │                      │<─────────────────────────────────────────│
   │                   │                      │  [Event1, Event2, Event3]                │
   │                   │                      │                     │                    │
   │                   │                      │  POST /chat         │                    │
   │                   │                      │  {message, events}  │                    │
   │                   │                      │────────────────────>│                    │
   │                   │                      │                     │                    │
   │                   │                      │                     │  Call Gemini API   │
   │                   │                      │                     │───────────────────>│
   │                   │                      │                     │<───────────────────│
   │                   │                      │                     │                    │
   │                   │                      │  {reply: "I found   │                    │
   │                   │                      │   3 jazz events..."}│                    │
   │                   │                      │<────────────────────│                    │
   │                   │                      │                     │                    │
   │                   │  {reply, events}     │                     │                    │
   │                   │<─────────────────────│                     │                    │
   │                   │                      │                     │                    │
   │  Display response │                      │                     │                    │
   │  and event cards  │                      │                     │                    │
   │<──────────────────│                      │                     │                    │
   │                   │                      │                     │                    │
```

---

## 5.4 Activity Diagram

### Event Discovery Process

```
                                    ┌─────────────┐
                                    │    START    │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  User opens │
                                    │     app     │
                                    └──────┬──────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │  Display event list   │
                               │   (default view)      │
                               └───────────┬───────────┘
                                           │
                                           ▼
                                    ◆─────────────◆
                                   ╱               ╲
                                  ╱  User wants to  ╲
                                 ╱      search?      ╲
                                 ╲                   ╱
                                  ╲                 ╱
                                   ╲               ╱
                                    ◆─────────────◆
                                    │Yes          │No
                        ┌───────────┘             └───────────┐
                        │                                     │
                        ▼                                     ▼
               ┌─────────────────┐                   ┌─────────────────┐
               │  Enter search   │                   │  Browse events  │
               │     query       │                   │    by date      │
               └────────┬────────┘                   └────────┬────────┘
                        │                                     │
                        ▼                                     │
                 ◆─────────────◆                              │
                ╱               ╲                             │
               ╱  Natural lang   ╲                            │
              ╱   or keyword?     ╲                           │
              ╲                   ╱                           │
               ╲                 ╱                            │
                ╲               ╱                             │
                 ◆─────────────◆                              │
                 │NL           │Keyword                       │
      ┌──────────┘             └──────────┐                   │
      │                                   │                   │
      ▼                                   ▼                   │
┌───────────────┐                ┌───────────────┐            │
│ Send to LLM   │                │ Direct DB     │            │
│ parse-intent  │                │ search        │            │
└───────┬───────┘                └───────┬───────┘            │
        │                                │                    │
        ▼                                │                    │
┌───────────────┐                        │                    │
│ Extract       │                        │                    │
│ SearchParams  │                        │                    │
└───────┬───────┘                        │                    │
        │                                │                    │
        ▼                                │                    │
┌───────────────┐                        │                    │
│ Query DB with │                        │                    │
│ parameters    │                        │                    │
└───────┬───────┘                        │                    │
        │                                │                    │
        ├────────────────────────────────┘                    │
        │                                                     │
        ▼                                                     │
┌───────────────┐                                             │
│ Get matching  │◄────────────────────────────────────────────┘
│ events        │
└───────┬───────┘
        │
        ▼
 ◆─────────────◆
╱               ╲
╱  Events found? ╲
╲                ╱
 ╲              ╱
  ◆────────────◆
  │Yes         │No
  │            │
  ▼            ▼
┌────────┐  ┌─────────────────┐
│Display │  │ Show "no events │
│results │  │ found" message  │
└───┬────┘  └────────┬────────┘
    │                │
    ▼                │
◆─────────◆          │
╱  User    ╲         │
╱ clicks    ╲        │
╲ event?    ╱        │
 ╲         ╱         │
  ◆───────◆          │
  │Yes    │No        │
  │       │          │
  ▼       └────┬─────┘
┌─────────┐    │
│ Show    │    │
│ event   │    │
│ details │    │
└────┬────┘    │
     │         │
     ▼         │
┌──────────┐   │
│ Link to  │   │
│ source   │   │
└────┬─────┘   │
     │         │
     └────┬────┘
          │
          ▼
    ┌───────────┐
    │    END    │
    └───────────┘
```

---

# Appendix A: Database Schema

```sql
-- Events table
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    venue TEXT,
    source_url TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    location_preference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User preferences
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    weight INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, category)
);

-- User interactions
CREATE TABLE user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

# Appendix B: API Specification Summary

## Rust Backend (:3000)

| Method | Endpoint | Request Body | Response |
|--------|----------|--------------|----------|
| GET | /api/events | - | Event[] |
| POST | /api/events | CreateEvent | Event |
| GET | /api/events/:id | - | Event |
| GET | /api/events/search | ?q=&category= | Event[] |
| POST | /api/users | CreateUser | User |
| GET | /api/users/:id | - | User |
| GET | /api/users/:id/profile | - | UserProfile |
| POST | /api/users/:id/preferences | CreatePreference | UserPreference |
| POST | /api/users/:id/interactions | CreateInteraction | UserInteraction |
| POST | /api/chat | ChatRequest | ChatResponse |

## Python LLM Service (:8001)

| Method | Endpoint | Request Body | Response |
|--------|----------|--------------|----------|
| GET | /health | - | {status: "healthy"} |
| POST | /api/parse-intent | {message} | {params: SearchParams} |
| POST | /api/chat | {message, events} | {reply} |
| POST | /api/normalize | {events: RawEvent[]} | {events: NormalizedEvent[]} |

---

*Document prepared by Team Locate918*
*Last updated: January 2026*