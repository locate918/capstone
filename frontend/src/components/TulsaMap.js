/**
 * TulsaMap Component
 * ==================
 * Interactive Leaflet map showing event locations with custom markers.
 * 
 * PROPS:
 * - events: Array of events with coordinates
 * - onMarkerClick: Function called when marker/popup is clicked
 * - hoveredEventId: ID of event being hovered in list (for highlighting)
 * - className: Additional CSS classes for container
 * 
 * FEATURES:
 * - Custom styled markers by event category
 * - Glassmorphism tooltips with event details on hover
 * - Floating legend
 * - Centers map on hovered event card
 */

import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Tooltip, ZoomControl, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { THEME } from '../styles/theme';

// =============================================================================
// CATEGORY COLORS
// =============================================================================

const CATEGORY_COLORS = {
    music: '#7c3aed',          // Violet - Music
    art: '#ec4899',            // Pink - Arts & Culture
    nature: '#059669',         // Emerald - Nature & Outdoors
    food: '#f59e0b',           // Amber - Food & Drink
    sports: '#ef4444',         // Red - Sports
    family: '#06b6d4',         // Cyan - Family
    comedy: '#8b5cf6',         // Purple - Comedy
    educational: '#3b82f6',    // Blue - Educational
    fitness: '#10b981',        // Green - Fitness
    film: '#6366f1',           // Indigo - Film
    shopping: '#f97316',       // Orange - Shopping
    pets: '#84cc16',           // Lime - Pets
    default: '#64748b'         // Slate - Default
};

// =============================================================================
// CUSTOM MAP STYLES (injected once)
// =============================================================================

const injectMapStyles = () => {
    if (document.getElementById('tulsa-map-styles')) return;

    const style = document.createElement('style');
    style.id = 'tulsa-map-styles';
    style.innerHTML = `
    @keyframes pulse-glow {
      0% { filter: drop-shadow(0 0 8px var(--marker-color)) drop-shadow(0 0 16px var(--marker-color)); }
      50% { filter: drop-shadow(0 0 16px var(--marker-color)) drop-shadow(0 0 28px var(--marker-color)); }
      100% { filter: drop-shadow(0 0 8px var(--marker-color)) drop-shadow(0 0 16px var(--marker-color)); }
    }
    .marker-pin svg {
      filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.3));
      transition: transform 0.3s ease, filter 0.3s ease;
    }
    .marker-hovered svg {
      transform: scale(1.4);
      animation: pulse-glow 1.5s ease-in-out infinite;
    }
    .leaflet-tooltip {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(0, 0, 0, 0.05);
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
      padding: 0;
    }
    .leaflet-tooltip-top:before,
    .leaflet-tooltip-bottom:before,
    .leaflet-tooltip-left:before,
    .leaflet-tooltip-right:before {
      border-top-color: rgba(255, 255, 255, 0.95);
    }
    .leaflet-container {
      font-family: inherit;
    }
  `;
    document.head.appendChild(style);
};

// =============================================================================
// MARKER ICON GENERATOR
// =============================================================================

const createPinIcon = (color, isHovered = false) => {
    return new L.DivIcon({
        className: `bg-transparent border-none marker-pin ${isHovered ? 'marker-hovered' : ''}`,
        html: `
      <div style="--marker-color: ${color};">
        <svg width="36" height="48" viewBox="0 0 30 42" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M15 0C6.71573 0 0 6.71573 0 15C0 26.25 15 42 15 42C15 42 30 26.25 30 15C30 6.71573 23.2843 0 15 0Z" fill="${color}"/>
          <circle cx="15" cy="15" r="6" fill="white" fill-opacity="0.95"/>
        </svg>
      </div>
    `,
        iconSize: [36, 48],
        iconAnchor: [18, 48],
        popupAnchor: [0, -42]
    });
};

/**
 * Get category icon based on vibe tags.
 * Uses keyword matching for flexible detection.
 */
const getCategoryIcon = (tags, isHovered = false) => {
    const lowerTags = (tags || []).map(t => t.toLowerCase());
    const tagString = lowerTags.join(' ');

    // Music
    if (tagString.includes('music') || tagString.includes('concert') || tagString.includes('live') || tagString.includes('band') || tagString.includes('jazz') || tagString.includes('rock')) {
        return createPinIcon(CATEGORY_COLORS.music, isHovered);
    }
    // Arts & Culture
    if (tagString.includes('art') || tagString.includes('theater') || tagString.includes('theatre') || tagString.includes('dance') || tagString.includes('culture') || tagString.includes('gallery') || tagString.includes('performance')) {
        return createPinIcon(CATEGORY_COLORS.art, isHovered);
    }
    // Nature & Outdoors
    if (tagString.includes('nature') || tagString.includes('outdoor') || tagString.includes('park') || tagString.includes('garden') || tagString.includes('hiking') || tagString.includes('trail')) {
        return createPinIcon(CATEGORY_COLORS.nature, isHovered);
    }
    // Food & Drink
    if (tagString.includes('food') || tagString.includes('drink') || tagString.includes('dining') || tagString.includes('culinary') || tagString.includes('restaurant') || tagString.includes('wine') || tagString.includes('beer') || tagString.includes('brewery')) {
        return createPinIcon(CATEGORY_COLORS.food, isHovered);
    }
    // Sports
    if (tagString.includes('sport') || tagString.includes('game') || tagString.includes('tournament') || tagString.includes('football') || tagString.includes('basketball') || tagString.includes('baseball')) {
        return createPinIcon(CATEGORY_COLORS.sports, isHovered);
    }
    // Family
    if (tagString.includes('family') || tagString.includes('kid') || tagString.includes('children') || tagString.includes('child')) {
        return createPinIcon(CATEGORY_COLORS.family, isHovered);
    }
    // Comedy
    if (tagString.includes('comedy') || tagString.includes('comedian') || tagString.includes('funny') || tagString.includes('standup') || tagString.includes('stand-up')) {
        return createPinIcon(CATEGORY_COLORS.comedy, isHovered);
    }
    // Educational
    if (tagString.includes('education') || tagString.includes('museum') || tagString.includes('history') || tagString.includes('lecture') || tagString.includes('workshop') || tagString.includes('class')) {
        return createPinIcon(CATEGORY_COLORS.educational, isHovered);
    }
    // Fitness & Wellness
    if (tagString.includes('fitness') || tagString.includes('wellness') || tagString.includes('yoga') || tagString.includes('workout') || tagString.includes('gym') || tagString.includes('run')) {
        return createPinIcon(CATEGORY_COLORS.fitness, isHovered);
    }
    // Film
    if (tagString.includes('film') || tagString.includes('movie') || tagString.includes('cinema') || tagString.includes('screening')) {
        return createPinIcon(CATEGORY_COLORS.film, isHovered);
    }
    // Shopping & Markets
    if (tagString.includes('shopping') || tagString.includes('market') || tagString.includes('fair') || tagString.includes('expo') || tagString.includes('trade')) {
        return createPinIcon(CATEGORY_COLORS.shopping, isHovered);
    }
    // Pets
    if (tagString.includes('pet') || tagString.includes('dog') || tagString.includes('cat') || tagString.includes('animal')) {
        return createPinIcon(CATEGORY_COLORS.pets, isHovered);
    }

    return createPinIcon(CATEGORY_COLORS.default, isHovered);
};

// =============================================================================
// MAP CONTROLLER - Handles centering on hovered event
// =============================================================================

const MapController = ({ hoveredEventId, events }) => {
    const map = useMap();

    useEffect(() => {
        if (hoveredEventId) {
            const hoveredEvent = events.find(e => e.id === hoveredEventId);
            if (hoveredEvent?.coordinates) {
                map.flyTo(
                    [hoveredEvent.coordinates.lat, hoveredEvent.coordinates.lng],
                    15, // Zoom level when centering
                    { duration: 0.5 } // Smooth animation duration
                );
            }
        }
    }, [hoveredEventId, events, map]);

    return null;
};

// =============================================================================
// HELPER: Format date for tooltip
// =============================================================================

const formatEventDate = (dateIso) => {
    if (!dateIso) return 'Date TBA';
    const date = new Date(dateIso);
    return date.toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
};

// =============================================================================
// SVG ICONS for tooltip
// =============================================================================

const CalendarIcon = () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="16" y1="2" x2="16" y2="6"></line>
        <line x1="8" y1="2" x2="8" y2="6"></line>
        <line x1="3" y1="10" x2="21" y2="10"></line>
    </svg>
);

const MapPinIcon = () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
        <circle cx="12" cy="10" r="3"></circle>
    </svg>
);

// =============================================================================
// COMPONENT
// =============================================================================

const TulsaMap = ({ events, onMarkerClick, hoveredEventId, className = "h-[500px]" }) => {
    const center = [36.1540, -95.9928]; // Downtown Tulsa

    // Inject custom styles on mount
    useEffect(() => {
        injectMapStyles();
    }, []);

    return (
        <div className={`w-full rounded-2xl overflow-hidden border border-white/20 shadow-2xl relative z-0 ${className}`}>
            {/* Vignette Overlay */}
            <div className="absolute inset-0 z-[400] pointer-events-none shadow-[inset_0_0_60px_rgba(0,0,0,0.1)] rounded-2xl" />

            <MapContainer
                center={center}
                zoom={13}
                maxZoom={17}
                style={{ height: '100%', width: '100%' }}
                scrollWheelZoom={true}
                zoomControl={false}
            >
                {/* Map Controller for centering on hover */}
                <MapController hoveredEventId={hoveredEventId} events={events} />

                <TileLayer
                    attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}@2x.png"
                />

                <ZoomControl position="bottomright" />

                {events.map((event) => (
                    event.coordinates && (
                        <Marker
                            key={event.id}
                            position={[event.coordinates.lat, event.coordinates.lng]}
                            icon={getCategoryIcon(event.vibe_tags, event.id === hoveredEventId)}
                            eventHandlers={{
                                click: () => onMarkerClick(event),
                            }}
                        >
                            {/* Tooltip with full event details (on hover) */}
                            <Tooltip
                                direction="top"
                                offset={[0, -42]}
                                opacity={1}
                            >
                                <div style={{ width: '240px', padding: '16px' }}>
                                    {/* Category Tag */}
                                    <div style={{ marginBottom: '8px' }}>
                                        <span style={{
                                            fontSize: '10px',
                                            fontWeight: 'bold',
                                            letterSpacing: '0.05em',
                                            color: '#9ca3af',
                                            textTransform: 'uppercase'
                                        }}>
                                            {event.vibe_tags?.[0] || 'Local'}
                                        </span>
                                    </div>

                                    {/* Title - wraps to show full text */}
                                    <h3 style={{
                                        fontWeight: 'bold',
                                        fontSize: '14px',
                                        marginBottom: '8px',
                                        color: '#0f172a',
                                        lineHeight: '1.4',
                                        wordWrap: 'break-word',
                                        overflowWrap: 'break-word',
                                        whiteSpace: 'normal'
                                    }}>
                                        {event.title}
                                    </h3>

                                    {/* Date & Time */}
                                    <p style={{
                                        fontSize: '12px',
                                        color: '#475569',
                                        marginBottom: '4px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px'
                                    }}>
                                        <CalendarIcon /> {formatEventDate(event.date_iso)}
                                    </p>

                                    {/* Location */}
                                    <p style={{
                                        fontSize: '12px',
                                        color: '#64748b',
                                        marginBottom: '12px',
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: '6px'
                                    }}>
                                        <MapPinIcon />
                                        <span style={{
                                            wordWrap: 'break-word',
                                            overflowWrap: 'break-word',
                                            whiteSpace: 'normal'
                                        }}>
                                            {event.location}
                                        </span>
                                    </p>

                                    {/* Click hint */}
                                    <p style={{
                                        fontSize: '10px',
                                        textAlign: 'center',
                                        color: '#9ca3af',
                                        paddingTop: '8px',
                                        borderTop: '1px solid #e2e8f0'
                                    }}>
                                        Click for details
                                    </p>
                                </div>
                            </Tooltip>
                        </Marker>
                    )
                ))}
            </MapContainer>

            {/* ===== FLOATING LEGEND ===== */}
            <div className="absolute bottom-6 left-6 z-[1000] bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-white/50 shadow-lg">
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 pb-2 border-b border-gray-100/50">
                    Categories
                </h4>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                    {[
                        { label: 'Music', color: CATEGORY_COLORS.music },
                        { label: 'Arts', color: CATEGORY_COLORS.art },
                        { label: 'Nature', color: CATEGORY_COLORS.nature },
                        { label: 'Food', color: CATEGORY_COLORS.food },
                        { label: 'Sports', color: CATEGORY_COLORS.sports },
                        { label: 'Family', color: CATEGORY_COLORS.family },
                        { label: 'Comedy', color: CATEGORY_COLORS.comedy },
                        { label: 'Education', color: CATEGORY_COLORS.educational },
                        { label: 'Fitness', color: CATEGORY_COLORS.fitness },
                        { label: 'Film', color: CATEGORY_COLORS.film },
                        { label: 'Shopping', color: CATEGORY_COLORS.shopping },
                        { label: 'Pets', color: CATEGORY_COLORS.pets },
                    ].map((item) => (
                        <div key={item.label} className="flex items-center gap-2 group cursor-default">
                            <span
                                className="w-2.5 h-2.5 rounded-full ring-2 ring-white shadow-sm transition-all duration-300 group-hover:scale-125"
                                style={{ backgroundColor: item.color }}
                            />
                            <span className="text-[11px] font-medium text-slate-600 group-hover:text-slate-900 transition-colors">
                                {item.label}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default TulsaMap;