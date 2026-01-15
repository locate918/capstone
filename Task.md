# Project Tasks

A breakdown of all project tasks organized by phase.

---

## Phase 1: Foundation

### Task 1.1: Project Setup
- [x] Create GitHub repo
- [x] Add README
- [ ] Set up .gitignore
- [ ] Create folder structure (docs/, backend/, frontend/)
- [ ] Add team members as collaborators

### Task 1.2: Documentation
- [ ] Write Problem Statement (Task 1 deliverable)
- [ ] Create initial project timeline/Gantt chart
- [ ] Draft System Requirements Specification (Task 2 deliverable)

---

## Phase 2: Backend Core

### Task 2.1: Rust Backend Scaffolding
- [ ] Initialize Cargo project
- [ ] Set up Axum with basic routes
- [ ] Configure PostgreSQL with Docker
- [ ] Create database migrations

### Task 2.2: Data Models
- [ ] Event model (title, description, date, location, source_url, etc.)
- [ ] Source model (platform name, scrape config)
- [ ] User model (preferences, saved events)

### Task 2.3: Basic API Endpoints
- [ ] GET /api/events (list events)
- [ ] GET /api/events/:id (single event)
- [ ] GET /api/events/search?q= (basic search)

---

## Phase 3: Data Ingestion

### Task 3.1: Scraper Service
- [ ] Research target sources (public calendars, venue sites)
- [ ] Build scraper for one source as proof of concept
- [ ] Store raw event data in database

### Task 3.2: Event Normalization (No LLM yet)
- [ ] Basic field mapping (title, date, location)
- [ ] Deduplication logic
- [ ] Source attribution and linking

---

## Phase 4: Frontend

### Task 4.1: React App Scaffolding
- [ ] Initialize React project (Vite or Create React App)
- [ ] Set up routing
- [ ] Create basic layout/navigation

### Task 4.2: Event UI
- [ ] Event list view
- [ ] Event detail view
- [ ] Basic search bar

---

## Phase 5: LLM Integration

### Task 5.1: Anthropic API Setup
- [ ] Get API key
- [ ] Create LLM service module in Rust
- [ ] Test basic completion calls

### Task 5.2: Event Processing
- [ ] LLM-based summarization of scraped events
- [ ] Category/vibe classification
- [ ] Natural language search

---

## Phase 6: Polish & Deliverables

### Task 6.1: Testing & Refinement
- [ ] Unit tests
- [ ] Integration tests
- [ ] UI polish

### Task 6.2: Documentation & Presentation
- [ ] Architecture diagrams (Task 3 deliverable)
- [ ] Midcourse presentation (Task 4 deliverable)
- [ ] Final demo prep

---

## Capstone Milestone Mapping

| Capstone Task | Project Phase |
|---------------|---------------|
| Task 1: Problem Statement & Timeline | Phase 1 |
| Task 2: System Requirements Specification | Phase 1-2 |
| Task 3: Architectural Design & Modeling | Phase 2-3 |
| Task 4: Midcourse Presentation | Phase 4-5 |
