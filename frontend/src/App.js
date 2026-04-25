/**
 * App.js - Main Application Component
 * ====================================
 *
 * STRUCTURE:
 * 1. Fixed Header (search + navigation)
 * 2. Hero Section (slideshow, shown when no search query)
 * 3. Main Content
 *    - AI Chat Widget (Tully)
 *    - Tab Selection (Saved Events / Recommended / This Week / All Events / By Venue)
 *    - Date Filter (From / To)
 *    - Events List + Map (two-column layout)
 *    - Pagination
 * 4. Event Modal (overlay for event details)
 * 5. Venue Selector Modal (when "By Venue" is clicked)
 * 6. User Profile Modal (when profile button is clicked)
 *
 * STATE:
 * - events: Array of event objects from API
 * - savedEvents: Array of saved event objects from API
 * - recommendedEvents: Array of AI-ranked personalized events from API
 * - loading: Boolean for loading state
 * - query: Search query string
 * - selectedEvent: Event object for modal
 * - hoveredEventId: For map marker highlighting
 * - viewMode: 'list' | 'map' (mobile toggle)
 * - currentSlide: Index for hero slideshow
 * - activeTab: 'savedEvents' | 'recommended' | 'thisWeek' | 'allEvents' | 'byVenue'
 * - currentPage: Current pagination page (1-indexed)
 * - dateFrom: Start date filter (YYYY-MM-DD string or '')
 * - dateTo: End date filter (YYYY-MM-DD string or '')
 * - selectedVenue: Selected venue name for filtering (null = show venue selector)
 * - showVenueModal: Boolean to control venue selector modal visibility
 * - showProfileModal: Boolean to control user profile modal visibility
 */

import React, { useState, useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { Sparkles, Loader2, Map as MapIcon, List, Compass, ChevronLeft, ChevronRight, Calendar, LayoutGrid, Filter, X, AlertCircle, Building2, MapPin, Clock, Heart } from 'lucide-react';
import { fetchEvents, fetchRecommendedEvents, fetchSavedEvents, smartSearch, recordInteraction, updateUserPreferences, addUserPreference } from './services/api';
import { useAuth } from './context/AuthContext';

// Components
import EventCard from './components/EventCard';
import EventModal from './components/EventModal';
import Header from './components/Header';
import TulsaMap from './components/TulsaMap';
import AIChatWidget from './components/AIChatWidget';
import AuthModal from './components/AuthModal';
import OnboardingModal from './components/OnboardingModal';
import UserProfileModal from './components/UserProfileModal';
import Footer from './components/Footer';

import './index.css';

// =============================================================================
// CONSTANTS
// =============================================================================

/** Hero slideshow images (local assets with Unsplash fallbacks) */
const HERO_SLIDES = [
    '/assets/TulsaSlideshow/slide1.jpg',
    '/assets/TulsaSlideshow/slide2.jpg',
    '/assets/TulsaSlideshow/slide3.jpg',
    '/assets/TulsaSlideshow/slide4.jpg',
    '/assets/TulsaSlideshow/slide5.jpg',
    '/assets/TulsaSlideshow/slide6.jpg',
];

const FALLBACK_SLIDES = [
    "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1950&q=80",
    "https://images.unsplash.com/photo-1569336415962-a4bd9f69cd83?auto=format&fit=crop&w=1950&q=80",
    "https://images.unsplash.com/photo-1572576578056-b6b553e14449?auto=format&fit=crop&w=1950&q=80",
    "https://images.unsplash.com/photo-1557065963-356c94e022bf?auto=format&fit=crop&w=1950&q=80"
];

/** Slideshow interval in milliseconds */
const SLIDE_INTERVAL = 5000;

/** Events per page for pagination */
const EVENTS_PER_PAGE = 6;

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get the start and end of the current week (Sunday to Saturday)
 */
const getThisWeekRange = () => {
    const now = new Date();
    const startOfWeek = new Date(now);
    startOfWeek.setDate(now.getDate() - now.getDay()); // Sunday
    startOfWeek.setHours(0, 0, 0, 0);

    const endOfWeek = new Date(startOfWeek);
    endOfWeek.setDate(startOfWeek.getDate() + 6); // Saturday
    endOfWeek.setHours(23, 59, 59, 999);

    return { start: startOfWeek, end: endOfWeek };
};

/**
 * Filter events to only those happening this week
 */
const filterThisWeekEvents = (events) => {
    if (!Array.isArray(events)) return [];
    const { start, end } = getThisWeekRange();
    return events.filter(event => {
        if (!event.date_iso) return false;
        const eventDate = new Date(event.date_iso);
        return eventDate >= start && eventDate <= end;
    });
};

/**
 * Filter events by date range
 */
const filterByDateRange = (events, fromDate, toDate) => {
    if (!Array.isArray(events)) return [];
    return events.filter(event => {
        if (!event.date_iso) return false;
        const eventDate = new Date(event.date_iso);

        if (fromDate) {
            const from = new Date(fromDate);
            from.setHours(0, 0, 0, 0);
            if (eventDate < from) return false;
        }

        if (toDate) {
            const to = new Date(toDate);
            to.setHours(23, 59, 59, 999);
            if (eventDate > to) return false;
        }

        return true;
    });
};

/**
 * Get unique venues with event counts and details
 */
const getVenuesWithDetails = (events) => {
    if (!Array.isArray(events)) return [];

    const venueMap = new Map();

    events.forEach(event => {
        const venueName = event.location || 'Unknown Venue';
        if (!venueMap.has(venueName)) {
            venueMap.set(venueName, {
                name: venueName,
                address: event.venue_address || '',
                eventCount: 0,
                upcomingEvent: null,
                imageUrl: null,
            });
        }

        const venue = venueMap.get(venueName);
        venue.eventCount++;

        // Get the first event's image as venue image
        if (!venue.imageUrl && event.imageUrl) {
            venue.imageUrl = event.imageUrl;
        }

        // Track the next upcoming event
        if (event.date_iso) {
            const eventDate = new Date(event.date_iso);
            if (!venue.upcomingEvent || eventDate < new Date(venue.upcomingEvent.date_iso)) {
                venue.upcomingEvent = event;
            }
        }
    });

    // Convert to array and sort by event count (most events first)
    return Array.from(venueMap.values())
        .filter(v => v.name !== 'Unknown Venue')
        .sort((a, b) => b.eventCount - a.eventCount);
};

/**
 * Get unique venue count
 */
const getUniqueVenueCount = (events) => {
    if (!Array.isArray(events)) return 0;
    const venues = new Set(events.map(e => e.location).filter(Boolean));
    return venues.size;
};

// =============================================================================
// BETA DISCLAIMER MODAL
// =============================================================================

const BetaDisclaimer = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[200] p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#1a1a2e] border border-[#D4AF37]/30 rounded-2xl max-w-md w-full p-6 sm:p-8 shadow-2xl shadow-[#D4AF37]/10"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Icon */}
                <div className="flex justify-center mb-4">
                    <div className="bg-[#D4AF37]/20 p-4 rounded-full">
                        <AlertCircle size={32} className="text-[#D4AF37]" />
                    </div>
                </div>

                {/* Title */}
                <h2 className="text-2xl sm:text-3xl font-serif text-white text-center mb-2">
                    Welcome to <span className="text-[#D4AF37]">Locate918</span>
                </h2>

                {/* Beta Badge */}
                <div className="flex justify-center mb-4">
                    <span className="bg-[#D4AF37] text-black text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                        Open Beta
                    </span>
                </div>

                {/* Message */}
                <p className="text-slate-300 text-center text-sm sm:text-base leading-relaxed mb-6">
                    This site is currently in <strong className="text-white">open beta</strong>.
                    Event information is aggregated from multiple sources and may contain inaccuracies.
                    Please verify event details with the original source before attending.
                </p>

                {/* Disclaimer Points */}
                <ul className="text-slate-400 text-xs sm:text-sm space-y-2 mb-6">
                    <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#D4AF37] mt-1.5 flex-shrink-0"></span>
                        <span>Event dates, times, and locations may change without notice</span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#D4AF37] mt-1.5 flex-shrink-0"></span>
                        <span>Some features are still under development</span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#D4AF37] mt-1.5 flex-shrink-0"></span>
                        <span>We appreciate your feedback as we improve</span>
                    </li>
                </ul>

                {/* Button */}
                <button
                    onClick={onClose}
                    className="w-full bg-[#D4AF37] hover:bg-[#C5A028] text-black font-bold py-3 sm:py-4 rounded-xl transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] shadow-lg"
                >
                    I Understand, Let's Explore!
                </button>

                {/* Footer */}
                <p className="text-slate-500 text-[10px] sm:text-xs text-center mt-4">
                    By continuing, you acknowledge this is a beta product.
                </p>
            </div>
        </div>
    );
};

// =============================================================================
// VENUE IMAGE COMPONENT (handles load/error state per card)
// =============================================================================

const VenueImage = ({ src, alt }) => {
    const [status, setStatus] = useState(src ? 'loading' : 'fallback');

    // Reset status when src changes
    useEffect(() => {
        setStatus(src ? 'loading' : 'fallback');
    }, [src]);

    return (
        <div className="relative h-32 overflow-hidden bg-gradient-to-br from-[#162b4a] to-[#1f3a60]">
            {/* Real image only rendered when there's a src to try */}
            {status !== 'fallback' && src && (
                <img
                    src={src}
                    alt={alt}
                    className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    onLoad={() => setStatus('loaded')}
                    onError={() => setStatus('fallback')}
                />
            )}

            {/* Logo fallback only shown when there's no image or it failed */}
            {status === 'fallback' && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <img
                        src="/assets/Logo.png"
                        alt="Locate918"
                        className="w-16 h-16 object-contain opacity-50"
                    />
                </div>
            )}

            {/* Gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        </div>
    );
};

// =============================================================================
// VENUE SELECTOR MODAL
// =============================================================================

const VenueSelectorModal = ({ isOpen, onClose, venues, onSelectVenue }) => {
    const [searchTerm, setSearchTerm] = useState('');

    if (!isOpen) return null;

    const filteredVenues = venues.filter(venue =>
        venue.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        venue.address?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[150] p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#f8f1e0] border border-[#D4AF37]/30 rounded-2xl max-w-4xl w-full max-h-[85vh] flex flex-col shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-4 sm:p-6 border-b border-slate-200 flex-shrink-0">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="bg-[#D4AF37]/20 p-2.5 rounded-xl">
                                <Building2 size={24} className="text-[#D4AF37]" />
                            </div>
                            <div>
                                <h2 className="text-xl sm:text-2xl font-serif text-slate-900">
                                    Select a Venue
                                </h2>
                                <p className="text-xs sm:text-sm text-slate-500">
                                    {venues.length} venues with upcoming events
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                        >
                            <X size={20} className="text-slate-500" />
                        </button>
                    </div>

                    {/* Search */}
                    <div className="relative">
                        <input
                            type="text"
                            placeholder="Search venues..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full px-4 py-3 pl-10 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37] bg-white"
                        />
                        <MapPin size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                </div>

                {/* Venue Grid */}
                <div className="flex-1 overflow-y-auto p-4 sm:p-6">
                    {filteredVenues.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredVenues.map((venue) => (
                                <button
                                    key={venue.name}
                                    onClick={() => onSelectVenue(venue.name)}
                                    className="group bg-white rounded-xl border border-slate-200 overflow-hidden hover:border-[#D4AF37] hover:shadow-lg transition-all duration-300 text-left"
                                >
                                    {/* Venue Image with proper fallback */}
                                    <div className="relative">
                                        <VenueImage src={venue.imageUrl} alt={venue.name} />

                                        {/* Event Count Badge */}
                                        <div className="absolute top-2 right-2 bg-[#D4AF37] text-black text-xs font-bold px-2 py-1 rounded-full z-10">
                                            {venue.eventCount} {venue.eventCount === 1 ? 'event' : 'events'}
                                        </div>
                                    </div>

                                    {/* Venue Info */}
                                    <div className="p-3">
                                        <h3 className="font-semibold text-slate-900 text-sm sm:text-base line-clamp-1 group-hover:text-[#D4AF37] transition-colors">
                                            {venue.name}
                                        </h3>
                                        {venue.address && (
                                            <p className="text-xs text-slate-500 mt-1 line-clamp-1 flex items-center gap-1">
                                                <MapPin size={12} className="flex-shrink-0" />
                                                {venue.address}
                                            </p>
                                        )}
                                        {venue.upcomingEvent && (
                                            <p className="text-xs text-[#D4AF37] mt-2 flex items-center gap-1">
                                                <Clock size={12} className="flex-shrink-0" />
                                                Next: {new Date(venue.upcomingEvent.date_iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                                            </p>
                                        )}
                                    </div>
                                </button>
                            ))}

                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                            <Building2 size={48} className="text-slate-300 mb-4" />
                            <p className="text-slate-500">No venues found matching "{searchTerm}"</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

const getLoadingCopy = ({ query, activeTab, selectedVenue }) => {
    if (query) {
        return {
            title: 'Searching events...',
            subtitle: `Looking for matches for "${query}".`,
        };
    }

    if (activeTab === 'savedEvents') {
        return {
            title: 'Loading saved events...',
            subtitle: 'Retrieving your bookmarked events.',
        };
    }

    if (activeTab === 'recommended') {
        return {
            title: 'Building recommendations...',
            subtitle: 'Matching upcoming events to your preferences.',
        };
    }

    if (activeTab === 'byVenue' && selectedVenue) {
        return {
            title: 'Loading venue events...',
            subtitle: `Fetching upcoming events for ${selectedVenue}.`,
        };
    }

    return {
        title: 'Loading events...',
        subtitle: 'Retrieving the latest upcoming events from the backend.',
    };
};

const DataLoadingOverlay = ({ isVisible, title, subtitle }) => {
    if (!isVisible) return null;

    return (
        <div className="fixed inset-0 z-[80] bg-[#08111f]/55 backdrop-blur-sm flex items-center justify-center px-4">
            <div className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-950/85 px-6 py-8 text-center shadow-2xl">
                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full border border-[#D4AF37]/30 bg-[#D4AF37]/10">
                    <Loader2 size={28} className="animate-spin text-[#D4AF37]" />
                </div>
                <h2 className="text-2xl font-serif text-white">{title}</h2>
                <p className="mt-2 text-sm text-slate-300">{subtitle}</p>
            </div>
        </div>
    );
};

// =============================================================================
// MAIN APP COMPONENT
// =============================================================================

export default function App() {
    const { user, signOut, loading: authLoading, refreshUser } = useAuth();

    // --- STATE ---
    const [events, setEvents] = useState([]);
    const [savedEvents, setSavedEvents] = useState([]);
    const [recommendedEvents, setRecommendedEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [selectedEvent, setSelectedEvent] = useState(null);
    const [hoveredEventId, setHoveredEventId] = useState(null);
    const [viewMode, setViewMode] = useState('list');
    const [currentSlide, setCurrentSlide] = useState(0);
    const [isAuthOpen, setIsAuthOpen] = useState(false);
    const [activeTab, setActiveTab] = useState(user ? 'savedEvents' : 'thisWeek');
    const [currentPage, setCurrentPage] = useState(1);
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [showDateFilter, setShowDateFilter] = useState(false);
    const [showBetaDisclaimer, setShowBetaDisclaimer] = useState(false);
    const [showVenueModal, setShowVenueModal] = useState(false);
    const [selectedVenue, setSelectedVenue] = useState(null);
    const [showOnboarding, setShowOnboarding] = useState(false);
    const [showProfileModal, setShowProfileModal] = useState(false);
    const [showLoadingOverlay, setShowLoadingOverlay] = useState(false);
    const [loadingCopy, setLoadingCopy] = useState(() =>
        getLoadingCopy({
            query: '',
            activeTab: user ? 'savedEvents' : 'thisWeek',
            selectedVenue: null,
        })
    );
    const [hasFetchedSavedEvents, setHasFetchedSavedEvents] = useState(false);

    // --- FIX 1: Ref to track current user without triggering effect re-runs ---
    const userRef = useRef(user);
    userRef.current = user;

    // --- HANDLERS ---

    const handleSignOut = async () => {
        const { error } = await signOut();
        if (error) {
            console.error("Sign out failed:", error.message);
        }
    };

    const handleOpenProfile = () => {
        setShowProfileModal(true);
    };

    const handleCloseProfile = () => {
        setShowProfileModal(false);
    };

    const handleProfileUpdate = async (updatedData) => {
        // Refresh user data from backend after profile update
        await refreshUser();
    };

    // --- EFFECTS ---
    // Update default tab based on login status when auth finishes loading
    useEffect(() => {
        if (authLoading) {
            return; // Wait for auth to load
        }

        if (!user && activeTab === 'savedEvents') {
            setActiveTab('thisWeek');
        }
    }, [user, activeTab, authLoading]);

    // Check if onboarding is needed - but ONLY AFTER we've fetched backend data
    useEffect(() => {
        if (authLoading) {
            return; // Wait for auth to load
        }

        if (!user) {
            setShowOnboarding(false);
            return; // No user, don't show onboarding
        }

        // Don't check onboarding until we have backend data
        if (user.backend_user === undefined) {
            console.log('[DEBUG] Waiting for backend user data...');
            return; // Wait for refreshUser() to fetch data
        }

        // Check the flag explicitly
        const hasCompleted = user.user_metadata?.has_completed_onboarding === true;

        console.log('[DEBUG] Onboarding check:', {
            user_id: user.id,
            has_completed_onboarding: hasCompleted,
            will_show_onboarding: !hasCompleted,
        });

        setShowOnboarding(!hasCompleted);
    }, [user, user?.user_metadata?.has_completed_onboarding, user?.backend_user, authLoading]);

    // Refresh user data from backend when user logs in (to get accurate has_completed_onboarding)
    useEffect(() => {
        if (!authLoading && user && user.backend_user === undefined) {
            // Only call if we haven't already fetched backend data
            console.log('[DEBUG] Auto-refreshing user on login');
            refreshUser();
        }
    }, [user, authLoading, refreshUser]);

    // Show beta disclaimer on first visit (per session)
    useEffect(() => {
        const hasSeenDisclaimer = sessionStorage.getItem('locate918_beta_seen');
        if (!hasSeenDisclaimer) {
            setShowBetaDisclaimer(true);
        }
    }, []);

    const handleCloseBetaDisclaimer = () => {
        sessionStorage.setItem('locate918_beta_seen', 'true');
        setShowBetaDisclaimer(false);
    };

    // Slideshow auto-advance timer
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentSlide((prev) => (prev + 1) % HERO_SLIDES.length);
        }, SLIDE_INTERVAL);
        return () => clearInterval(timer);
    }, []);

    // Debounce the search query to prevent excessive API calls while typing
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedQuery(query);
        }, 500); // 500ms delay

        return () => {
            clearTimeout(handler);
        };
    }, [query]);

    // Scroll to top when search query changes
    useLayoutEffect(() => {
        window.scrollTo({ top: 0, behavior: 'auto' });
    }, [debouncedQuery]);

    // Reset to page 1 when tab changes, query changes, or date filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [activeTab, debouncedQuery, dateFrom, dateTo, selectedVenue]);

    // Clear date filter when switching to "This Week", "Saved Events", or "Recommended" tabs
    useEffect(() => {
        if (activeTab === 'thisWeek' || activeTab === 'savedEvents' || activeTab === 'recommended') {
            setDateFrom('');
            setDateTo('');
            setShowDateFilter(false);
        }
    }, [activeTab]);

    // Clear selected venue when switching away from byVenue tab
    useEffect(() => {
        if (activeTab !== 'byVenue') {
            setSelectedVenue(null);
        }
    }, [activeTab]);

    // --- FIX 2: Main fetch effect — removed `user` from dependency array ---
    useEffect(() => {
        const currentUser = userRef.current;
        const loadData = async () => {
            try {
                if (debouncedQuery) {
                    const useSmartSearch = currentUser?.backend_user?.use_smart_search !== false;
                    const result = await smartSearch(debouncedQuery, useSmartSearch);
                    setEvents(Array.isArray(result?.events) ? result.events : []);
                } else if (activeTab === 'savedEvents' && currentUser) {
                    // Already handled by background fetch
                } else if (activeTab === 'recommended' && currentUser) {
                    const data = await fetchRecommendedEvents();
                    setRecommendedEvents(Array.isArray(data) ? data : []);
                } else {
                    const eventsData = await fetchEvents();
                    setEvents(Array.isArray(eventsData) ? eventsData : []);
                }
            } catch (err) {
                console.error("Failed to fetch events:", err);
                if (debouncedQuery) {
                    setEvents([]);
                } else if (activeTab === 'savedEvents') {
                    setSavedEvents([]);
                } else if (activeTab === 'recommended') {
                    setRecommendedEvents([]);
                } else {
                    setEvents([]);
                }
            } finally {
                setLoading(false);
            }
        };

        setLoading(true);
        setLoadingCopy(getLoadingCopy({ query: debouncedQuery, activeTab, selectedVenue }));
        loadData();
    }, [debouncedQuery, activeTab, selectedVenue]);

    useEffect(() => {
        if (!loading || authLoading) {
            setShowLoadingOverlay(false);
            return;
        }

        const timer = setTimeout(() => {
            setShowLoadingOverlay(true);
        }, 180);

        return () => clearTimeout(timer);
    }, [loading, authLoading]);

    // =============================================================================
    // BACKGROUND FETCH: Populate saved events for badge (independent of tab)
    // =============================================================================
    useEffect(() => {
        if (!user) {
            // User logged out, clear saved events and reset flag
            setSavedEvents([]);
            setHasFetchedSavedEvents(false);
            return;
        }

        // Only fetch once per user session
        if (hasFetchedSavedEvents) {
            return;
        }

        // --- FIX 3: Set flag BEFORE async work to prevent re-entry ---
        const loadSavedEventsForBadge = async () => {
            try {
                setHasFetchedSavedEvents(true); // Guard immediately
                const data = await fetchSavedEvents();
                // Filter out events where date_iso is in the past
                const now = new Date();
                const futureSavedEvents = (data || []).filter(event => {
                    if (!event.date_iso) return true; // Keep if no date
                    const eventDate = new Date(event.date_iso);
                    return eventDate >= now;
                });
                setSavedEvents(futureSavedEvents);
                console.log('[DEBUG] Background fetch: loaded', futureSavedEvents?.length || 0, 'saved events (filtered for future dates)');
            } catch (err) {
                console.error('[ERROR] Failed to fetch saved events for badge:', err);
                setHasFetchedSavedEvents(false); // Reset flag so it can retry
                setSavedEvents([]);
            }
        };

        loadSavedEventsForBadge();
    }, [user, hasFetchedSavedEvents]);

    // --- DERIVED STATE ---

    // Get venues with details for the modal
    const venuesWithDetails = useMemo(() => getVenuesWithDetails(events), [events]);

    // Choose source of events (saved vs recommended vs all)
    const sourceEvents = debouncedQuery ? events : activeTab === 'savedEvents' ? savedEvents : activeTab === 'recommended' ? recommendedEvents : events;

    const filteredEvents = useMemo(() => {
        // handles natural language search explicitly.
        return Array.isArray(sourceEvents) ? sourceEvents : [];
    }, [sourceEvents]);

    // Apply tab filter (Saved Events vs Recommended vs This Week vs All Events vs By Venue) and date range filter
    const tabFilteredEvents = useMemo(() => {
        if (debouncedQuery) {
            // During search, apply date filter if set
            return (dateFrom || dateTo)
                ? filterByDateRange(filteredEvents, dateFrom, dateTo)
                : filteredEvents;
        }

        if (activeTab === 'savedEvents') {
            // Saved Events: filter out expired events (already in saved collection)
            const now = new Date();
            return filteredEvents.filter(event => {
                if (!event.date_iso) return true;
                const eventDate = new Date(event.date_iso);
                return eventDate >= now;
            });
        }

        if (activeTab === 'recommended') {
            // Recommended: return all filtered (already ranked by backend)
            return filteredEvents;
        }

        if (activeTab === 'thisWeek') {
            // This Week: flagship + featured only (P1 + P2), no P3 clutter.
            // Safety guard also blocks library/educational sources in case of bad DB data.
            const featured = filteredEvents.filter(e => {
                if ((e.venue_priority ?? 3) > 2) return false;
                const src = (e.originalSource || '').toLowerCase();
                if (src.includes('library') || src.includes('tccl')) return false;
                return true;
            });
            return filterThisWeekEvents(featured);
        }

        if (activeTab === 'byVenue' && selectedVenue) {
            // Filter events by selected venue
            let venueEvents = filteredEvents.filter(e => e.location === selectedVenue);
            // Apply date filter if set
            if (dateFrom || dateTo) {
                venueEvents = filterByDateRange(venueEvents, dateFrom, dateTo);
            }
            return venueEvents;
        }

        // "All Events" tab - apply date filter if set
        return (dateFrom || dateTo)
            ? filterByDateRange(filteredEvents, dateFrom, dateTo)
            : filteredEvents;
    }, [filteredEvents, activeTab, debouncedQuery, dateFrom, dateTo, selectedVenue]);

    // Pagination calculations
    const totalPages = Math.ceil(tabFilteredEvents.length / EVENTS_PER_PAGE);
    const paginatedEvents = useMemo(() => {
        const startIndex = (currentPage - 1) * EVENTS_PER_PAGE;
        return tabFilteredEvents.slice(startIndex, startIndex + EVENTS_PER_PAGE);
    }, [tabFilteredEvents, currentPage]);

    // Count for "This Week" tab badge — P1+P2 only
    const thisWeekCount = useMemo(() => {
        const featured = events.filter(e => (e.venue_priority ?? 3) <= 2);
        return filterThisWeekEvents(featured).length;
    }, [events]);

    // Count for "Saved Events" tab badge
    const savedEventsCount = useMemo(() => savedEvents.length, [savedEvents]);

    // Count for unique venues
    const venueCount = useMemo(() => getUniqueVenueCount(events), [events]);

    // Check if date filter is active
    const hasDateFilter = dateFrom || dateTo;
    const showDataLoadingOverlay = showLoadingOverlay && loading && !authLoading;

    // --- PAGE NAVIGATION HANDLERS ---

    const goToPage = (page) => {
        setHoveredEventId(null); // Clear hover state to prevent stale flyTo
        setCurrentPage(Math.max(1, Math.min(page, totalPages)));
        window.scrollTo({ top: 1000, behavior: 'smooth' });
    };

    const clearDateFilter = () => {
        setDateFrom('');
        setDateTo('');
    };

    const handleByVenueClick = () => {
        setActiveTab('byVenue');
        setShowVenueModal(true);
    };

    const handleSelectVenue = (venueName) => {
        setSelectedVenue(venueName);
        setShowVenueModal(false);
        setCurrentPage(1);
    };

    const handleClearVenue = () => {
        setSelectedVenue(null);
        setShowVenueModal(true);
    };

    // --- EVENT INTERACTION HANDLERS ---

    const handleEventClick = (event, type = 'clicked') => {
        console.log(`[DEBUG] Event clicked: ${event.title}`);
        setSelectedEvent(event);
        if (user) {
            recordInteraction({
                userId: user.id,
                eventId: event.id,
                interactionType: type,
                eventCategories: event.categories
            });
        }
    };

    const handleEventClosing = () => {
        console.log(`[DEBUG] Event dismissed: ${selectedEvent.title}`);
        setSelectedEvent(null);
        if (user && selectedEvent) {
            recordInteraction({
                userId: user.id,
                eventId: selectedEvent.id,
                interactionType: 'dismissed',
                eventCategories: selectedEvent.categories
            });
        }
    };

    // --- SAVE EVENT HANDLER ---

    const handleSaveChange = (eventId, isSaved) => {
        if (isSaved) {
            // Event was saved, add to savedEvents if not already there
            setSavedEvents(prev => {
                if (prev.some(e => e.id === eventId)) return prev;
                const eventToAdd = events.find(e => e.id === eventId) ||
                    recommendedEvents.find(e => e.id === eventId);
                return eventToAdd ? [...prev, eventToAdd] : prev;
            });
        } else {
            // Event was unsaved, remove from savedEvents
            setSavedEvents(prev => prev.filter(e => e.id !== eventId));
        }
    };

    // --- ONBOARDING HANDLER ---

    const handleOnboardingComplete = async (prefs) => {
        console.log("Onboarding complete, submitting:", prefs);
        try {
            // 1. Update general preferences
            await updateUserPreferences({
                location_preference: prefs.location,
                radius_miles: prefs.radius,
                price_max: prefs.priceMax,
                family_friendly_only: prefs.familyFriendly,
                has_completed_onboarding: true,
            });

            // 2. Add category preferences (already have weights from onboarding)
            for (const categoryPref of prefs.categories) {
                await addUserPreference({
                    category: categoryPref.category,
                    weight: categoryPref.weight
                });
            }

            // 3. Refresh user data in auth context
            console.log('[DEBUG] About to call refreshUser()');
            await refreshUser();
            console.log('[DEBUG] refreshUser() completed');

            // 4. Explicitly close the modal
            console.log('[DEBUG] Explicitly closing onboarding modal');
            setShowOnboarding(false);

        } catch (error) {
            console.error("Failed to save onboarding preferences:", error);
            // Still close modal on error so user isn't stuck
            setShowOnboarding(false);
        }
    };

    // --- RENDER ---
    return (
        <div className="min-h-screen text-slate-800 bg-[#f8f1e0] bg-premium-pattern selection-gold relative">
            <DataLoadingOverlay
                isVisible={showDataLoadingOverlay}
                title={loadingCopy.title}
                subtitle={loadingCopy.subtitle}
            />

            {/* ===== ONBOARDING MODAL ===== */}
            <OnboardingModal
                isOpen={showOnboarding}
                onComplete={handleOnboardingComplete}
                user={user}
            />

            {/* ===== BETA DISCLAIMER MODAL ===== */}
            <BetaDisclaimer isOpen={showBetaDisclaimer} onClose={handleCloseBetaDisclaimer} />

            {/* ===== VENUE SELECTOR MODAL ===== */}
            <VenueSelectorModal
                isOpen={showVenueModal}
                onClose={() => {
                    setShowVenueModal(false);
                    if (!selectedVenue) {
                        setActiveTab('allEvents');
                    }
                }}
                venues={venuesWithDetails}
                onSelectVenue={handleSelectVenue}
            />

            {/* ===== USER PROFILE MODAL ===== */}
            <UserProfileModal
                isOpen={showProfileModal}
                onClose={handleCloseProfile}
                user={user}
                onUpdate={handleProfileUpdate}
            />

            {/* ===== FIXED HEADER ===== */}
            <div className="fixed top-0 left-0 right-0 z-50 header-container shadow-sm">
                <Header
                    query={query}
                    setQuery={setQuery}
                    user={user}
                    onOpenAuth={() => setIsAuthOpen(true)}
                    onSignOut={handleSignOut}
                    onOpenProfile={handleOpenProfile}
                    isSearching={Boolean(query) && (loading || query !== debouncedQuery)}
                />
            </div>

            {/* ===== HERO SECTION (shown when no search query) ===== */}
            {!debouncedQuery && (
                <section className="relative h-[50vh] sm:h-[55vh] md:h-[65vh] min-h-[280px] sm:min-h-[350px] md:min-h-[400px] flex items-center justify-center overflow-hidden mt-[100px] md:mt-[172px] lg:mt-[204px] xl:mt-[220px]">
                    {/* Slideshow Background */}
                    <div className="absolute inset-0 z-0">
                        {HERO_SLIDES.map((slide, index) => (
                            <div
                                key={index}
                                className={`absolute inset-0 w-full h-full transition-opacity duration-[2000ms] ease-in-out ${index === currentSlide ? 'opacity-100' : 'opacity-0'}`}
                            >
                                <img
                                    src={slide}
                                    alt="Tulsa"
                                    className="w-full h-full object-cover object-center scale-105"
                                    onError={(e) => {
                                        e.target.onerror = null;
                                        e.target.src = FALLBACK_SLIDES[index % FALLBACK_SLIDES.length];
                                    }}
                                />
                            </div>
                        ))}
                        {/* Cinematic Overlays */}
                        <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/20 to-[#f8f1e0]" />
                        <div className="absolute inset-0 bg-gradient-to-r from-black/30 via-transparent to-black/30" />
                    </div>

                    {/* Hero Content */}
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12 relative z-10">
                        <div className="max-w-4xl mx-auto text-center">
                            {/* Decorative Line */}
                            <div className="flex items-center justify-center gap-4 mb-6 opacity-0 animate-fade-up">
                                <span className="h-px w-12 bg-[#D4AF37]" />
                                <span className="text-[#D4AF37] text-xs sm:text-sm md:text-base font-semibold tracking-[0.3em] uppercase">
                                    Discover Local Events
                                </span>
                                <span className="h-px w-12 bg-[#D4AF37]" />
                            </div>

                            {/* Main Title */}
                            <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-white mb-6 leading-[1.1] opacity-0 animate-fade-up delay-100 drop-shadow-2xl">
                                Experience
                                <span className="block text-[#D4AF37] mt-2">Tulsa</span>
                            </h1>

                            {/* Subtitle */}
                            <p className="text-base sm:text-lg md:text-xl text-white/90 mb-8 max-w-2xl mx-auto leading-relaxed font-light opacity-0 animate-fade-up delay-200 drop-shadow-lg">
                                A curated collection of the city's finest culture, entertainment, and hidden gems.
                            </p>

                            {/* CTA Button */}
                            <div className="opacity-0 animate-fade-up delay-300">
                                <button
                                    onClick={() => document.getElementById('events-section')?.scrollIntoView({ behavior: 'smooth' })}
                                    className="group inline-flex items-center gap-2 bg-[#D4AF37] hover:bg-[#C5A028] text-white px-8 py-4 rounded-full font-semibold text-sm tracking-wide shadow-xl shadow-black/20 transition-all duration-300 hover:scale-105 hover:shadow-2xl"
                                >
                                    Explore Events
                                    <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Slide Indicators */}
                    <div className="absolute bottom-4 sm:bottom-8 left-1/2 -translate-x-1/2 z-20 flex gap-1.5 sm:gap-2">
                        {HERO_SLIDES.map((_, index) => (
                            <button
                                key={index}
                                onClick={() => setCurrentSlide(index)}
                                className={`slide-indicator rounded-full transition-all duration-300 !min-h-0 ${index === currentSlide
                                    ? 'bg-[#D4AF37] w-5 h-1.5 sm:w-6 sm:h-2'
                                    : 'bg-white/50 hover:bg-white/80 w-1.5 h-1.5 sm:w-2 sm:h-2'
                                    }`}
                                aria-label={`Go to slide ${index + 1}`}
                            />
                        ))}
                    </div>
                </section>
            )}

            {/* ===== MAIN CONTENT ===== */}
            <main id="events-section" className={`max-w-7xl mx-auto px-4 sm:px-6 pb-24 relative z-10 transition-all duration-300 ${debouncedQuery ? 'pt-[145px] md:pt-[230px] lg:pt-[235px] xl:pt-[275px]' : 'pt-6 sm:pt-12'}`}>

                {/* AI Chat Widget (only on home page) */}
                {!debouncedQuery && <AIChatWidget userId={user?.id} />}

                {/* Results Header */}
                <div className="flex flex-col gap-4 mb-6 sm:mb-8 pb-4 sm:pb-6 border-b border-slate-200/60 animate-fade-up delay-300">
                    <div className="flex flex-col gap-1 w-full">
                        {debouncedQuery ? (
                            <>
                                <div className="flex items-center justify-between gap-4 md:mt-6">
                                    <div>
                                        <h2 className="text-xl sm:text-2xl md:text-3xl font-serif tracking-tight text-slate-900">
                                            Results: "{debouncedQuery}"
                                        </h2>
                                        <span className="text-xs text-slate-500 font-medium tracking-wide uppercase">
                                            {filteredEvents.length} Experiences Found
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => setQuery('')}
                                        className="flex items-center gap-1.5 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-white text-slate-600 border border-slate-200 hover:border-red-300 hover:text-red-600 hover:bg-red-50 transition-all shadow-sm"
                                    >
                                        <X size={14} className="sm:w-4 sm:h-4" />
                                        <span className="hidden sm:inline">Clear Filter</span>
                                        <span className="sm:hidden">Clear</span>
                                    </button>
                                </div>
                            </>
                        ) : activeTab === 'byVenue' && selectedVenue ? (
                            /* Venue-filtered view header */
                            <div className="flex items-center justify-between gap-4">
                                <div>
                                    <h2 className="text-xl sm:text-2xl md:text-3xl font-serif tracking-tight text-slate-900">
                                        Events at {selectedVenue}
                                    </h2>
                                    <span className="text-xs text-slate-500 font-medium tracking-wide uppercase">
                                        {tabFilteredEvents.length} {tabFilteredEvents.length === 1 ? 'Event' : 'Events'} Found
                                    </span>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setActiveTab('allEvents')}
                                        className="flex items-center gap-1.5 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:text-slate-900 transition-all shadow-sm"
                                    >
                                        <X size={14} className="sm:w-4 sm:h-4" />
                                        <span className="hidden sm:inline">Clear Filter</span>
                                        <span className="sm:hidden">Clear</span>
                                    </button>
                                    <button
                                        onClick={handleClearVenue}
                                        className="flex items-center gap-1.5 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37] hover:text-[#D4AF37] transition-all shadow-sm"
                                    >
                                        <Building2 size={14} className="sm:w-4 sm:h-4" />
                                        <span className="hidden sm:inline">Choose Venue</span>
                                        <span className="sm:hidden">Change</span>
                                    </button>
                                </div>
                            </div>
                        ) : (
                            /* Tab Buttons - Two-row staggered layout */
                            <>
                                {/* Row 1: Personalized Tabs (User-only) */}
                                {user && (
                                    <div className="flex gap-2 mb-3 -mx-4 px-4 sm:mx-0 sm:px-0 overflow-x-auto scrollbar-hide">
                                        <button
                                            onClick={() => setActiveTab('savedEvents')}
                                            className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all duration-300 whitespace-nowrap flex-shrink-0 ${activeTab === 'savedEvents'
                                                ? 'bg-[#D4AF37] text-white shadow-lg shadow-[#D4AF37]/30'
                                                : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50 hover:text-slate-900'
                                                }`}
                                        >
                                            <Heart size={16} className="sm:w-[18px] sm:h-[18px]" />
                                            <span className="hidden sm:inline">Saved Events</span>
                                            <span className="sm:hidden">Saved</span>
                                            <span className={`ml-1 px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-xs rounded-full ${activeTab === 'savedEvents'
                                                ? 'bg-white/20 text-white'
                                                : 'bg-slate-100 text-slate-500'
                                                }`}>
                                                {savedEventsCount}
                                            </span>
                                        </button>
                                        <button
                                            onClick={() => setActiveTab('recommended')}
                                            className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all duration-300 whitespace-nowrap flex-shrink-0 ${activeTab === 'recommended'
                                                ? 'bg-[#D4AF37] text-white shadow-lg shadow-[#D4AF37]/30'
                                                : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50 hover:text-slate-900'
                                                }`}
                                        >
                                            <Sparkles size={16} className="sm:w-[18px] sm:h-[18px]" />
                                            <span className="hidden sm:inline">Recommended for You</span>
                                            <span className="sm:hidden">For You</span>
                                        </button>
                                    </div>
                                )}

                                {/* Row 2: Browse Tabs (Always visible) */}
                                <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4 sm:mx-0 sm:px-0 sm:overflow-visible scrollbar-hide">
                                    <button
                                        onClick={() => setActiveTab('thisWeek')}
                                        className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all duration-300 whitespace-nowrap flex-shrink-0 ${activeTab === 'thisWeek'
                                            ? 'bg-[#D4AF37] text-white shadow-lg shadow-[#D4AF37]/30'
                                            : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50 hover:text-slate-900'
                                            }`}
                                    >
                                        <Calendar size={16} className="sm:w-[18px] sm:h-[18px]" />
                                        <span className="hidden sm:inline">This Week in Tulsa</span>
                                        <span className="sm:hidden">This Week</span>
                                        <span className={`ml-1 px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-xs rounded-full ${activeTab === 'thisWeek'
                                            ? 'bg-white/20 text-white'
                                            : 'bg-slate-100 text-slate-500'
                                            }`}>
                                            {thisWeekCount}
                                        </span>
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('allEvents')}
                                        className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all duration-300 whitespace-nowrap flex-shrink-0 ${activeTab === 'allEvents'
                                            ? 'bg-[#D4AF37] text-white shadow-lg shadow-[#D4AF37]/30'
                                            : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50 hover:text-slate-900'
                                            }`}
                                    >
                                        <LayoutGrid size={16} className="sm:w-[18px] sm:h-[18px]" />
                                        All Events
                                        <span className={`ml-1 px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-xs rounded-full ${activeTab === 'allEvents'
                                            ? 'bg-white/20 text-white'
                                            : 'bg-slate-100 text-slate-500'
                                            }`}>
                                            {events.length}
                                        </span>
                                    </button>
                                    <button
                                        onClick={handleByVenueClick}
                                        className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all duration-300 whitespace-nowrap flex-shrink-0 ${activeTab === 'byVenue'
                                            ? 'bg-[#D4AF37] text-white shadow-lg shadow-[#D4AF37]/30'
                                            : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50 hover:text-slate-900'
                                            }`}
                                    >
                                        <Building2 size={16} className="sm:w-[18px] sm:h-[18px]" />
                                        <span className="hidden sm:inline">By Venue</span>
                                        <span className="sm:hidden">Venues</span>
                                        <span className={`ml-1 px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-xs rounded-full ${activeTab === 'byVenue'
                                            ? 'bg-white/20 text-white'
                                            : 'bg-slate-100 text-slate-500'
                                            }`}>
                                            {venueCount}
                                        </span>
                                    </button>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Mobile View Toggle */}
                    <div className="flex lg:hidden bg-white rounded-lg p-1 border border-slate-200 shadow-sm self-start">
                        <button
                            onClick={() => setViewMode('list')}
                            className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold transition-all ${viewMode === 'list' ? 'bg-slate-900 text-white shadow-md' : 'text-slate-400 hover:text-slate-900'
                                }`}
                        >
                            <List size={14} />
                            List
                        </button>
                        <button
                            onClick={() => setViewMode('map')}
                            className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold transition-all ${viewMode === 'map' ? 'bg-slate-900 text-white shadow-md' : 'text-slate-400 hover:text-slate-900'
                                }`}
                        >
                            <MapIcon size={14} />
                            Map
                        </button>
                    </div>
                </div>

                {/* ===== DATE FILTER ===== */}
                {(activeTab === 'allEvents' || (activeTab === 'byVenue' && selectedVenue) || query) && (
                    <div className="mb-4 sm:mb-6 animate-fade-up">
                        {/* Filter Toggle Button */}
                        <button
                            onClick={() => setShowDateFilter(!showDateFilter)}
                            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all mb-3 ${hasDateFilter
                                ? 'bg-[#D4AF37] text-white'
                                : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50'
                                }`}
                        >
                            <Filter size={14} className="sm:w-4 sm:h-4" />
                            {hasDateFilter ? 'Date Filter Active' : 'Filter by Date'}
                            {hasDateFilter && (
                                <span
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        clearDateFilter();
                                    }}
                                    className="ml-1 p-0.5 hover:bg-white/20 rounded-full cursor-pointer"
                                >
                                    <X size={12} className="sm:w-3.5 sm:h-3.5" />
                                </span>
                            )}
                        </button>

                        {/* Date Filter Inputs - stack on mobile */}
                        {showDateFilter && (
                            <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 sm:gap-4 p-3 sm:p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
                                <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2">
                                    <label htmlFor="dateFrom" className="text-xs sm:text-sm font-medium text-slate-600">
                                        From:
                                    </label>
                                    <input
                                        type="date"
                                        id="dateFrom"
                                        value={dateFrom}
                                        onChange={(e) => setDateFrom(e.target.value)}
                                        className="w-full sm:w-auto px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37]"
                                    />
                                </div>
                                <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2">
                                    <label htmlFor="dateTo" className="text-xs sm:text-sm font-medium text-slate-600">
                                        To:
                                    </label>
                                    <input
                                        type="date"
                                        id="dateTo"
                                        value={dateTo}
                                        onChange={(e) => setDateTo(e.target.value)}
                                        min={dateFrom || undefined}
                                        className="w-full sm:w-auto px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37]"
                                    />
                                </div>
                                {hasDateFilter && (
                                    <button
                                        onClick={clearDateFilter}
                                        className="text-xs sm:text-sm text-slate-500 hover:text-[#D4AF37] transition-colors underline self-start sm:self-auto"
                                    >
                                        Clear dates
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Page Info */}
                {!loading && tabFilteredEvents.length > 0 && (
                    <div className="mb-4 sm:mb-6 text-xs sm:text-sm text-slate-500">
                        Showing {((currentPage - 1) * EVENTS_PER_PAGE) + 1}-{Math.min(currentPage * EVENTS_PER_PAGE, tabFilteredEvents.length)} of {tabFilteredEvents.length} events
                        {hasDateFilter && (
                            <span className="ml-2 text-[#D4AF37]">
                                (filtered)
                            </span>
                        )}
                    </div>
                )}

                {/* ===== DATA VIEW ===== */}
                {loading ? (
                    <div className="flex justify-center items-center py-20">
                        <Loader2 className="animate-spin text-[#C5A028]" size={40} />
                    </div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 sm:gap-12 lg:gap-16">

                        {/* LEFT: Events List */}
                        <div className={`${viewMode === 'list' ? 'block' : 'hidden lg:block'}`}>
                            {paginatedEvents.length > 0 ? (
                                <>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 gap-4 sm:gap-6 lg:gap-8">
                                        {paginatedEvents.map((event, index) => (
                                            <div
                                                key={event.id}
                                                className="relative z-10 transition-transform duration-300 hover:-translate-y-1"
                                                onMouseEnter={() => setHoveredEventId(event.id)}
                                                onMouseLeave={() => setHoveredEventId(null)}
                                            >
                                                <EventCard
                                                    event={event}
                                                    index={index}
                                                    onClick={() => handleEventClick(event, 'clicked')}
                                                    user={user}
                                                    isSaved={savedEvents.some(e => e.id === event.id)}
                                                    onSaveChange={handleSaveChange}
                                                />
                                            </div>
                                        ))}
                                    </div>

                                    {/* Pagination Controls */}
                                    {totalPages > 1 && (
                                        <div className="flex items-center justify-center gap-1 sm:gap-2 mt-8 sm:mt-12 flex-wrap">
                                            {/* Previous Button */}
                                            <button
                                                onClick={() => goToPage(currentPage - 1)}
                                                disabled={currentPage === 1}
                                                className={`flex items-center gap-1 px-2 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${currentPage === 1
                                                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                                    : 'bg-white text-slate-700 border border-slate-200 hover:border-[#D4AF37] hover:text-[#D4AF37]'
                                                    }`}
                                            >
                                                <ChevronLeft size={16} className="sm:w-[18px] sm:h-[18px]" />
                                                <span className="hidden sm:inline">Prev</span>
                                            </button>

                                            {/* Page Numbers */}
                                            <div className="flex items-center gap-1">
                                                {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => {
                                                    // Show first page, last page, current page, and pages around current
                                                    const showPage = page === 1 ||
                                                        page === totalPages ||
                                                        Math.abs(page - currentPage) <= 1;

                                                    // Show ellipsis
                                                    const showEllipsisBefore = page === currentPage - 2 && currentPage > 3;
                                                    const showEllipsisAfter = page === currentPage + 2 && currentPage < totalPages - 2;

                                                    if (showEllipsisBefore || showEllipsisAfter) {
                                                        return <span key={page} className="px-1 sm:px-2 text-slate-400 text-xs sm:text-sm">...</span>;
                                                    }

                                                    if (!showPage) return null;

                                                    return (
                                                        <button
                                                            key={page}
                                                            onClick={() => goToPage(page)}
                                                            className={`w-8 h-8 sm:w-10 sm:h-10 rounded-lg text-xs sm:text-sm font-medium transition-all ${currentPage === page
                                                                ? 'bg-[#D4AF37] text-white shadow-lg'
                                                                : 'bg-white text-slate-700 border border-slate-200 hover:border-[#D4AF37] hover:text-[#D4AF37]'
                                                                }`}
                                                        >
                                                            {page}
                                                        </button>
                                                    );
                                                })}
                                            </div>

                                            {/* Next Button */}
                                            <button
                                                onClick={() => goToPage(currentPage + 1)}
                                                disabled={currentPage === totalPages}
                                                className={`flex items-center gap-1 px-2 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${currentPage === totalPages
                                                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                                    : 'bg-white text-slate-700 border border-slate-200 hover:border-[#D4AF37] hover:text-[#D4AF37]'
                                                    }`}
                                            >
                                                <span className="hidden sm:inline">Next</span>
                                                <ChevronRight size={16} className="sm:w-[18px] sm:h-[18px]" />
                                            </button>
                                        </div>
                                    )}
                                </>
                            ) : (
                                /* Empty State */
                                <div className="flex flex-col items-center justify-center py-16 sm:py-24 bg-white/40 rounded-2xl sm:rounded-[2rem] border border-dashed border-slate-300 text-center px-4">
                                    <div className="bg-white p-4 sm:p-6 rounded-full mb-4 sm:mb-6 shadow-xl shadow-slate-200/50">
                                        <Sparkles className="text-[#D4AF37]" size={24} />
                                    </div>
                                    <h3 className="text-slate-900 font-serif text-xl sm:text-2xl mb-2">
                                        {hasDateFilter
                                            ? 'No events in this date range'
                                            : activeTab === 'savedEvents'
                                                ? 'No saved events'
                                                : activeTab === 'recommended'
                                                    ? 'No recommendations'
                                                    : activeTab === 'thisWeek' && !query
                                                        ? 'No events this week'
                                                        : activeTab === 'byVenue' && selectedVenue
                                                            ? `No upcoming events at ${selectedVenue}`
                                                            : 'No experiences found'}
                                    </h3>
                                    <p className="text-slate-500 mb-4 sm:mb-6 text-sm sm:text-base">
                                        {hasDateFilter
                                            ? 'Try adjusting your date range.'
                                            : activeTab === 'savedEvents'
                                                ? 'Start bookmarking events to see them here!'
                                                : activeTab === 'recommended'
                                                    ? 'Complete your onboarding to get personalized recommendations.'
                                                    : activeTab === 'thisWeek' && !query
                                                        ? 'Check out all upcoming events instead.'
                                                        : activeTab === 'byVenue' && selectedVenue
                                                            ? 'Try selecting a different venue.'
                                                            : 'Try adjusting your search criteria.'}
                                    </p>
                                    <button
                                        onClick={() => {
                                            if (hasDateFilter) {
                                                clearDateFilter();
                                            } else if (query) {
                                                setQuery('');
                                            } else if (activeTab === 'savedEvents') {
                                                setActiveTab('allEvents');
                                            } else if (activeTab === 'recommended') {
                                                setActiveTab('allEvents');
                                            } else if (activeTab === 'byVenue' && selectedVenue) {
                                                handleClearVenue();
                                            } else {
                                                setActiveTab('allEvents');
                                            }
                                        }}
                                        className="text-xs font-bold tracking-widest border-b-2 border-[#D4AF37] pb-1 text-slate-900 hover:text-[#C5A028] transition-all uppercase"
                                    >
                                        {hasDateFilter
                                            ? 'Clear Date Filter'
                                            : activeTab === 'savedEvents'
                                                ? 'Browse All Events'
                                                : activeTab === 'recommended'
                                                    ? 'Browse All Events'
                                                    : activeTab === 'thisWeek' && !query
                                                        ? 'View All Events'
                                                        : activeTab === 'byVenue' && selectedVenue
                                                            ? 'Choose Different Venue'
                                                            : 'Clear Filters'}
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* RIGHT: Map */}
                        <div className={`${viewMode === 'map' ? 'block' : 'hidden lg:block'}`}>
                            <div className="lg:sticky lg:top-[260px] animate-fade-up delay-200">
                                <TulsaMap
                                    events={tabFilteredEvents}
                                    onMarkerClick={handleEventClick}
                                    hoveredEventId={hoveredEventId}
                                    className="h-[60vh] min-h-[400px] sm:h-[500px] lg:h-[650px] shadow-2xl shadow-slate-200/50 border border-white"
                                />
                                <div className="mt-3 sm:mt-4 flex items-center justify-center gap-2 text-[10px] sm:text-xs text-slate-400 font-medium uppercase tracking-widest">
                                    <Compass size={12} className="sm:w-3.5 sm:h-3.5" />
                                    <span>Interactive Map</span>
                                </div>
                            </div>
                        </div>

                    </div>
                )}
            </main>

            <EventModal
                event={selectedEvent}
                onClose={() => handleEventClosing()}
                user={user}
                isSaved={selectedEvent ? savedEvents.some(e => e.id === selectedEvent.id) : false}
                onSaveChange={handleSaveChange}
            />

            {/* ===== AUTH MODAL ===== */}
            <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
            {/* ===== FOOTER ===== */}
            <Footer />
        </div>
    );
}