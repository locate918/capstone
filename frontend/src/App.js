/**
 * App.js - Main Application Component
 * ====================================
 * 
 * STRUCTURE:
 * 1. Fixed Header (search + navigation)
 * 2. Hero Section (slideshow, shown when no search query)
 * 3. Main Content
 *    - AI Chat Widget (Tully)
 *    - Events List + Map (two-column layout)
 * 4. Event Modal (overlay for event details)
 * 
 * STATE:
 * - events: Array of event objects from API
 * - loading: Boolean for loading state
 * - query: Search query string
 * - selectedEvent: Event object for modal
 * - hoveredEventId: For map marker highlighting
 * - viewMode: 'list' | 'map' (mobile toggle)
 * - currentSlide: Index for hero slideshow
 */

import React, { useState, useEffect, useLayoutEffect } from 'react';
import { Sparkles, Loader2, Map as MapIcon, List, Compass } from 'lucide-react';
import { fetchEvents, smartSearch } from './services/api';

// Components
import EventCard from './components/EventCard';
import EventModal from './components/EventModal';
import Header from './components/Header'; 
import TulsaMap from './components/TulsaMap';
import AIChatWidget from './components/AIChatWidget';

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

// =============================================================================
// MAIN APP COMPONENT
// =============================================================================

export default function App() {
  // --- STATE ---
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [hoveredEventId, setHoveredEventId] = useState(null); 
  const [viewMode, setViewMode] = useState('list'); 
  const [currentSlide, setCurrentSlide] = useState(0);

  // --- EFFECTS ---

  // Slideshow auto-advance timer
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % HERO_SLIDES.length);
    }, SLIDE_INTERVAL);
    return () => clearInterval(timer);
  }, []);

  // Scroll to top when search query changes
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [query]);

  // Fetch events (all or search results)
  useEffect(() => {
    const loadData = async () => {
      try {
        let data;
        if (query) {
          const result = await smartSearch(query);
          data = result.events;
        } else {
          data = await fetchEvents();
        }
        setEvents(data);
      } catch (err) {
        console.error("Failed to fetch events:", err);
        setEvents([]);
      } finally {
        setLoading(false);
      }
    };
    
    setLoading(true);
    loadData();
  }, [query]);

  // --- DERIVED STATE ---

  // Client-side filtering (backup for API search)
  const filteredEvents = events.filter(e => {
    if (!query) return true;
    const searchStr = query.toLowerCase();
    return (
      e.title?.toLowerCase().includes(searchStr) ||
      e.vibe_tags?.some(v => v.toLowerCase().includes(searchStr)) ||
      e.summary?.toLowerCase().includes(searchStr) ||
      e.ai_analysis?.crowd_type?.toLowerCase().includes(searchStr)
    );
  });

  // --- RENDER ---
  return (
    <div className="min-h-screen text-slate-800 bg-[#f8f1e0] bg-premium-pattern selection-gold relative">
      
      {/* ===== FIXED HEADER ===== */}
      <div className="fixed top-0 left-0 right-0 z-50 header-container shadow-sm">
        <Header query={query} setQuery={setQuery} />
      </div>

      {/* ===== HERO SECTION (shown when no search query) ===== */}
      {!query && (
        <section className="relative h-[65vh] min-h-[400px] flex items-center justify-center py-12 overflow-hidden mt-[90px] md:mt-[202px] lg:mt-[234px] xl:mt-[250px]"> 
          {/* Slideshow Background */}
          <div className="absolute inset-0 z-0">
            {HERO_SLIDES.map((slide, index) => (
              <div
                key={index}
                className={`absolute inset-0 w-full h-full transition-opacity duration-[2000ms] ease-in-out ${
                  index === currentSlide ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <img 
                  src={slide} 
                  alt="Tulsa" 
                  className="w-full h-full object-cover object-top"
                  onError={(e) => {
                    e.target.onerror = null; 
                    e.target.src = FALLBACK_SLIDES[index % FALLBACK_SLIDES.length];
                  }}
                />
              </div>
            ))}
            {/* Overlays */}
            <div className="absolute inset-0 bg-white/10 backdrop-blur-[1px]"></div>
            <div className="absolute inset-0 bg-gradient-to-b from-white/30 via-transparent to-[#f8f1e0]"></div>
          </div>

          {/* Hero Text */}
          <div className="max-w-7xl mx-auto px-6 lg:px-12 relative z-10">
            <div className="max-w-4xl mx-auto text-center opacity-0 animate-fade-up">
              <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-slate-900 mb-8 leading-[1.1] text-outline-gold">
                Experience Tulsa <br />
              </h1>
              <p className="text-xl text-slate-500 mb-10 max-w-2xl mx-auto leading-relaxed font-light opacity-0 animate-fade-up delay-100 bg-white/75 backdrop-blur-sm rounded-xl p-2 inline-block">
                A curated collection of Tulsa's culture, places, and moments brought together in one place.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ===== MAIN CONTENT ===== */}
      <main className={`max-w-7xl mx-auto px-6 pb-24 relative z-10 transition-all duration-300 ${
        query ? 'pt-[130px] md:pt-[242px] lg:pt-[274px] xl:pt-[290px]' : 'pt-12'
      }`}>
        
        {/* AI Chat Widget (only on home page) */}
        {!query && <AIChatWidget />}
        
        {/* Results Header */}
        <div className="flex flex-col md:flex-row justify-between items-end md:items-center mb-12 pb-6 border-b border-slate-200/60 animate-fade-up delay-300 gap-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-3xl font-serif tracking-tight text-slate-900">
              {query ? `Curated Results: "${query}"` : 'Trending Collections'}
            </h2>
            <span className="text-xs text-slate-500 font-medium tracking-wide uppercase">
              {filteredEvents.length} Experiences Found
            </span>
          </div>

          {/* Mobile View Toggle */}
          <div className="flex lg:hidden bg-white rounded-lg p-1 border border-slate-200 shadow-sm">
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-bold transition-all ${
                viewMode === 'list' ? 'bg-slate-900 text-white shadow-md' : 'text-slate-400 hover:text-slate-900'
              }`}
            >
              <List size={16} />
              List
            </button>
            <button
              onClick={() => setViewMode('map')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-bold transition-all ${
                viewMode === 'map' ? 'bg-slate-900 text-white shadow-md' : 'text-slate-400 hover:text-slate-900'
              }`}
            >
              <MapIcon size={16} />
              Map
            </button>
          </div>
        </div>

        {/* ===== DATA VIEW ===== */}
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <Loader2 className="animate-spin text-[#C5A028]" size={40} />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16">
            
            {/* LEFT: Events List */}
            <div className={`${viewMode === 'list' ? 'block' : 'hidden lg:block'}`}>
              {filteredEvents.length > 0 ? (
                <div className="grid md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 gap-8">
                  {filteredEvents.map((event, index) => (
                    <div 
                      key={event.id}
                      className="relative z-10 transition-transform duration-300 hover:-translate-y-1"
                      onMouseEnter={() => setHoveredEventId(event.id)}
                      onMouseLeave={() => setHoveredEventId(null)}
                    >
                      <EventCard 
                        event={event} 
                        index={index}
                        onClick={setSelectedEvent} 
                      />
                    </div>
                  ))}
                </div>
              ) : (
                /* Empty State */
                <div className="flex flex-col items-center justify-center py-24 bg-white/40 rounded-[2rem] border border-dashed border-slate-300 text-center">
                  <div className="bg-white p-6 rounded-full mb-6 shadow-xl shadow-slate-200/50">
                    <Sparkles className="text-[#D4AF37]" size={32} />
                  </div>
                  <h3 className="text-slate-900 font-serif text-2xl mb-2">No experiences found</h3>
                  <p className="text-slate-500 mb-6">Try adjusting your search criteria.</p>
                  <button 
                    onClick={() => setQuery('')} 
                    className="text-xs font-bold tracking-widest border-b-2 border-[#D4AF37] pb-1 text-slate-900 hover:text-[#C5A028] transition-all uppercase"
                  >
                    Clear Filters
                  </button>
                </div>
              )}
            </div>

            {/* RIGHT: Map */}
            <div className={`${viewMode === 'map' ? 'block' : 'hidden lg:block'}`}>
              <div className="lg:sticky lg:top-[260px] animate-fade-up delay-200">
                <TulsaMap 
                  events={filteredEvents} 
                  onMarkerClick={setSelectedEvent} 
                  hoveredEventId={hoveredEventId}
                  className="h-[500px] lg:h-[650px] shadow-2xl shadow-slate-200/50 border border-white" 
                />
                <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-400 font-medium uppercase tracking-widest">
                  <Compass size={14} />
                  <span>Interactive Discovery Map</span>
                </div>
              </div>
            </div>

          </div>
        )}
      </main>

      {/* ===== EVENT MODAL ===== */}
      <EventModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}