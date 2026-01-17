# Project Proposal: Event Discovery Aggregator

**Team Name:** TBD  
**Team Coordinator:** TBD  
**Date:** January 2026  
**Course:** Senior Capstone Project - Spring 2026

---

## Project Summary

An AI-powered event aggregator that pulls from multiple public sources, uses an LLM to normalize and summarize event information, and matches users to events through natural language preferences. It links back to original sources rather than reproducing content, driving traffic to organizers while giving users a unified discovery experience.

---

## Problem Statement

Discovering local events is unnecessarily difficult. Event information is scattered across dozens of platforms—Eventbrite, Facebook Events, venue websites, Instagram stories, newsletters, Discord servers, and community boards. Existing solutions like Eventbrite optimize for promoters who pay for visibility, not for attendees seeking relevant experiences. Facebook Events has declined significantly as younger users have left the platform. The result: people routinely miss events they would have attended if they had known about them.

---

## Proposed Solution

A web application (with future mobile support) that:

1. **Aggregates** event data from multiple public sources
2. **Normalizes** inconsistent event information using an LLM
3. **Summarizes** events and answers natural language questions about them
4. **Matches** users to relevant events based on natural language preferences
5. **Links back** to original sources, respecting content ownership

---

## AI/ML Component

| AI Feature | Technology | Purpose |
|------------|------------|---------|
| Event Normalization | LLM (Claude API) | Standardize inconsistent data from varied sources |
| Summarization | LLM (Claude API) | Generate concise, useful event descriptions |
| Natural Language Search | LLM (Claude API) | Allow queries like "outdoor events this weekend, not too crowded" |
| Categorization | LLM (Claude API) | Classify events by vibe, audience, formality beyond simple tags |
| Personalization (stretch) | ML Model | Learn user preferences from interaction patterns |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Rust (Axum framework) |
| Database | PostgreSQL |
| LLM Integration | Anthropic Claude API |
| Frontend | React / JavaScript / HTML / CSS |
| Mobile (future) | Kotlin (Android), Swift (iOS) |

---

## Scope Limitations

To ensure feasibility within one semester:

- Focus on a **single geographic area** (e.g., Stillwater/OSU campus or Tulsa metro)
- Limit initial data sources to **3-5 public platforms**
- Web app MVP first; mobile as stretch goal

---

## Project Timeline Overview

| Phase | Timeframe | Deliverables |
|-------|-----------|--------------|
| Phase 1: Foundation | Weeks 1-2 | Repo setup, documentation, problem statement |
| Phase 2: Backend Core | Weeks 3-4 | API scaffolding, database schema, basic endpoints |
| Phase 3: Data Ingestion | Weeks 5-6 | Scraper for 1-2 sources, event storage |
| Phase 4: Frontend | Weeks 7-8 | React app, event list/detail views, search |
| Phase 5: LLM Integration | Weeks 9-11 | Summarization, natural language search |
| Phase 6: Polish | Weeks 12-14 | Testing, documentation, presentation prep |

---

## Ethical Considerations

- **Web Scraping:** Only publicly posted information; original summaries rather than reproduced content; attribution and linking to sources
- **User Privacy:** Minimal data collection; clear privacy policy
- **Algorithmic Bias:** Analysis of how discovery algorithms might create filter bubbles or exclude communities

---

## Team Members

| Name | Role | Responsibilities |
|------|------|------------------|
| TBD | Coordinator | Communication, organization, backend |
| TBD | TBD | TBD |
| TBD | TBD | TBD |
| TBD | TBD | TBD |

---

## Originality Statement

This project is an original concept developed by the team. It has not been completed, either fully or partially, in any previous coursework or external project.

---

## Contact

**Team Coordinator:** TBD  
**Email:** TBD  
**GitHub Repository:** [link to repo]
