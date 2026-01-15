# locate918
# Event Discovery Aggregator

An AI-powered event aggregator that pulls from multiple public sources, uses an LLM to normalize and summarize event information, and matches users to events through natural language preferences. It links back to original sources rather than reproducing content, driving traffic to organizers while giving users a unified discovery experience.

---

## Table of Contents

- [Product Vision](#product-vision)
- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Development Methodology](#development-methodology)
- [Team](#team)
- [License](#license)

---

## Product Vision

**For** people looking for local events  
**Who** are frustrated by scattered, incomplete, and algorithm-gated event information  
**The** Event Discovery Aggregator  
**Is a** mobile application  
**That** unifies event data from multiple sources and uses AI to provide personalized, natural language search  
**Unlike** Eventbrite or Facebook Events which optimize for promoters  
**Our product** optimizes for attendees, surfacing relevant events without requiring users to check multiple platforms

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Rust (Axum) |
| Database | PostgreSQL |
| LLM Integration | Anthropic Claude API |
| Mobile (Android) | Kotlin / Jetpack Compose |
| Mobile (iOS) | Swift (future) |

---

## Architecture Overview
```mermaid
flowchart TB
    subgraph Data Sources
        A1[Eventbrite API]
        A2[Public Calendars]
        A3[Venue Websites]
    end
    
    subgraph Backend
        B[Axum REST API]
        C[Scraper / Ingestion Service]
        D[LLM Service]
        E[(PostgreSQL)]
    end
    
    subgraph Client
        F[Android App]
    end
    
    A1 --> C
    A2 --> C
    A3 --> C
    C --> E
    C --> D
    D --> E
    F <-->|HTTPS| B
    B --> E
    B --> D
```

---

## Project Structure
```
event-discovery/
├── README.md
├── docs/
│   ├── requirements/
│   │   └── system-requirements.md
│   ├── design/
│   │   ├── architecture.md
│   │   └── uml-diagrams.md
│   ├── reports/
│   │   └── sprint-reports/
│   └── meeting-notes/
├── backend/
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs
│   │   ├── routes/
│   │   ├── models/
│   │   ├── services/
│   │   └── scraper/
│   └── migrations/
├── android/
│   └── app/
└── .gitignore
```

---

## Getting Started

### Prerequisites

- Rust (latest stable)
- Docker (for PostgreSQL)
- Android Studio (for mobile development)
- Anthropic API key

### Backend Setup
```bash
# Start PostgreSQL
docker run --name event-discovery-db \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=event_discovery \
  -p 5432:5432 -d postgres:16

# Navigate to backend
cd backend

# Create .env file
echo "DATABASE_URL=postgres://postgres:password@localhost:5432/event_discovery" > .env
echo "ANTHROPIC_API_KEY=your_key_here" >> .env

# Run the server
cargo run
```

### Android Setup

1. Open `android/` folder in Android Studio
2. Sync Gradle
3. Run on emulator or device

---

## Development Methodology

- **Framework:** Agile/Scrum with 2-week sprints
- **Documentation:** UML diagrams for system design
- **Version Control:** GitHub with feature branches
- **CI/CD:** TBD

### Sprint Milestones

| Sprint | Goals |
|--------|-------|
| 1 | Backend scaffolding, database schema, basic API endpoints |
| 2 | Event ingestion pipeline, initial scraper |
| 3 | LLM integration for normalization and summarization |
| 4 | Android app scaffolding, event list UI |
| 5 | Natural language search, user preferences |
| 6 | Polish, testing, documentation |

---

## Capstone Deliverables

- [ ] **Task 1:** Problem Statement and Initial Project Timeline
- [ ] **Task 2:** System Requirements Specification
- [ ] **Task 3:** Architectural Design and System Modeling
- [ ] **Task 4:** Midcourse Project Presentation

---

## Team

| Name | Role |
|------|------|
| TBD | TBD |
| TBD | TBD |
| TBD | TBD |
| TBD | TBD |

---

## Ethical Considerations

- **Web Scraping:** Focuses on publicly posted information; generates original summaries rather than reproducing content; links back to sources
- **User Privacy:** Clear data policies; minimal data collection
- **Algorithmic Bias:** Analysis of how discovery algorithms might create filter bubbles or exclude communities

---

## License

TBD
