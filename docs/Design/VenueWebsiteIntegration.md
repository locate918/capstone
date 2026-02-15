# Venue Website Integration Guide

## Summary
This update adds venue website links to event cards, so users can click directly to venue websites (like cainsballroom.com) instead of just the aggregator pages (like visittulsa.com).

## Files to Update

### 1. Backend: `events.rs`
Replace your current `events.rs` with `events_with_venue_website.rs`

**Key Changes:**
- Added `venue_website: Option<String>` to the Event struct
- All queries now use LEFT JOIN to get venue website:
```sql
SELECT e.*, v.website AS venue_website
FROM events e
LEFT JOIN venues v ON LOWER(TRIM(e.venue)) = LOWER(TRIM(v.name))
```

### 2. Frontend: `api.js`
Update the `transformBackendEvents` function to include venue_website:

```javascript
// In api.js, update transformBackendEvents function
const transformBackendEvents = (backendEvents) => {
  return backendEvents.map(event => ({
    id: event.id,
    title: event.title,
    summary: event.description?.substring(0, 200) || '',
    location: event.venue || event.location || 'Tulsa',
    date_iso: event.start_time,
    imageUrl: event.image_url || '/placeholder-event.jpg',
    original_url: event.source_url,      // VisitTulsa/aggregator page
    venue_website: event.venue_website,   // NEW: Actual venue website
    originalSource: event.source_name,
    vibe_tags: event.categories?.slice(0, 3) || [],
    categories: event.categories || [],
    price_min: event.price_min,
    price_max: event.price_max,
    outdoor: event.outdoor,
    family_friendly: event.family_friendly,
  }));
};
```

### 3. Frontend: `EventCard.js`
Replace with the new version that shows two buttons:
- **"Venue"** (gold) → Opens venue's actual website
- **"Info"** (subtle) → Opens aggregator page with event details

### 4. Database: Run venue website updates
Execute `update_venue_websites.sql` in Supabase SQL Editor to populate venue websites.

## Testing
1. Run the SQL updates
2. Rebuild/restart backend
3. Refresh frontend
4. Event cards should now show "Venue" button for events at venues with websites

## Button Behavior

| Has venue_website | Has source_url | Shows                    |
|-------------------|----------------|--------------------------|
| ✓                 | ✓              | "Venue" + "Info" buttons |
| ✓                 | ✗              | "Venue" button only      |
| ✗                 | ✓              | "Info" button only       |
| ✗                 | ✗              | Vibe tags (fallback)     |

## Why Two Links?
- **Venue website**: For general venue info, directions, other events
- **Source URL (Info)**: For THIS specific event - tickets, exact times, registration