# Production Meeting Log

Weekly meeting summaries for the Locate918 team.

---

## Meeting Template

Copy this for each new meeting:
```
### Week [Date]

**Attendees:** 

**Duration:** 

#### Progress Since Last Meeting
- 

#### Blockers / Issues
- 

#### Decisions Made
- 

#### Action Items
| Task | Owner | Due Date |
|------|-------|----------|
|  |  |  |

#### Notes
- We have decided to make a hybrid search engine featuring an AI interface that will power the search or double as a chat bot when needed.

---
```

---

## Meetings

### Week 1 - January 16, 2026

**Attendees:** Will, Ben, Skylar, Malachi.....Abe, lol

**Duration:** 

#### Progress Since Last Meeting
- Project repo created
- Backend scaffolding complete (Rust/Axum)
- PostgreSQL database running
- Basic API endpoint working (GET /api/events)
- Documentation in place (README, TASKS, TIMELINE)

#### Blockers / Issues
- None

#### Decisions Made
- Established team roles:
  - **Will** - Coordinator / Backend Lead
  - **Ben** - AI/LLM Engineer
  - **Skylar** - Data Engineer
  - **Malachi** - Frontend Developer
  - **Jordi** - Full Stack / QA
- Each member will focus on development docs for their respective role
- Next meeting scheduled for Sunday, January 25

#### Action Items
| Task | Owner | Due Date |
|------|-------|----------|
| Backend development docs | Will | Jan 25 |
| AI/LLM integration research & docs | Ben | Jan 25 |
| Data scraping research & docs | Skylar | Jan 25 |
| Frontend architecture docs | Malachi | Jan 25 |
| QA strategy & CI/CD docs | Jordi | Jan 25 |

#### Notes
- Team kickoff successful
- All members assigned and clear on responsibilities

---

### January 25, 2025

**Attendees: Will ,Ben, Skylar, Malachi, Jordi** 

**Duration: start 6:30 end ** 

#### Progress Since Last Meeting
- Api is built * changes to the database structure- normalize first
- FrontEnd- Mock up in production
- LLm structure is started
- Jordi has created a testing CI pipeline- once scrapers are built we can begin testing.
- Timline and requirements. Still need UML charts

#### Blockers / Issues
- Need to make sure the API normalizes the data before storing it in the database
- find a rust library that can map python for the scrapers


#### Decisions Made
- Skylar to look into Rust language for scraper logic. 
- Application will be search engine based with a generative AI element. 
- Will look inot gemini free plan vs claude for token costs. 

#### Action Items
| Task | Owner | Due Date |
|------|-------|----------|
| Will | Update backend for normalizing data |  2/1/26 |
| Malachi | Continue developing frontend features, UML design docs/user stories/requirements | 2/15/26 |
| Jordi | UML designs/requirements docs/testing pipeline | 2/15/26 |
| Ben | UML design, Begin research into AI API needs for Gemini/Claude | 2/15/26
| Skylar | UML design, Find free API keys for EventBrite, and other large search engines, begin developing scrapers | 2/15/26 |


#### Notes
Create AI powered search engine along with chatbot

---
