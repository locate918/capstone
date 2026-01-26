# Event Sources for Locate918

## Overview

This document catalogs all event sources for the Tulsa metro area. Sources are categorized by:
- **API** - Structured data, no scraping needed
- **Scraper** - Requires HTML parsing
- **Priority** - MVP (must have) vs Future (nice to have)

---

## Structured APIs (Priority: MVP)

These return clean JSON and should be implemented first.

| Source | Coverage | API Docs | Notes |
|--------|----------|----------|-------|
| **Eventbrite** | Major events, festivals | [API Docs](https://www.eventbrite.com/platform/api) | Free tier available |
| **Bandsintown** | Concerts only | [API Docs](https://artists.bandsintown.com/support/api-installation) | Artist-focused |
| **Ticketmaster** | Large venues (BOK, etc) | [API Docs](https://developer.ticketmaster.com/) | 5000 calls/day free |
| **Songkick** | Concerts | [API Docs](https://www.songkick.com/developer) | Good for smaller venues |

---

## Local Scrapers (Priority: MVP)

No APIs available. Need HTML scraping.

### Tier 1 - Build First

| Source | URL | Event Types | Difficulty |
|--------|-----|-------------|------------|
| **Visit Tulsa** | visitulsa.com/events | All types | Medium |
| **Tulsa World Events** | tulsaworld.com/calendar | All types | Medium |
| **Cain's Ballroom** | cainsballroom.com | Concerts | Easy |

### Tier 2 - Build Next

| Source | URL | Event Types | Difficulty |
|--------|-----|-------------|------------|
| Tulsa PAC | tulsapac.com | Theater, concerts | Medium |
| BOK Center | bokcenter.com | Major concerts, sports | Easy |
| Cox Business Center | coxcentertulsa.com | Expos, conventions | Easy |

---

## Venues by Category

### 🎸 Concert Venues

| Venue | Capacity | Location | Website |
|-------|----------|----------|---------|
| BOK Center | 19,199 | Downtown | bokcenter.com |
| Cain's Ballroom | 1,800 | Downtown | cainsballroom.com |
| Tulsa Theater | 1,200 | Downtown | tulsatheater.com |
| The Vanguard | 700 | Downtown | thevanguardtulsa.com |
| Mercury Lounge | 400 | Downtown | mercuryloungetulsa.com |
| The Shrine | 300 | Downtown | shrineok.com |
| Soundpony | 200 | Downtown | soundpony.com |
| The Colony | 350 | Downtown | thecolonytulsa.com |

### 🎭 Performing Arts

| Venue | Type | Location | Website |
|-------|------|----------|---------|
| Tulsa PAC | Theater, Symphony | Downtown | tulsapac.com |
| Circle Cinema | Independent Film | Downtown | circlecinema.org |
| Tulsa Ballet | Ballet | Brookside | tulsaballet.org |
| Theatre Tulsa | Community Theater | Downtown | theatretulsa.org |
| American Theatre | Historic | Downtown | americantheatretulsa.com |

### 🏟️ Sports Venues

| Venue | Teams/Sports | Location | Website |
|-------|--------------|----------|---------|
| BOK Center | Oilers (hockey) | Downtown | bokcenter.com |
| ONEOK Field | Drillers (baseball) | Downtown | tulsadrillers.com |
| Skelly Stadium | TU Football | TU Campus | tulsahurricane.com |
| Expo Square | Rodeos, Racing | Expo | exposquare.com |

### 👨‍👩‍👧‍👦 Family-Friendly

| Venue | Type | Location | Website |
|-------|------|----------|---------|
| Tulsa Zoo | Zoo | Midtown | tulsazoo.org |
| Gathering Place | Park | Riverside | gatheringplace.org |
| Oklahoma Aquarium | Aquarium | Jenks | okaquarium.org |
| Discovery Lab | Children's Museum | Downtown | discoverylab.org |
| Safari Joe's H2O | Water Park | Tulsa | safarijoes.com |
| Incredible Pizza | Entertainment | Various | incrediblepizza.com |

### 🍺 Nightlife & Bars

| Venue | Type | Location | Website |
|-------|------|----------|---------|
| The Max | Retro Bar | Downtown | themaxretropub.com |
| Inner Circle Vodka Bar | Craft Cocktails | Downtown | innercirclevodkabar.com |
| Valkyrie | Cocktail Lounge | Downtown | valkyrietulsa.com |
| Hodges Bend | Wine Bar | Downtown | hodgesbend.com |
| Roosevelt's | Gastropub | Cherry Street | rooseveltstulsa.com |
| McNellie's | Irish Pub | Downtown | mcnellies.com |
| Arnie's Bar | Dive Bar | Downtown | arniesbar.com |

### 😂 Comedy

| Venue | Type | Location | Website |
|-------|------|----------|---------|
| Loony Bin | Comedy Club | Downtown | loonybincomedy.com |
| The Fur Shop | Variety | Downtown | thefurshop.com |

### 🍽️ Food & Drink Events

| Source | Event Types | Location |
|--------|-------------|----------|
| Cherry Street Farmers Market | Markets | Cherry Street |
| Kendall Whittier Market | Markets | Kendall Whittier |
| Mother Road Market | Food Hall Events | Route 66 |
| Tulsa Food Tours | Tours | Various |

---

## Suburban Coverage

### Broken Arrow
| Source | URL | Notes |
|--------|-----|-------|
| Visit Broken Arrow | visitbrokenarrow.com | City events |
| BA Performing Arts | brokenarrowpac.com | Theater |
| Central Park | baparks.org | Outdoor events |

### Jenks
| Source | URL | Notes |
|--------|-----|-------|
| Oklahoma Aquarium | okaquarium.org | Family events |
| Jenks Riverwalk | jenksriverwalk.com | Festivals |

### Owasso
| Source | URL | Notes |
|--------|-----|-------|
| Owasso Community Center | owassops.org | Local events |
| Redbud Festival | rebudfestival.org | Annual festival |

### Bixby
| Source | URL | Notes |
|--------|-----|-------|
| Bixby Community Center | bixbyok.gov | Local events |
| Green Corn Festival | bixbychamber.com | Annual festival |

### Sand Springs
| Source | URL | Notes |
|--------|-----|-------|
| Case Community Center | sandspringsok.org | Events |
| Herbal Affair | herbalaffair.org | Annual festival |

### Sapulpa
| Source | URL | Notes |
|--------|-----|-------|
| Sapulpa Main Street | sapulpamainstreet.com | Downtown events |
| Route 66 Blowout | sapulpaok.gov | Annual festival |

### Claremore
| Source | URL | Notes |
|--------|-----|-------|
| Will Rogers Memorial | willrogers.com | Museum events |
| Claremore Expo | claremorecity.com | Rodeos |

---

## Aggregator Sites

These compile events from multiple sources:

| Site | URL | Notes |
|------|-----|-------|
| Visit Tulsa | visitulsa.com/events | Official tourism |
| Tulsa World | tulsaworld.com/calendar | Newspaper |
| Tulsa People | tulsapeople.com | Magazine |
| What's Up Tulsa | facebook.com/groups/whatuptulsa | Community |
| Do918 | do918.com | Event discovery |

---

## Implementation Priority

### MVP (Week 1-2)
1. ✅ Eventbrite API
2. ✅ Bandsintown API  
3. ✅ Visit Tulsa scraper
4. ✅ Cain's Ballroom scraper
5. ✅ Tulsa World scraper

### Phase 2 (Week 3-4)
1. Ticketmaster API
2. BOK Center scraper
3. Tulsa PAC scraper
4. Gathering Place scraper

### Phase 3 (Week 5+)
1. Suburban sources
2. Smaller venue scrapers
3. Facebook Events integration
4. Community submissions

---

## Scraping Notes

### Rate Limiting
- Be respectful: 1 request per second max
- Cache responses for 1 hour minimum
- Use appropriate User-Agent

### Legal Considerations
- Always link back to source
- Don't store full content, just metadata
- Check robots.txt before scraping
- APIs are always preferred over scraping

### Data Quality
- Deduplicate by source_url (UNIQUE constraint)
- Normalize venue names
- Validate dates (reject past events)
- Flag missing required fields
