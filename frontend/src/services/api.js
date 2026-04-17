// =============================================================================
// API Configuration
// =============================================================================

import { supabase } from "../lib/supabaseClient";

// Backend URLs - adjust based on environment
// CRA uses process.env.REACT_APP_*
const RUST_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:3000";
const LLM_SERVICE_URL = process.env.REACT_APP_LLM_SERVICE_URL || "http://localhost:8001";

// Set to false to use real APIs
const USE_MOCKS = process.env.REACT_APP_USE_MOCKS === "true";

// =============================================================================
// AGGREGATOR BLOCKLIST
// =============================================================================

/**
 * Domains we treat as low-trust aggregators.
 * Any event whose best known URL comes from one of these will have its
 * original_url suppressed in the UI — the Venue button still works via
 * venue_website, but the "Info / View Listing" button won't route users
 * back to BIT / Visit Tulsa / Eventbrite.
 */
const AGGREGATOR_DOMAINS = [
    'visittulsa.com',
    'bit918.com',
    'do918.com',
    'eventbrite.com',
    'eventbrite.co.uk',
    'evbuc.com',
    'allevents.in',
    'events.com',
    'eventful.com',
    'meetup.com',
    'facebook.com',
];

const isAggregatorUrl = (url) => {
    if (!url) return false;
    try {
        const hostname = new URL(url).hostname.replace(/^www\./, '');
        return AGGREGATOR_DOMAINS.some(d => hostname === d || hostname.endsWith('.' + d));
    } catch {
        return false;
    }
};

// =============================================================================
// CATEGORY DEFINITIONS
// =============================================================================

/**
 * Master category list with keywords for flexible matching.
 * Each category has related terms that will map to it.
 */
const CATEGORY_KEYWORDS = {
    // Music — live performances, concerts, bands, DJ sets
    music: ['music', 'concert', 'live music', 'band', 'singer', 'dj', 'jazz', 'rock', 'country', 'hip hop', 'rap', 'classical', 'orchestra', 'choir', 'karaoke', 'open mic', 'acoustic', 'blues', 'folk', 'indie', 'metal', 'punk', 'edm', 'electronic', 'r&b', 'soul', 'gospel', 'reggae', 'bluegrass', 'tribute'],

    // Comedy — stand-up, improv, sketch, comedy shows
    comedy: ['comedy', 'comedian', 'stand-up', 'standup', 'improv', 'sketch', 'funny', 'humor', 'laugh', 'comic', 'roast'],

    // Arts & Theater — theater, ballet, opera, symphony, visual arts, galleries
    art: ['theater', 'theatre', 'ballet', 'opera', 'symphony', 'orchestra', 'dance', 'musical', 'play', 'gallery', 'exhibit', 'exhibition', 'painting', 'sculpture', 'photography', 'art show', 'performing arts', 'drag', 'burlesque', 'circus', 'magic'],

    // Festival — multi-day or large outdoor celebrations
    festival: ['festival', 'fest', 'oktoberfest', 'mayfest', 'rocklahoma', 'carnival', 'celebration', 'street festival', 'culture fest', 'block party', 'heritage', 'irish fest', 'tulsa tough'],

    // Film — movies, screenings, cinema events
    film: ['film', 'movie', 'cinema', 'screening', 'documentary', 'indie film', 'film festival', 'drive-in', 'premiere'],

    // Food & Drink — food events, tastings, dining, brewery, wine, cocktails
    food: ['food', 'dining', 'restaurant', 'culinary', 'chef', 'cooking', 'tasting', 'wine', 'beer', 'brewery', 'distillery', 'cocktail', 'brunch', 'dinner', 'food truck', 'farmers market', 'baking', 'dessert', 'coffee', 'whiskey', 'spirits'],

    // Nightlife — bar events, club nights, late-night, 21+
    nightlife: ['nightlife', 'bar', 'club night', 'dj set', 'dance party', 'late night', '21+', 'lounge', 'happy hour', 'trivia night', 'pub crawl', 'karaoke night'],

    // Sports & Fitness — athletic events, fitness classes, races, games
    sports: ['sport', 'sports', 'game', 'match', 'tournament', 'league', 'football', 'basketball', 'baseball', 'soccer', 'hockey', 'wrestling', 'boxing', 'mma', 'racing', 'cycling', 'bike', 'run', 'marathon', '5k', '10k', 'yoga', 'fitness', 'workout', 'gym', 'pilates', 'wellness', 'meditation', 'swim', 'tennis', 'golf', 'rodeo', 'esports'],

    // Family — kids/all-ages events, storytime, children's programming
    family: ['family', 'kid', 'kids', 'children', 'child', 'all ages', 'youth', 'teen', 'toddler', 'baby', 'storytime', 'puppet', 'playground', 'family-friendly'],

    // Educational — lectures, workshops, library programs, museums
    educational: ['educational', 'education', 'history', 'historical', 'museum', 'lecture', 'workshop', 'class', 'seminar', 'tour', 'exhibit', 'science', 'library', 'book', 'reading', 'author', 'learning', 'school', 'university', 'heritage'],

    // Nature & Outdoors — parks, hiking, wildlife, outdoor recreation
    nature: ['nature', 'outdoor', 'outdoors', 'park', 'garden', 'hiking', 'trail', 'camping', 'wildlife', 'bird', 'fishing', 'lake', 'river', 'kayak', 'botanical', 'zoo', 'aquarium', 'farm', 'ranch', 'picnic'],

    // Community — markets, nonprofits, fundraisers, neighborhood events
    community: ['community', 'market', 'vendor', 'nonprofit', 'fundraiser', 'charity', 'volunteer', 'neighborhood', 'tradeshow', 'expo', 'bazaar', 'flea market', 'antique', 'artisan', 'craft fair', 'pop-up', 'handmade', 'auction'],
};

// Attach Supabase access token when available so backend can verify identity.
const authedFetch = async (url, options = {}) => {
    let token = null;
    try {
        const { data } = await supabase.auth.getSession();
        token = data?.session?.access_token ?? null;
    } catch (error) {
        console.warn("Supabase session unavailable. Continuing without auth header.");
    }
    const headers = {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    return fetch(url, { ...options, headers });
};

// =============================================================================
// Events API (Rust Backend :3000)
// =============================================================================

/**
 * Fetch all upcoming events from the backend.
 * Called on initial page load.
 */
export const fetchEvents = async () => {
    if (USE_MOCKS) {
        return getMockEvents();
    }

    try {
        // Request up to 2000 events (backend max)
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/events?limit=2000`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const events = await response.json();
        return transformBackendEvents(events);
    } catch (error) {
        console.error("Failed to fetch events:", error);
        return [];
    }
};

/**
 * Search events with filters.
 * Used when Header dropdown filters are applied.
 */
export const searchEvents = async (params = {}) => {
    if (USE_MOCKS) {
        return getMockEvents();
    }

    try {
        const queryString = new URLSearchParams(
            Object.entries(params).filter(([_, v]) => v != null)
        ).toString();

        const response = await authedFetch(`${RUST_BACKEND_URL}/api/events/search?${queryString}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const events = await response.json();
        return transformBackendEvents(events);
    } catch (error) {
        console.error("Failed to search events:", error);
        return [];
    }
};

/**
 * Fetch personalized event recommendations based on user preference weights.
 * Only available for authenticated users. Events are ranked by preference match.
 */
export const fetchRecommendedEvents = async () => {
    if (USE_MOCKS) {
        return getMockEvents();
    }

    try {
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/users/me/recommendations?limit=2000`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const events = await response.json();
        return transformBackendEvents(events);
    } catch (error) {
        console.error("Failed to fetch recommended events:", error);
        return [];
    }
};

// =============================================================================
// Smart Search API (Python LLM Service :8001)
// =============================================================================

/**
 * Smart search using natural language.
 * Parses query like "jazz concerts under $30" and returns matching events.
 */
export const smartSearch = async (query) => {
    if (USE_MOCKS) {
        return { events: getMockEvents(), parsed: { query } };
    }

    try {
        const response = await authedFetch(`${LLM_SERVICE_URL}/api/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return {
            events: transformBackendEvents(data.events || []),
            parsed: data.parsed || data.parsed_params || {},
        };
    } catch (error) {
        console.error("Smart search failed:", error);
        // Fallback to basic search
        return { events: await searchEvents({ q: query, limit: 500 }), parsed: { query } };
    }
};

// =============================================================================
// Chat API (Python LLM Service :8001 - Tully)
// =============================================================================

/**
 * Send a chat message to Tully.
 * Returns a conversational response with optional event recommendations.
 * Supports streaming for progress updates via an optional onProgress callback.
 */
export const chatWithTully = async (message, userId = null, conversationHistory = [], onProgress = null) => {
    if (USE_MOCKS) {
        return getMockChatResponse(message);
    }

    try {
        const response = await authedFetch(`${LLM_SERVICE_URL}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                user_id: userId,
                conversation_history: conversationHistory,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let result = { message: "", events: [], conversationId: null };
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            
            // Keep the last partial line in the buffer
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        
                        if (data.status && onProgress) {
                            onProgress(data.status);
                        }
                        
                        if (data.message) {
                            result.message = data.message;
                        }

                        if (data.events) {
                            result.events = transformBackendEvents(data.events);
                        }

                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        console.error("Error parsing SSE chunk:", e, line);
                    }
                }
            }
        }

        return result;
    } catch (error) {
        console.error("Chat failed:", error);
        return {
            message: "I'm having trouble connecting right now. Please try again in a moment.",
            events: [],
            conversationId: null,
        };
    }
};

// =============================================================================
// Data Transformation
// =============================================================================

/**
 * Strip HTML tags and decode HTML entities from description text.
 * Safety net for data that was scraped before the scraper fix.
 */
const cleanHtml = (text) => {
    if (!text) return "";
    // Pass 1: decode HTML entities (&lt;p&gt; → <p>)
    const decoded = new DOMParser().parseFromString(text, "text/html").body.textContent || "";
    // Pass 2: strip actual HTML tags (<p> → clean text)
    const clean = new DOMParser().parseFromString(decoded, "text/html").body.textContent || "";
    // Pass 3: trim trailing truncation artifacts (& , - , etc.)
    const cleanedText = clean.replace(/[\s&\-,;:]+$/, '').trim();

    // Truncate to desired max length (e.g., 500 chars) and add ellipsis
    const MAX_LENGTH = 500;
    return cleanedText.length > MAX_LENGTH ? cleanedText.slice(0, MAX_LENGTH) + '…' : cleanedText;
};

/**
 * Transform backend event format to frontend format.
 * Maps database fields to what the UI components expect.
 *
 * Coordinates come from the venues table via LEFT JOIN in the backend.
 * Events at venues without geocoded coordinates will have null coordinates
 * and won't show map pins (but still appear in list/search results).
 */
const transformBackendEvents = (events) => {
    return events.map((event) => ({
        id: event.id,
        title: event.title,
        summary: cleanHtml(event.description),
        date_iso: event.start_time,
        location: event.venue || event.location || "TBA",
        venue_address: event.venue_address,
        venue_website: event.venue_website,
        venue_priority: event.venue_priority ?? 3,
        categories: event.categories || [],
        imageUrl: event.image_url || getDefaultImage(event.categories, event.title, event.description),
        vibe_tags: mapCategoriesToVibes(event.categories, event.title, event.description),
        original_url: (() => {
            // Prefer canonical_url (set only by direct venue/ticketing sources).
            // Fall back to source_url. Suppress entirely if the best URL we have
            // is still an aggregator — the Venue button covers that case.
            const best = event.canonical_url || event.source_url;
            return isAggregatorUrl(best) ? null : best;
        })(),
        originalSource: event.source_name,
        price_min: event.price_min,
        price_max: event.price_max,
        outdoor: event.outdoor,
        family_friendly: event.family_friendly,
        // Use real coordinates from venues table, null if not geocoded
        coordinates: (event.venue_latitude && event.venue_longitude)
            ? { lat: event.venue_latitude, lng: event.venue_longitude }
            : null,
        ai_analysis: {
            noise_level: event.outdoor ? "Medium (Outdoor)" : "Medium",
            networking_pressure: "Medium",
            crowd_type: event.categories?.[0] || "General",
        },
        common_questions: [],
    }));
};

/**
 * Detect category from text using keyword matching.
 * Returns the best matching category or null.
 */
const detectCategoryFromText = (text) => {
    if (!text) return null;
    const lowerText = text.toLowerCase();

    for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
        for (const keyword of keywords) {
            if (lowerText.includes(keyword)) {
                return category;
            }
        }
    }
    return null;
};

/**
 * Map backend categories to frontend display labels.
 * Uses flexible keyword matching to broaden category detection.
 */
const mapCategoriesToVibes = (categories, title = '', description = '') => {
    const results = new Set();

    // First, try to match from explicit categories
    if (categories && categories.length > 0) {
        for (const cat of categories) {
            const lowerCat = cat.toLowerCase();

            // Check if category matches any of our keywords
            for (const [mainCategory, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
                if (keywords.some(kw => lowerCat.includes(kw) || kw.includes(lowerCat))) {
                    results.add(formatCategoryLabel(mainCategory));
                    break;
                }
            }

            // If no match found, add the original category capitalized
            if (results.size === 0) {
                results.add(cat.charAt(0).toUpperCase() + cat.slice(1));
            }
        }
    }

    // If no categories found, try to detect from title and description
    if (results.size === 0) {
        const titleCategory = detectCategoryFromText(title);
        if (titleCategory) results.add(formatCategoryLabel(titleCategory));

        const descCategory = detectCategoryFromText(description);
        if (descCategory && results.size === 0) results.add(formatCategoryLabel(descCategory));
    }

    // Default fallback
    if (results.size === 0) {
        results.add("General");
    }

    return Array.from(results).slice(0, 3); // Max 3 tags
};

/**
 * Format category key to display label.
 */
const formatCategoryLabel = (category) => {
    const labels = {
        music: "Music",
        comedy: "Comedy",
        art: "Arts & Theater",
        festival: "Festival",
        film: "Film",
        food: "Food & Drink",
        nightlife: "Nightlife",
        sports: "Sports & Fitness",
        family: "Family",
        educational: "Educational",
        nature: "Nature & Outdoors",
        community: "Community",
    };
    return labels[category] || category.charAt(0).toUpperCase() + category.slice(1);
};

/**
 * Get a default image based on event category.
 * Uses keyword matching for flexible detection.
 */
const getDefaultImage = (categories, title = '', description = '') => {
    const imageMap = {
        music: "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
        nature: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80",
        educational: "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=800&q=80",
        film: "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=800&q=80",
        art: "https://images.unsplash.com/photo-1547826039-bfc35e0f1ea8?auto=format&fit=crop&w=800&q=80",
        food: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=800&q=80",
        shopping: "https://images.unsplash.com/photo-1555529669-e69e7aa0ba9a?auto=format&fit=crop&w=800&q=80",
        pets: "https://images.unsplash.com/photo-1587300003388-59208cc962cb?auto=format&fit=crop&w=800&q=80",
        fitness: "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&w=800&q=80",
        comedy: "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?auto=format&fit=crop&w=800&q=80",
        family: "https://images.unsplash.com/photo-1536640712-4d4c36ff0e4e?auto=format&fit=crop&w=800&q=80",
        sports: "https://images.unsplash.com/photo-1461896836934-28e4c40e7d5c?auto=format&fit=crop&w=800&q=80",
    };

    // Try to match from explicit categories first
    if (categories && categories.length > 0) {
        for (const cat of categories) {
            const lowerCat = cat.toLowerCase();
            for (const [mainCategory, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
                if (keywords.some(kw => lowerCat.includes(kw) || kw.includes(lowerCat))) {
                    return imageMap[mainCategory];
                }
            }
        }
    }

    // Try to detect from title/description
    const detectedCategory = detectCategoryFromText(title) || detectCategoryFromText(description);
    if (detectedCategory && imageMap[detectedCategory]) {
        return imageMap[detectedCategory];
    }

    // Default fallback
    return "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=800&q=80";
};

// =============================================================================
// Mock Data (for development without backend)
// =============================================================================

const getMockEvents = () => [
    {
        id: "1",
        title: "Founders Lounge @ The Mayo",
        summary: "Exclusive networking for local tech founders and angel investors.",
        date_iso: "2026-02-14T19:00:00",
        location: "The Mayo Hotel, Downtown",
        coordinates: { lat: 36.152, lng: -95.9905 },
        imageUrl: "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=800&q=80",
        vibe_tags: ["Educational", "Food & Drink"],
        original_url: "#",
        originalSource: "Tulsa Remote",
        ai_analysis: { noise_level: "Medium", networking_pressure: "High", crowd_type: "Tech" },
        common_questions: [],
    },
    {
        id: "2",
        title: "Jazz Night at Cain's Ballroom",
        summary: "Live jazz featuring the Tulsa Quartet. Craft cocktails available.",
        date_iso: "2026-02-15T20:00:00",
        location: "Cain's Ballroom",
        coordinates: { lat: 36.1585, lng: -95.995 },
        imageUrl: "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
        vibe_tags: ["Music", "Food & Drink"],
        original_url: "#",
        originalSource: "Cain's Ballroom",
        ai_analysis: { noise_level: "Medium", networking_pressure: "Low", crowd_type: "Music Lovers" },
        common_questions: [],
    },
];

const getMockChatResponse = (message) => {
    const responses = [
        "That sounds wonderful! Based on your preferences, I'd recommend checking out the Jazz Night at Cain's Ballroom this weekend.",
        "I've found a few spots that match that vibe. Have you considered the Founders Lounge at The Mayo?",
        "Great question! The Arts District has several options this weekend.",
    ];

    return {
        message: responses[Math.floor(Math.random() * responses.length)],
        events: getMockEvents(),
        conversationId: "mock-" + Date.now(),
    };
};

// =============================================================================
// USER PREFERENCES API
// =============================================================================

/**
 * Update user preference settings (location, radius, price, family-friendly).
 * Called when user completes onboarding or updates their settings.
 */
export const updateUserPreferences = async (preferences) => {
    try {
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/users/me/preferences`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preferences),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('[DEBUG] User preferences updated:', data);
        return data;
    } catch (error) {
        console.error('Failed to update user preferences:', error);
        throw error;
    }
};

/**
 * Add or update a user's category preference (e.g., "music": 3.0).
 * Called when user sets their likes/dislikes for event categories.
 */
export const addUserPreference = async (preference) => {
    try {
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/users/me/preferences`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preference),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('[DEBUG] Category preference added:', data);
        return data;
    } catch (error) {
        console.error('Failed to add category preference:', error);
        throw error;
    }
};

// =============================================================================
// SAVED EVENTS API
// =============================================================================

/**
 * Saves an event to the user's bookmarks.
 * Called when user clicks the heart/save button on an event card.
 * Triggers a "saved" interaction which boosts preference weights by +0.4.
 */
export const saveEvent = async (eventId) => {
    if (!eventId) {
        console.warn("[DEBUG] Skipping save: missing eventId.");
        return;
    }

    try {
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/users/me/saved-events/${eventId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log(`[DEBUG] Event ${eventId} saved successfully.`);
        return data;
    } catch (error) {
        console.error('Failed to save event:', error);
        throw error;
    }
};
/**
 * Remove an event from the user's saved/bookmarked events.
 * Called when user clicks the filled heart to unsave an event.
 * Triggers an "unsaved" interaction.
 */
export const unsaveEvent = async (eventId) => {
    if (!eventId) {
        console.warn("[DEBUG] Skipping unsave: missing eventId.");
        return;
    }

    try {
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/users/me/saved-events/${eventId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // 204 No Content has no response body, so don't try to parse JSON
        if (response.status === 204) {
            console.log(`[DEBUG] Event ${eventId} unsaved successfully.`);
            return { success: true };
        }

        const data = await response.json();
        console.log(`[DEBUG] Event ${eventId} unsaved successfully.`);
        return data;
    } catch (error) {
        console.error('Failed to unsave event:', error);
        throw error;
    }
};
/**
 * Fetch all saved events for the authenticated user.
 * Called to display user's bookmarked events.
 */
export const fetchSavedEvents = async () => {
    if (USE_MOCKS) {
        return getMockEvents();
    }

    try {
        const response = await authedFetch(`${RUST_BACKEND_URL}/api/users/me/saved-events`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const events = await response.json();
        return transformBackendEvents(events);
    } catch (error) {
        console.error('Failed to fetch saved events:', error);
        return [];
    }
};

// =============================================================================
// INTERACTION & PREFERENCE API
// =============================================================================

/**
 * Records a user interaction and triggers a preference update.
 * This function calls the LLM service, which then:
 * 1. Logs the raw interaction to the main backend.
 * 2. Calculates and applies preference score changes.
 */
export const recordInteraction = async ({
    userId,
    eventId,
    interactionType,
    eventCategories = []
}) => {
    console.log("[DEBUG] recordInteraction called:", { interactionType, eventCategories });
    // No-op if user is not logged in or eventId is missing
    if (!userId || !eventId) {
        console.log("[DEBUG] Skipping interaction: missing userId or eventId.");
        return;
    }

    try {
        // This endpoint orchestrates logging the interaction and updating preferences.
        await authedFetch(`${LLM_SERVICE_URL}/api/interactions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                event_id: eventId,
                interaction_type: interactionType,
                event_categories: eventCategories, // Pass the full array of categories
            }),
        });
        console.log(`[DEBUG] Interaction for event ${eventId} sent to database.`);
    } catch (e) {
        console.warn('[recordInteraction] failed to send interaction to LLM service:', e.message);
    }
};