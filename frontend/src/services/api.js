// =============================================================================
// API Configuration
// =============================================================================

// Backend URLs - adjust based on environment
// CRA uses process.env.REACT_APP_*
const RUST_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:3000";
const LLM_SERVICE_URL = process.env.REACT_APP_LLM_SERVICE_URL || "http://localhost:8001";

// Set to false to use real APIs
const USE_MOCKS = process.env.REACT_APP_USE_MOCKS === "true";

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
        const response = await fetch(`${RUST_BACKEND_URL}/api/events`);
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

        const response = await fetch(`${RUST_BACKEND_URL}/api/events/search?${queryString}`);
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
        const response = await fetch(`${LLM_SERVICE_URL}/api/search`, {
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
        return { events: await searchEvents({ q: query }), parsed: { query } };
    }
};

// =============================================================================
// Chat API (Python LLM Service :8001 - Tully)
// =============================================================================

/**
 * Send a chat message to Tully.
 * Returns a conversational response with optional event recommendations.
 */
export const chatWithTully = async (message, userId = null, conversationHistory = [], conversationId = null) => {
    if (USE_MOCKS) {
        return getMockChatResponse(message);
    }

    try {
        const response = await fetch(`${LLM_SERVICE_URL}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                user_id: userId,
                conversation_history: conversationHistory,
                conversation_id: conversationId,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return {
            message: data.message,
            events: transformBackendEvents(data.events || []),
            conversationId: data.conversation_id,
        };
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
 * Transform backend event format to frontend format.
 * Maps database fields to what the UI components expect.
 */
const transformBackendEvents = (events) => {
    return events.map((event) => ({
        id: event.id,
        title: event.title,
        summary: event.description || "",
        date_iso: event.start_time,
        location: event.venue || event.location || "TBA",
        venue_address: event.venue_address,
        venue_website: event.venue_website,
        imageUrl: event.image_url || getDefaultImage(event.categories),
        vibe_tags: mapCategoriesToVibes(event.categories),
        original_url: event.source_url,
        originalSource: event.source_name,
        price_min: event.price_min,
        price_max: event.price_max,
        outdoor: event.outdoor,
        family_friendly: event.family_friendly,
        coordinates: event.coordinates || getDefaultCoordinates(event.location),
        ai_analysis: {
            noise_level: event.outdoor ? "Medium (Outdoor)" : "Medium",
            networking_pressure: "Medium",
            crowd_type: event.categories?.[0] || "General",
        },
        common_questions: [],
    }));
};

/**
 * Map backend categories to frontend vibe tags.
 */
const mapCategoriesToVibes = (categories) => {
    if (!categories || categories.length === 0) return ["General"];

    const vibeMap = {
        concerts: "Nightlife",
        music: "Nightlife",
        jazz: "Chill",
        sports: "Exclusive",
        family: "Chill",
        comedy: "Nightlife",
        nightlife: "Nightlife",
        business: "Business",
        networking: "Business",
        outdoor: "Chill",
        wellness: "Chill",
    };

    return categories.map((cat) => vibeMap[cat.toLowerCase()] || cat);
};

/**
 * Get a default image based on event category.
 */
const getDefaultImage = (categories) => {
    const firstCategory = categories?.[0]?.toLowerCase() || "";

    const imageMap = {
        concerts: "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
        music: "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
        sports: "https://images.unsplash.com/photo-1461896836934-28e4c40e7d5c?auto=format&fit=crop&w=800&q=80",
        family: "https://images.unsplash.com/photo-1536640712-4d4c36ff0e4e?auto=format&fit=crop&w=800&q=80",
        comedy: "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?auto=format&fit=crop&w=800&q=80",
        business: "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=800&q=80",
    };

    return imageMap[firstCategory] || "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=800&q=80";
};

/**
 * Get default coordinates for Tulsa area.
 */
const getDefaultCoordinates = (location) => {
    return {
        lat: 36.1539 + (Math.random() - 0.5) * 0.02,
        lng: -95.9928 + (Math.random() - 0.5) * 0.02,
    };
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
        vibe_tags: ["Exclusive", "Business"],
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
        vibe_tags: ["Nightlife", "Chill"],
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