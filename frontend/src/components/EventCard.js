/**
 * EventCard Component
 * ===================
 * Displays a single event in a card format.
 *
 * PROPS:
 * - event: Event object with title, summary, location, original_url, venue_website, etc.
 * - onClick: Function called when card is clicked
 * - index: Position in list (used for staggered animation)
 * - user: Authenticated user object
 * - isSaved: Boolean indicating if event is in user's saved events
 * - onSaveChange: Optional callback function when save state changes
 *
 * LINKS:
 * - "Venue" button → venue_website (actual venue's website)
 * - "Save" button → bookmark event for later (toggles save/unsave)
 */

import React, { useState } from 'react';
import { Calendar, Building2, Heart, Tag } from 'lucide-react';
import { THEME, styles } from '../styles/theme';
import { recordInteraction, saveEvent, unsaveEvent } from '../services/api';

const EventCard = ({ event, onClick, index = 0, user, isSaved = false, onSaveChange }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [saved, setSaved] = useState(isSaved);
    const [imageError, setImageError] = useState(false);

    // Format date for display
    const formattedDate = event.date_iso
        ? new Date(event.date_iso).toLocaleDateString(undefined, {
            weekday: 'short',
            month: 'short',
            day: 'numeric'
        })
        : 'Date TBA';

    // Get event type from vibe_tags or categories
    const eventType = event.vibe_tags?.[0] || event.categories?.[0] || 'Event';

    // Helper for recording interactions
    const logClick = (type) => {
        if (user) {
            console.log(`[DEBUG] Event ${type}: ${event.title}`);
            recordInteraction({
                userId: user.id,
                eventId: event.id,
                interactionType: type,
                eventCategories: event.categories
            });
        } else {
            console.warn("[DEBUG] logClick called but user is missing", event);
        }
    };

    // Handle "Venue" click - open venue website in new tab
    const handleVenueClick = (e) => {
        e.stopPropagation(); // Don't trigger card onClick
        logClick('clicked');
        if (event.venue_website) {
            window.open(event.venue_website, '_blank', 'noopener,noreferrer');
        }
    };

    // Handle "Save/Unsave" click - toggle bookmark state
    const handleToggleSaveEvent = async (e) => {
        e.stopPropagation(); // Don't trigger card onClick
        if (!user) {
            console.warn("[DEBUG] Save clicked but user is missing");
            return;
        }

        setIsLoading(true);
        try {
            if (saved) {
                // Unsave the event
                await unsaveEvent(event.id);
                console.log(`[DEBUG] Event unsaved: ${event.title}`);
                logClick('unsaved');
                setSaved(false);
            } else {
                // Save the event
                await saveEvent(event.id);
                console.log(`[DEBUG] Event saved: ${event.title}`);
                logClick('saved');
                setSaved(true);
            }
            // Notify parent if callback provided
            if (onSaveChange) {
                onSaveChange(event.id, !saved);
            }
        } catch (error) {
            console.error("Failed to toggle save event:", error);
        } finally {
            setIsLoading(false);
        }
    };

    // Handle image load error
    const handleImageError = () => {
        console.warn(`[DEBUG] Image failed to load: ${event.imageUrl}`);
        setImageError(true);
    };

    // Check which links are available
    const hasVenueLink = Boolean(event.venue_website);

    // Determine if we have a valid image URL
    const hasImageUrl = event.imageUrl && event.imageUrl.trim().length > 0;

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
            <div className="h-52 relative overflow-hidden bg-gradient-to-br from-slate-700 to-slate-900">
                {hasImageUrl && !imageError ? (
                    <img
                        src={event.imageUrl}
                        alt={event.title}
                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-1000 ease-out"
                        onError={handleImageError}
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-700 to-slate-900">
                        <img
                            src="/assets/Logo.png"
                            alt="Locate918"
                            className="w-20 h-20 object-contain opacity-40"
                        />
                    </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] via-transparent to-transparent opacity-80" />

                {/* Venue Name Badge - Properly constrained and truncated */}
                {event.location && (
                    <div className="absolute top-4 right-4 left-4">
                        <span
                            className="inline-block text-[10px] font-bold tracking-wider bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 uppercase group-hover:border-[#d4af37]/50 transition-colors truncate max-w-full"
                            style={styles.primaryText}
                            title={event.location}
                        >
                            {event.location}
                        </span>
                    </div>
                )}
            </div>

            {/* Content Section */}
            <div className="p-6 flex-1 flex flex-col -mt-12 relative z-10">
                {/* Date Badge */}
                <div className="flex justify-end mb-3">
                    <span
                        className="text-xs font-semibold flex items-center gap-1 bg-black/60 px-3 py-1.5 rounded-full border border-white/10 backdrop-blur-md shadow-lg shrink-0"
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
                    {/* Event Type */}
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate max-w-[40%]">
                        <Tag size={12} className="shrink-0" />
                        <span className="truncate tracking-wide group-hover:text-slate-400 transition-colors capitalize">
                            {eventType}
                        </span>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2">
                        {/* Save Button - Heart Icon (toggles save/unsave) */}
                        {user && (
                            <button
                                onClick={handleToggleSaveEvent}
                                disabled={isLoading}
                                className={`flex items-center justify-center text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${saved
                                    ? 'bg-[#d4af37]/20 text-[#d4af37] border border-[#d4af37]/40 hover:bg-[#d4af37]/30'
                                    : 'bg-[#d4af37]/10 text-[#d4af37] border border-[#d4af37]/20 hover:bg-[#d4af37]/20 hover:border-[#d4af37]/40'
                                    }`}
                                title={saved ? "Remove from saved" : "Save event"}
                            >
                                <Heart size={12} className={`${saved ? 'fill-current' : ''} ${isLoading ? "animate-pulse" : ""}`} />
                            </button>
                        )}

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
                    </div>
                </div>
            </div>
        </div>
    );
};

export default EventCard;