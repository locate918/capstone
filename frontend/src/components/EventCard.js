/**
 * EventCard Component
 * ===================
 * Displays a single event in a card format.
 *
 * PROPS:
 * - event: Event object with title, summary, location, original_url, venue_website, etc.
 * - onClick: Function called when card is clicked
 * - index: Position in list (used for staggered animation)
 */

import React from 'react';
import { MapPin, Calendar, Clock, ExternalLink, Building2, Share2 } from 'lucide-react';
import { THEME } from '../styles/theme';

const EventCard = ({ event, onClick, index = 0 }) => {
    // Format date for display
    const eventDate = event.date_iso ? new Date(event.date_iso) : null;
    
    const formattedDate = eventDate
        ? eventDate.toLocaleDateString(undefined, {
            weekday: 'short',
            month: 'short',
            day: 'numeric'
        })
        : 'Date TBA';

    const formattedTime = eventDate
        ? eventDate.toLocaleTimeString(undefined, {
            hour: 'numeric',
            minute: '2-digit'
        })
        : '';

    // Handle "Info" click - open source URL in new tab
    const handleViewEvent = (e) => {
        e.stopPropagation();
        if (event.original_url) {
            window.open(event.original_url, '_blank', 'noopener,noreferrer');
        }
    };

    // Handle "Venue" click - open venue website in new tab
    const handleVenueClick = (e) => {
        e.stopPropagation();
        if (event.venue_website) {
            window.open(event.venue_website, '_blank', 'noopener,noreferrer');
        }
    };

    // Handle share button click
    const handleShare = async (e) => {
        e.stopPropagation();
        const shareData = {
            title: event.title,
            text: `Check out ${event.title} in Tulsa!`,
            url: event.original_url || window.location.href,
        };
        
        try {
            if (navigator.share) {
                await navigator.share(shareData);
            } else {
                await navigator.clipboard.writeText(shareData.url);
                alert('Link copied to clipboard!');
            }
        } catch (err) {
            console.log('Share cancelled or failed');
        }
    };

    const hasEventLink = Boolean(event.original_url);
    const hasVenueLink = Boolean(event.venue_website);
    const hasAnyLink = hasEventLink || hasVenueLink;

    return (
        <div
            onClick={() => onClick && onClick(event)}
            className="group rounded-xl border border-white/5 hover:border-[#d4af37]/30 transition-all duration-500 cursor-pointer overflow-hidden flex flex-col h-full relative hover:shadow-[0_10px_40px_-10px_rgba(0,0,0,0.5)] hover:-translate-y-2 animate-fade-up bg-[#0f172a]"
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

                {/* Share Button - Top Left */}
                <button
                    onClick={handleShare}
                    className="absolute top-4 left-4 p-2 rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white/70 hover:text-white hover:bg-black/60 transition-all opacity-0 group-hover:opacity-100"
                    title="Share event"
                >
                    <Share2 size={14} />
                </button>

                {/* Location Badge - Top Right */}
                {event.location && (
                    <div className="absolute top-4 right-4">
                        <span
                            className="text-[10px] font-bold tracking-wider bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 uppercase group-hover:border-[#d4af37]/50 transition-colors text-[#d4af37]"
                        >
                            {event.location}
                        </span>
                    </div>
                )}
            </div>

            {/* Content Section */}
            <div className="p-6 flex-1 flex flex-col -mt-12 relative z-10">
                {/* Date & Time Badge */}
                <div className="flex justify-between items-start mb-3">
                    <span className="text-xs font-semibold flex items-center gap-2 bg-black/60 px-3 py-1.5 rounded-full border border-white/10 backdrop-blur-md shadow-lg text-[#d4af37]">
                        <div className="flex items-center gap-1">
                            <Calendar size={12} />
                            {formattedDate}
                        </div>
                        {formattedTime && (
                            <>
                                <span className="w-1 h-1 rounded-full bg-white/30"></span>
                                <div className="flex items-center gap-1 text-slate-300">
                                    <Clock size={12} />
                                    {formattedTime}
                                </div>
                            </>
                        )}
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
                <div className="mt-auto pt-5 border-t border-white/5 flex flex-col gap-2 group-hover:border-white/10 transition-colors">
                    <div className="flex items-center justify-between">
                        {/* Location */}
                        <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate max-w-[40%]">
                            <MapPin size={12} className="shrink-0 text-[#d4af37]" />
                            <span className="truncate tracking-wide group-hover:text-slate-400 transition-colors font-medium">
                                {event.location}
                            </span>
                        </div>

                        {/* Action Buttons */}
                        {hasAnyLink ? (
                            <div className="flex items-center gap-2">
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
                        ) : (
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

                    {/* Address Row */}
                    {event.venue_address && (
                        <div className="text-[10px] text-slate-600 pl-4 truncate">
                            {event.venue_address}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default EventCard;