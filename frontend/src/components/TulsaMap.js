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
 * - Glassmorphism popups and tooltips
 * - Floating legend
 */

import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Tooltip, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { THEME } from '../styles/theme';

// =============================================================================
// CATEGORY COLORS
// =============================================================================

const CATEGORY_COLORS = {
  exclusive: THEME.primary,  // Gold
  business: '#0f172a',       // Slate 900
  nightlife: '#7c3aed',      // Violet 600
  chill: '#059669',          // Emerald 600
  default: '#64748b'         // Slate 500
};

// =============================================================================
// CUSTOM MAP STYLES (injected once)
// =============================================================================

const injectMapStyles = () => {
  if (document.getElementById('tulsa-map-styles')) return;
  
  const style = document.createElement('style');
  style.id = 'tulsa-map-styles';
  style.innerHTML = `
    @keyframes pulse-gold {
      0% { transform: scale(1); filter: drop-shadow(0 0 0 rgba(212, 175, 55, 0)); }
      50% { transform: scale(1.05); filter: drop-shadow(0 0 10px rgba(212, 175, 55, 0.5)); }
      100% { transform: scale(1); filter: drop-shadow(0 0 0 rgba(212, 175, 55, 0)); }
    }
    .marker-exclusive svg {
      animation: pulse-gold 2s infinite ease-in-out;
    }
    .leaflet-popup-content-wrapper {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(8px);
      border-radius: 12px;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
      padding: 0; 
    }
    .leaflet-popup-content {
      margin: 0;
      width: auto !important;
    }
    .leaflet-popup-tip {
      background: rgba(255, 255, 255, 0.95);
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

const createPinIcon = (color, isExclusive = false) => {
  return new L.DivIcon({
    className: `bg-transparent border-none ${isExclusive ? 'marker-exclusive' : ''}`, 
    html: `
      <svg width="36" height="48" viewBox="0 0 30 42" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 4px 6px rgba(0, 0, 0, 0.3));">
        <path d="M15 0C6.71573 0 0 6.71573 0 15C0 26.25 15 42 15 42C15 42 30 26.25 30 15C30 6.71573 23.2843 0 15 0Z" fill="${color}"/>
        <circle cx="15" cy="15" r="6" fill="white" fill-opacity="0.9"/>
      </svg>
    `,
    iconSize: [36, 48],
    iconAnchor: [18, 48],
    popupAnchor: [0, -42]
  });
};

const getCategoryIcon = (tags) => {
  const lowerTags = (tags || []).map(t => t.toLowerCase());

  if (lowerTags.includes('exclusive')) return createPinIcon(CATEGORY_COLORS.exclusive, true);
  if (lowerTags.includes('business')) return createPinIcon(CATEGORY_COLORS.business);
  if (lowerTags.includes('nightlife') || lowerTags.includes('music')) return createPinIcon(CATEGORY_COLORS.nightlife);
  if (lowerTags.includes('chill') || lowerTags.includes('wellness') || lowerTags.includes('outdoors')) return createPinIcon(CATEGORY_COLORS.chill);
  
  return createPinIcon(CATEGORY_COLORS.default);
};

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
              icon={getCategoryIcon(event.vibe_tags)} 
              eventHandlers={{
                click: () => onMarkerClick(event),
                mouseover: (e) => e.target.openTooltip(),
                mouseout: (e) => e.target.closeTooltip(),
              }}
            >
              {/* Tooltip (on hover) */}
              <Tooltip 
                direction="top" 
                offset={[0, -45]} 
                opacity={1}
              >
                <div className="bg-white/95 backdrop-blur-md px-3 py-2 rounded-lg shadow-lg border border-gray-100">
                  <h3 className="font-bold text-xs text-slate-900 leading-tight">{event.title}</h3>
                </div>
              </Tooltip>

              {/* Popup (on click) */}
              <Popup>
                <div className="text-center min-w-[180px] p-4">
                  <div className="mb-2">
                    <span className="text-[10px] font-bold tracking-widest text-gray-400 uppercase">
                      {event.vibe_tags?.[0] || 'Local'}
                    </span>
                  </div>
                  <h3 className="font-bold text-lg mb-1 text-slate-900 font-serif leading-tight">
                    {event.title}
                  </h3>
                  <p className="text-xs text-gray-500 mb-4">{event.location}</p>
                  
                  <button 
                    onClick={() => onMarkerClick(event)}
                    className="w-full text-xs text-white px-4 py-2.5 rounded-full transition-all hover:scale-105 active:scale-95 font-semibold shadow-md"
                    style={{ backgroundColor: THEME.primary, boxShadow: `0 4px 12px ${THEME.primary}40` }}
                  >
                    View Details
                  </button>
                </div>
              </Popup>
            </Marker>
          )
        ))}
      </MapContainer>

      {/* ===== FLOATING LEGEND ===== */}
      <div className="absolute bottom-6 left-6 z-[1000] bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-white/50 shadow-lg">
        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 pb-2 border-b border-gray-100/50">
          Vibe Check
        </h4>
        <div className="flex flex-col gap-2.5">
          {[
            { label: 'Exclusive', color: CATEGORY_COLORS.exclusive, glow: true },
            { label: 'Business', color: CATEGORY_COLORS.business },
            { label: 'Nightlife', color: CATEGORY_COLORS.nightlife },
            { label: 'Chill / Wellness', color: CATEGORY_COLORS.chill },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-3 group cursor-default">
              <span 
                className={`w-2.5 h-2.5 rounded-full ring-2 ring-white transition-all duration-300 group-hover:scale-125 ${item.glow ? 'shadow-[0_0_8px_rgba(212,175,55,0.6)]' : 'shadow-sm'}`}
                style={{ backgroundColor: item.color }} 
              />
              <span className="text-xs font-medium text-slate-600 group-hover:text-slate-900 transition-colors">
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