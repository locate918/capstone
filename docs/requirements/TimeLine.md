# Project Timeline

## Gantt Chart (Parallel Workflow)
```mermaid
gantt
    title Event Discovery Aggregator - Spring 2026
    dateFormat YYYY-MM-DD
    
    section Foundation
    Repo Setup & Docs           :p1a, 2026-01-13, 7d
    Problem Statement           :p1b, 2026-01-16, 5d
    Requirements Doc            :p1c, 2026-01-21, 7d
    
    section Coordinator
    Backend Scaffolding         :c1, 2026-01-20, 5d
    Database Schema             :c2, 2026-01-25, 4d
    API Endpoints               :c3, 2026-01-29, 7d
    API Refinement              :c4, 2026-02-05, 5d
    Code Review & Support       :c5, 2026-02-10, 30d
    
    section Data Engineer
    Research Sources            :d1, 2026-01-20, 7d
    Scraper Architecture        :d2, 2026-01-27, 5d
    Scraper Prototype           :d3, 2026-02-01, 7d
    Integrate with DB           :d4, 2026-02-08, 7d
    Additional Scrapers         :d5, 2026-02-15, 14d
    Deduplication Logic         :d6, 2026-03-01, 7d
    
    section AI Engineer
    Claude API Research         :a1, 2026-01-20, 7d
    Prompt Prototyping          :a2, 2026-01-27, 10d
    LLM Service Module          :a3, 2026-02-06, 7d
    Summarization               :a4, 2026-02-13, 10d
    NL Search                   :a5, 2026-02-23, 14d
    Prompt Refinement           :a6, 2026-03-09, 14d
    
    section Frontend Dev
    Wireframes & Mockups        :f1, 2026-01-20, 7d
    React Setup                 :f2, 2026-01-27, 4d
    UI Components               :f3, 2026-01-31, 10d
    Connect to API              :f4, 2026-02-10, 7d
    Search UI                   :f5, 2026-02-17, 7d
    NL Search UI                :f6, 2026-02-24, 7d
    UI Polish                   :f7, 2026-03-03, 14d
    
    section Full Stack QA
    CI CD Setup                 :q1, 2026-01-20, 5d
    Testing Framework           :q2, 2026-01-25, 7d
    API Contract OpenAPI        :q3, 2026-02-01, 5d
    Integration Tests           :q4, 2026-02-06, 37d
    Documentation               :q5, 2026-03-01, 21d
    
    section Final
    Testing Sprint              :p6a, 2026-04-01, 10d
    Documentation Final         :p6b, 2026-04-11, 7d
    Presentation Prep           :p6c, 2026-04-18, 6d
```

## Parallel Work Summary

| Week | Coordinator - Will | Data Engineer - Skylar | AI/LLM Engineer - Ben | Frontend Dev - Malachi | Full Stack/QA - Jordi |
|------|-------------|---------------|-----------------|--------------|---------------|
| 1-2 | Docs + Start backend | Docs + Research sources | Docs + Claude research | Docs + Wireframes | Docs + CI/CD |
| 3-4 | DB schema + API endpoints | Scraper architecture + prototype | Prompt prototyping | React setup + mock UI | Testing framework + OpenAPI spec |
| 5-6 | API refinement | Integrate scrapers with DB | LLM service module | Connect UI to API | Integration tests |
| 7-8 | Support + review | Additional scrapers | Summarization | Search UI | Documentation |
| 9-10 | Support + review | Deduplication | NL search | NL search UI | Bug fixes |
| 11-12 | Support + review | Polish | Prompt refinement | UI polish | Documentation |
| 13-14 | Presentation | Presentation | Presentation | Presentation | Presentation |

## Milestone Checkpoints

| Date | Milestone | Who Presents |
|------|-----------|--------------|
| Jan 23 | Problem Statement & Timeline | Coordinator |
| Feb 7 | System Requirements Spec | All |
| Feb 14 | Backend API Demo | Coordinator |
| Feb 21 | Scraper Demo | Data Engineer |
| Mar 1 | Architecture Design Doc | All |
| Mar 7 | Frontend Demo | Frontend Dev |
| Mar 15 | Midcourse Presentation | All |
| Mar 21 | LLM Integration Demo | AI Engineer |
| Apr 10 | Feature Complete | All |
| Apr 24 | Final Presentation | All |

## Risk Mitigation

| Risk | Mitigation | Owner |
|------|------------|-------|
| Backend delays block everyone | OpenAPI spec + mock data enables parallel work | Full Stack |
| Scraper sources change or break | Build 3-5 scrapers, only need 2 working | Data Engineer |
| LLM responses unpredictable | Start prompt engineering early, iterate | AI Engineer |
| Integration issues | Weekly integration checkpoints | Full Stack |
| Scope creep | MVP first, stretch goals documented separately | Coordinator |
