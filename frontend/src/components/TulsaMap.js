/**
 * TulsaMap Component
 * ==================
 * Interactive Leaflet map showing event locations with custom markers.
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Tooltip, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import { X, ChevronRight, MapPin, Calendar } from 'lucide-react';

// =============================================================================
// CATEGORY COLORS
// =============================================================================

const CATEGORY_COLORS = {
    music: '#7c3aed',
    art: '#ec4899',
    nature: '#059669',
    food: '#f59e0b',
    sports: '#ef4444',
    family: '#06b6d4',
    comedy: '#8b5cf6',
    educational: '#3b82f6',
    fitness: '#10b981',
    film: '#6366f1',
    shopping: '#f97316',
    pets: '#84cc16',
    default: '#64748b'
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
    .marker-cluster {
      background: rgba(212, 175, 55, 0.3);
      border: 2px solid #d4af37;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .marker-cluster div {
      background: #d4af37;
      border-radius: 50%;
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 12px;
      color: #1a1a2e;
    }
    .marker-cluster-small { background: rgba(212, 175, 55, 0.4); }
    .marker-cluster-medium { background: rgba(212, 175, 55, 0.5); }
    .marker-cluster-large { background: rgba(212, 175, 55, 0.6); }
  `;
    document.head.appendChild(style);
};

// =============================================================================
// CLUSTER ICON
// =============================================================================

const createClusterIcon = (cluster) => {
    const count = cluster.getChildCount();
    let size = 'small';
    if (count >= 10) size = 'medium';
    if (count >= 20) size = 'large';

    return L.divIcon({
        html: `<div>${count}</div>`,
        className: `marker-cluster marker-cluster-${size}`,
        iconSize: L.point(40, 40, true),
    });
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

const getCategoryIcon = (tags, isHovered = false) => {
    const lowerTags = (tags || []).map(t => t.toLowerCase());
    const tagString = lowerTags.join(' ');

    if (tagString.includes('music') || tagString.includes('concert') || tagString.includes('live') || tagString.includes('band') || tagString.includes('jazz') || tagString.includes('rock')) {
        return createPinIcon(CATEGORY_COLORS.music, isHovered);
    }
    if (tagString.includes('art') || tagString.includes('theater') || tagString.includes('theatre') || tagString.includes('dance') || tagString.includes('culture') || tagString.includes('gallery') || tagString.includes('performance')) {
        return createPinIcon(CATEGORY_COLORS.art, isHovered);
    }
    if (tagString.includes('nature') || tagString.includes('outdoor') || tagString.includes('park') || tagString.includes('garden') || tagString.includes('hiking') || tagString.includes('trail')) {
        return createPinIcon(CATEGORY_COLORS.nature, isHovered);
    }
    if (tagString.includes('food') || tagString.includes('drink') || tagString.includes('dining') || tagString.includes('culinary') || tagString.includes('restaurant') || tagString.includes('wine') || tagString.includes('beer') || tagString.includes('brewery')) {
        return createPinIcon(CATEGORY_COLORS.food, isHovered);
    }
    if (tagString.includes('sport') || tagString.includes('game') || tagString.includes('tournament') || tagString.includes('football') || tagString.includes('basketball') || tagString.includes('baseball')) {
        return createPinIcon(CATEGORY_COLORS.sports, isHovered);
    }
    if (tagString.includes('family') || tagString.includes('kid') || tagString.includes('children') || tagString.includes('child')) {
        return createPinIcon(CATEGORY_COLORS.family, isHovered);
    }
    if (tagString.includes('comedy') || tagString.includes('comedian') || tagString.includes('funny') || tagString.includes('standup') || tagString.includes('stand-up')) {
        return createPinIcon(CATEGORY_COLORS.comedy, isHovered);
    }
    if (tagString.includes('education') || tagString.includes('museum') || tagString.includes('history') || tagString.includes('lecture') || tagString.includes('workshop') || tagString.includes('class')) {
        return createPinIcon(CATEGORY_COLORS.educational, isHovered);
    }
    if (tagString.includes('fitness') || tagString.includes('wellness') || tagString.includes('yoga') || tagString.includes('workout') || tagString.includes('gym') || tagString.includes('run')) {
        return createPinIcon(CATEGORY_COLORS.fitness, isHovered);
    }
    if (tagString.includes('film') || tagString.includes('movie') || tagString.includes('cinema') || tagString.includes('screening')) {
        return createPinIcon(CATEGORY_COLORS.film, isHovered);
    }
    if (tagString.includes('shopping') || tagString.includes('market') || tagString.includes('fair') || tagString.includes('expo') || tagString.includes('trade')) {
        return createPinIcon(CATEGORY_COLORS.shopping, isHovered);
    }
    if (tagString.includes('pet') || tagString.includes('dog') || tagString.includes('cat') || tagString.includes('animal')) {
        return createPinIcon(CATEGORY_COLORS.pets, isHovered);
    }

    return createPinIcon(CATEGORY_COLORS.default, isHovered);
};

// =============================================================================
// MAP CONTROLLER (WITH HOVER TIMER)
// =============================================================================

const MapController = ({ hoveredEventId, events, onMapReady }) => {
    const map = useMap();
    const animationRef = useRef(null);
    const timeoutRef = useRef(null);

    // ========================================
    // HOVER TIMER CONFIGURATION
    // ========================================
    // Duration (in milliseconds) the user must hover before the map centers.
    // Adjust this value to change the responsiveness:
    // - 300ms: Quick, responsive
    // - 500ms: Balanced (default) — allows for natural browsing without snapping
    // - 800ms: Relaxed, requires intentional hover
    const HOVER_DELAY_MS = 500;

    useEffect(() => {
        if (onMapReady) {
            onMapReady(map);
        }

        const timers = [100, 300, 500].map(delay =>
            setTimeout(() => map.invalidateSize(), delay)
        );

        const handleResize = () => map.invalidateSize();
        window.addEventListener('resize', handleResize);

        return () => {
            timers.forEach(clearTimeout);
            window.removeEventListener('resize', handleResize);
        };
    }, [map, onMapReady]);

    useEffect(() => {
        // ========================================
        // CLEANUP PREVIOUS ANIMATION
        // ========================================
        if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
            animationRef.current = null;
        }

        // ========================================
        // CLEANUP PREVIOUS TIMEOUT (CRITICAL!)
        // ========================================
        // This prevents interim snaps when the user hovers over multiple cards quickly.
        // If the user moves to a different card before the timeout fires, we cancel
        // the pending map movement and start a fresh timer.
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }

        // ========================================
        // EARLY EXIT IF NO HOVER
        // ========================================
        if (!hoveredEventId) return;

        // ========================================
        // FIND HOVERED EVENT
        // ========================================
        const hoveredEvent = events.find(e => e.id === hoveredEventId);

        // ========================================
        // VALIDATE COORDINATES
        // ========================================
        if (
            hoveredEvent?.coordinates &&
            typeof hoveredEvent.coordinates.lat === 'number' &&
            typeof hoveredEvent.coordinates.lng === 'number' &&
            !isNaN(hoveredEvent.coordinates.lat) &&
            !isNaN(hoveredEvent.coordinates.lng) &&
            hoveredEvent.coordinates.lat !== 0 &&
            hoveredEvent.coordinates.lng !== 0
        ) {
            // ========================================
            // SET DEBOUNCE TIMER
            // ========================================
            // Wait HOVER_DELAY_MS before centering the map. This ensures:
            // 1. Accidental hovers while scrolling don't trigger map movement
            // 2. The map only moves when the user intentionally hovers for sustained duration
            // 3. Rapid card hopping is smooth (each new hover cancels the previous timeout)
            timeoutRef.current = setTimeout(() => {
                animationRef.current = requestAnimationFrame(() => {
                    try {
                        // ========================================
                        // CENTER MAP ON HOVERED PIN
                        // ========================================
                        // Smooth pan animation (duration: 0.3s) centers the map on the
                        // hovered event's coordinates at zoom level 15.
                        map.setView(
                            [hoveredEvent.coordinates.lat, hoveredEvent.coordinates.lng],
                            15,
                            { animate: true, duration: 0.3 }
                        );
                    } catch (error) {
                        // Silently ignore errors (stale event refs, etc.)
                    }
                });
            }, HOVER_DELAY_MS);
        }

        // ========================================
        // CLEANUP FUNCTION
        // ========================================
        // Called when:
        // 1. User stops hovering (hoveredEventId becomes null)
        // 2. User hovers a different card (hoveredEventId changes)
        // 3. Component unmounts
        // Ensures both the timeout and animation frame are cleared.
        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, [hoveredEventId, events, map, HOVER_DELAY_MS]);

    return null;
};

// =============================================================================
// HELPERS
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

const isValidCoordinates = (coords) => {
    return (
        coords &&
        typeof coords.lat === 'number' &&
        typeof coords.lng === 'number' &&
        !isNaN(coords.lat) &&
        !isNaN(coords.lng) &&
        coords.lat !== 0 &&
        coords.lng !== 0
    );
};

// =============================================================================
// COMPONENT
// =============================================================================

const TulsaMap = ({ events, onMarkerClick, hoveredEventId, className = "h-[500px]" }) => {
    const center = [36.1540, -95.9928];
    const containerRef = useRef(null);
    const mapInstanceRef = useRef(null);
    const [clusterEvents, setClusterEvents] = useState(null);
    const normalizedEvents = Array.isArray(events) ? events : [];

    useEffect(() => {
        injectMapStyles();
    }, []);

    const eventsByPosition = useMemo(() => {
        const lookup = new Map();
        normalizedEvents.forEach(event => {
            if (isValidCoordinates(event.coordinates)) {
                const key = `${event.coordinates.lat},${event.coordinates.lng}`;
                if (!lookup.has(key)) {
                    lookup.set(key, []);
                }
                lookup.get(key).push(event);
            }
        });
        return lookup;
    }, [normalizedEvents]);

    const eventsWithValidCoords = useMemo(() =>
        normalizedEvents.filter(event => isValidCoordinates(event.coordinates)),
        [normalizedEvents]
    );

    const handleMapReady = (map) => {
        mapInstanceRef.current = map;
    };

    const handleClusterClick = (e) => {
        const cluster = e.layer;
        const childMarkers = cluster.getAllChildMarkers();

        const eventsInCluster = [];
        childMarkers.forEach(marker => {
            const latlng = marker.getLatLng();
            const key = `${latlng.lat},${latlng.lng}`;
            const eventsAtPosition = eventsByPosition.get(key);
            if (eventsAtPosition) {
                eventsAtPosition.forEach(evt => {
                    if (!eventsInCluster.find(e => e.id === evt.id)) {
                        eventsInCluster.push(evt);
                    }
                });
            }
        });

        if (eventsInCluster.length > 0) {
            setClusterEvents(eventsInCluster);
        }
    };

    return (
        <div
            ref={containerRef}
            className={`relative rounded-2xl overflow-hidden ${className}`}
        >
            <MapContainer
                center={center}
                zoom={13}
                maxZoom={17}
                style={{ height: '100%', width: '100%' }}
                scrollWheelZoom={true}
                zoomControl={false}
            >
                <MapController
                    hoveredEventId={hoveredEventId}
                    events={eventsWithValidCoords}
                    onMapReady={handleMapReady}
                />

                <TileLayer
                    attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}@2x.png"
                />

                <MarkerClusterGroup
                    chunkedLoading
                    iconCreateFunction={createClusterIcon}
                    maxClusterRadius={50}
                    spiderfyOnMaxZoom={false}
                    zoomToBoundsOnClick={false}
                    disableClusteringAtZoom={18}
                    showCoverageOnHover={false}
                    eventHandlers={{
                        clusterclick: handleClusterClick
                    }}
                >
                    {eventsWithValidCoords.map((event) => (
                        <Marker
                            key={event.id}
                            position={[event.coordinates.lat, event.coordinates.lng]}
                            icon={getCategoryIcon(event.vibe_tags, event.id === hoveredEventId)}
                            eventHandlers={{
                                click: () => onMarkerClick(event),
                            }}
                        >
                            <Tooltip direction="top" offset={[0, -42]} opacity={1}>
                                <div style={{ width: '240px', padding: '16px' }}>
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
                    ))}
                </MarkerClusterGroup>
            </MapContainer>

            {/* Floating Legend */}
            <div className="absolute bottom-4 left-4 z-[1000] bg-white/80 backdrop-blur-md p-3 sm:p-4 rounded-xl sm:rounded-2xl border border-white/50 shadow-lg max-w-[140px] sm:max-w-none">
                <h4 className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 sm:mb-3 pb-1.5 sm:pb-2 border-b border-gray-100/50">
                    Categories
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 sm:gap-y-2">
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
                        <div key={item.label} className="flex items-center gap-1.5 sm:gap-2 group cursor-default">
                            <span
                                className="w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full ring-1 sm:ring-2 ring-white shadow-sm transition-all duration-300 group-hover:scale-125 flex-shrink-0"
                                style={{ backgroundColor: item.color }}
                            />
                            <span className="text-[10px] sm:text-[11px] font-medium text-slate-600 group-hover:text-slate-900 transition-colors truncate">
                                {item.label}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Bottom Sheet for Clustered Events */}
            {clusterEvents && (
                <div className="absolute inset-0 z-[1000] animate-slide-up">
                    {/* Backdrop scrim within the map */}
                    <div
                        className="absolute inset-0 bg-black/40"
                        onClick={() => setClusterEvents(null)}
                    />

                    {/* Bottom sheet anchored to bottom of map */}
                    <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl max-h-[85%] flex flex-col">

                        {/* Sticky header: drag handle + title bar with X — never scrolls away */}
                        <div className="flex-shrink-0 bg-white rounded-t-2xl">
                            <div className="flex justify-center pt-3 pb-2">
                                <div className="w-10 h-1 bg-slate-300 rounded-full" />
                            </div>

                            <div className="flex items-center justify-between px-4 pb-3 border-b border-slate-100">
                                <div className="flex items-center gap-2">
                                    <MapPin size={18} className="text-[#D4AF37]" />
                                    <span className="font-semibold text-slate-900">
                                        {clusterEvents.length} Events nearby
                                    </span>
                                </div>
                                <button
                                    onClick={() => setClusterEvents(null)}
                                    className="p-1.5 hover:bg-slate-100 rounded-full transition-colors"
                                >
                                    <X size={18} className="text-slate-500" />
                                </button>
                            </div>
                        </div>

                        {/* Scrollable event list */}
                        <div className="overflow-y-auto flex-1 overscroll-contain">
                            {clusterEvents.map((event) => (
                                <button
                                    key={event.id}
                                    onClick={() => {
                                        onMarkerClick(event);
                                        setClusterEvents(null);
                                    }}
                                    className="w-full flex items-center gap-3 p-4 hover:bg-slate-50 active:bg-slate-100 transition-colors text-left border-b border-slate-100 last:border-b-0"
                                >
                                    <div className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-slate-100">
                                        {event.imageUrl ? (
                                            <img
                                                src={event.imageUrl}
                                                alt={event.title}
                                                className="w-full h-full object-cover"
                                                onError={(e) => {
                                                    e.target.onerror = null;
                                                    e.target.src = '/assets/Logo.png';
                                                    e.target.className = 'w-full h-full object-contain p-2 opacity-50';
                                                }}
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center">
                                                <img src="/assets/Logo.png" alt="" className="w-8 h-8 opacity-40" />
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <h4 className="font-medium text-slate-900 text-sm line-clamp-1">
                                            {event.title}
                                        </h4>
                                        <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                                            <Calendar size={12} />
                                            {formatEventDate(event.date_iso)}
                                        </p>
                                        {event.location && (
                                            <p className="text-xs text-[#D4AF37] mt-0.5 line-clamp-1">
                                                {event.location}
                                            </p>
                                        )}
                                    </div>

                                    <ChevronRight size={18} className="text-slate-400 flex-shrink-0" />
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TulsaMap;