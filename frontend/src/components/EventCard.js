/**
 * EventCard Component
 * ===================
 * Displays a single event in a card format.
 *
 * PROPS:
 * - event: Event object with title, summary, location, original_url, venue_website, etc.
 * - onClick: Function called when card is clicked
 * - index: Position in list (used for staggered animation)
 *
 * LINKS:
 * - "Info" button → source_url (VisitTulsa/aggregator page with event details)
 * - "Venue" button → venue_website (actual venue's website)
 */

import React from 'react';
import { MapPin, Calendar, ExternalLink, Building2 } from 'lucide-react';
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

    // Handle "Info" click - open source URL in new tab
    const handleViewEvent = (e) => {
        e.stopPropagation(); // Don't trigger card onClick
        if (event.original_url) {
            window.open(event.original_url, '_blank', 'noopener,noreferrer');
        }
    };

    // Handle "Venue" click - open venue website in new tab
    const handleVenueClick = (e) => {
        e.stopPropagation(); // Don't trigger card onClick
        if (event.venue_website) {
            window.open(event.venue_website, '_blank', 'noopener,noreferrer');
        }
    };

    // Check which links are available
    const hasEventLink = Boolean(event.original_url);
    const hasVenueLink = Boolean(event.venue_website);
    const hasAnyLink = hasEventLink || hasVenueLink;

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

                {/* Venue Badge - Show venue name, not aggregator source */}
                {event.location && (
                    <div className="absolute top-4 right-4">
                        <span
                            className="text-[10px] font-bold tracking-wider bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 uppercase group-hover:border-[#d4af37]/50 transition-colors"
                            style={styles.primaryText}
                        >
                            {event.location}
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
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate max-w-[40%]">
                        <MapPin size={12} className="shrink-0" />
                        <span className="truncate tracking-wide group-hover:text-slate-400 transition-colors">
                            {event.location}
                        </span>
                    </div>

                    {/* Action Buttons */}
                    {hasAnyLink && (
                        <div className="flex items-center gap-2">
                            {/* Venue Website Button - Gold/Primary */}
                            {hasVenueLink && (
                                <button
                                    onClick={handleVenueClick}
                                    className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg bg-[#d4af37]/10 text-[#d4af37] border border-[#d4af37]/20 hover:bg-[#d4af37]/20 hover:border-[#d4af37]/40 transition-all duration-300"
                                    title="Visit venue website"
                                >
                                    <Building2 size={11} />
                                    <span>Venue</span>
                                </button>
                            )}

                            {/* Event Info Button - Subtle/Secondary */}
                            {hasEventLink && (
                                <button
                                    onClick={handleViewEvent}
                                    className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white transition-all duration-300"
                                    title="View event details"
                                >
                                    <span>Info</span>
                                    <ExternalLink size={10} />
                                </button>
                            )}
                        </div>
                    )}

                    {/* Tags - show if no links available */}
                    {!hasAnyLink && (
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
                    )}
                </div>
            </div>
        </div>
    );
};

export default EventCard;