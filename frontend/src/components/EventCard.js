/**
 * EventCard Component
 * ===================
 * Displays a single event in a card format.
 * 
 * PROPS:
 * - event: Event object with title, summary, location, etc.
 * - onClick: Function called when card is clicked
 * - index: Position in list (used for staggered animation)
 */

import React from 'react';
import { MapPin, Calendar } from 'lucide-react';
import { THEME, styles } from '../styles/theme';

const EventCard = ({ event, onClick, index = 0 }) => {
  // Format date for display
  const formattedDate = event.date_iso 
    ? new Date(event.date_iso).toLocaleDateString(undefined, { 
        weekday: 'short', 
        month: 'short', 
        day: 'numeric' 
      })
    : 'Date TBA';

  return (
    <div 
      onClick={() => onClick(event)}
      className="group rounded-xl border border-white/5 hover:border-[#d4af37]/30 transition-all duration-500 cursor-pointer overflow-hidden flex flex-col h-full relative hover:shadow-[0_10px_40px_-10px_rgba(0,0,0,0.5)] hover:-translate-y-2 animate-fade-up"
      style={{ 
        backgroundColor: THEME.bgCard,
        animationDelay: `${index * 150}ms` 
      }}
    >
      {/* Image Section */}
      <div className="h-52 relative overflow-hidden">
        <img 
          src={event.imageUrl} 
          alt={event.title} 
          className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-1000 ease-out" 
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] via-transparent to-transparent opacity-80" />
        
        {/* Source Badge */}
        {event.originalSource && (
          <div className="absolute top-4 right-4">
            <span 
              className="text-[10px] font-bold tracking-wider bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 uppercase group-hover:border-[#d4af37]/50 transition-colors"
              style={styles.primaryText}
            >
              {event.originalSource}
            </span>
          </div>
        )}
      </div>

      {/* Content Section */}
      <div className="p-6 flex-1 flex flex-col -mt-12 relative z-10">
        {/* Date Badge */}
        <div className="flex justify-between items-start mb-3">
          <span 
            className="text-xs font-semibold flex items-center gap-1 bg-black/60 px-3 py-1.5 rounded-full border border-white/10 backdrop-blur-md shadow-lg"
            style={styles.primaryText}
          >
            <Calendar size={12} />
            {formattedDate}
          </span>
        </div>
        
        {/* Title */}
        <h3 className="text-xl font-serif text-white mb-3 leading-snug group-hover:text-[#d4af37] transition-colors duration-300">
          {event.title}
        </h3>
        
        {/* Summary */}
        <p className="text-sm text-slate-400 mb-6 line-clamp-2 font-light leading-relaxed">
          {event.summary}
        </p>

        {/* Footer */}
        <div className="mt-auto pt-5 border-t border-white/5 flex items-center justify-between group-hover:border-white/10 transition-colors">
          {/* Location */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate max-w-[60%]">
            <MapPin size={12} className="shrink-0" />
            <span className="truncate tracking-wide group-hover:text-slate-400 transition-colors">
              {event.location}
            </span>
          </div>
          
          {/* Tags */}
          <div className="flex gap-1.5">
            {event.vibe_tags?.slice(0, 2).map((tag, i) => (
              <span 
                key={i} 
                className="text-[10px] font-medium bg-white/5 text-slate-300 px-2.5 py-1 rounded border border-white/5 group-hover:bg-white/10 transition-colors"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventCard;