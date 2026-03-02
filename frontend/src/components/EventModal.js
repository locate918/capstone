/**
 * EventModal Component
 * ====================
 * Full-screen overlay showing detailed event information.
 * 
 * PROPS:
 * - event: Event object to display (null to hide modal)
 * - onClose: Function called when modal should close
 */

import React from 'react';
import { X, Sparkles, Star, ExternalLink, Clock, MapPin, Building2, Link } from 'lucide-react';
import { THEME, styles } from '../styles/theme';

const EventModal = ({ event, onClose }) => {
    // Don't render if no event selected
    if (!event) return null;

    // Safe access to nested properties
    const aiAnalysis = event.ai_analysis || {};
    const questions = event.common_questions || [];

    // Format date and time for display
    const formatDateTime = (isoString) => {
        if (!isoString) return { date: 'Date TBA', time: null };
        const date = new Date(isoString);
        return {
            date: date.toLocaleDateString(undefined, {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric'
            }),
            time: date.toLocaleTimeString(undefined, {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            })
        };
    };

    const { date, time } = formatDateTime(event.date_iso);

    return (
        <div
            className="fixed inset-0 bg-black/90 backdrop-blur-lg flex items-center justify-center z-[100] p-4 overflow-y-auto animate-in fade-in duration-300"
            onClick={onClose}
        >
            <div
                className="rounded-2xl max-w-lg w-full shadow-2xl relative flex flex-col border border-white/10 overflow-hidden"
                style={{
                    backgroundColor: THEME.bgCard,
                    boxShadow: `0 0 50px -12px ${THEME.primaryGlow}`,
                    maxHeight: 'min(90vh, 800px)'
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* ===== HEADER IMAGE ===== */}
                <div className="relative h-56 sm:h-64 flex-shrink-0 overflow-hidden">
                    <img
                        src={event.imageUrl}
                        alt={event.title}
                        className="w-full h-full object-cover opacity-90"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] via-[#0f172a]/40 to-transparent" />

                    {/* Close Button */}
                    <button
                        onClick={onClose}
                        className="absolute top-4 right-4 p-2 bg-black/40 text-white rounded-full hover:bg-white/20 transition-all backdrop-blur-md border border-white/10 hover:scale-110 active:scale-95 z-10"
                    >
                        <X size={20} />
                    </button>

                    {/* Title Overlay */}
                    <div className="absolute bottom-4 left-6 right-6 sm:bottom-6 sm:left-8 sm:right-8">
                        <div className="flex items-center gap-2 text-xs font-bold tracking-widest uppercase mb-2 sm:mb-3" style={styles.primaryText}>
                            <Sparkles size={12} />
                            AI Curated • {event.originalSource || 'Local'}
                        </div>
                        <h2 className="text-2xl sm:text-3xl font-serif text-white leading-tight drop-shadow-xl line-clamp-3">
                            {event.title}
                        </h2>
                    </div>
                </div>

                {/* ===== SCROLLABLE CONTENT ===== */}
                <div className="flex-1 overflow-y-auto min-h-0">
                    <div className="p-6 sm:p-8">
                        {/* Date, Time & Location Info */}
                        <div className="mb-6 sm:mb-8 space-y-3">
                            {/* Date & Time */}
                            <div className="flex items-start gap-3 text-slate-300">
                                <Clock size={18} className="text-[#d4af37] shrink-0 mt-0.5" />
                                <div>
                                    <p className="font-medium text-white">{date}</p>
                                    {time && (
                                        <p className="text-sm text-slate-400">{time}</p>
                                    )}
                                </div>
                            </div>

                            {/* Venue & Address */}
                            {(event.location || event.venue_address) && (
                                <div className="flex items-start gap-3 text-slate-300">
                                    <MapPin size={18} className="text-[#d4af37] shrink-0 mt-0.5" />
                                    <div>
                                        {event.location && (
                                            <p className="font-medium text-white">{event.location}</p>
                                        )}
                                        {event.venue_address && (
                                            <p className="text-sm text-slate-400">{event.venue_address}</p>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Venue Website */}
                            {event.venue_website && (
                                <div className="flex items-start gap-3 text-slate-300">
                                    <Building2 size={18} className="text-[#d4af37] shrink-0 mt-0.5" />
                                    <a
                                        href={event.venue_website}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-sm text-[#d4af37] hover:text-[#e5c04b] hover:underline transition-colors break-all"
                                    >
                                        {event.venue_website.replace(/^https?:\/\/(www\.)?/, '')}
                                    </a>
                                </div>
                            )}

                            
                        </div>

                        {/* Summary */}
                        <p className="text-slate-300 mb-6 sm:mb-8 leading-relaxed font-light text-base sm:text-lg">
                            {event.summary}
                        </p>

                        {/* Atmosphere Analysis */}
                        {(aiAnalysis.noise_level || aiAnalysis.networking_pressure || aiAnalysis.crowd_type) && (
                            <div className="mb-6 sm:mb-8">
                                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <Star size={12} style={styles.primaryText} />
                                    Atmosphere Check
                                </h3>
                                <div className="grid grid-cols-3 gap-2 sm:gap-3 text-center">
                                    {[
                                        { label: "Noise", val: aiAnalysis.noise_level?.split('(')[0] || 'N/A' },
                                        { label: "Social", val: aiAnalysis.networking_pressure || 'N/A' },
                                        { label: "Crowd", val: aiAnalysis.crowd_type || 'N/A' }
                                    ].map((stat, i) => (
                                        <div key={i} className="bg-white/5 p-3 sm:p-4 rounded-xl border border-white/5 hover:border-white/10 hover:bg-white/10 transition-colors">
                                            <div className="font-medium text-xs sm:text-sm mb-1" style={styles.primaryText}>{stat.val}</div>
                                            <div className="text-[9px] sm:text-[10px] uppercase font-bold text-slate-500">{stat.label}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Q&A Section */}
                        {questions.length > 0 && (
                            <div className="mb-6 sm:mb-8">
                                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">
                                    Concierge Details
                                </h3>
                                <div className="space-y-4">
                                    {questions.map((item, idx) => (
                                        <div key={idx} className="flex gap-4 text-sm group">
                                            <div className="w-[2px] rounded-full bg-gradient-to-b from-[#d4af37] to-transparent opacity-50 group-hover:opacity-100 transition-all duration-500" />
                                            <div>
                                                <p className="font-medium text-slate-200 mb-1 group-hover:text-white transition-colors">
                                                    {item.q}
                                                </p>
                                                <p className="text-slate-400 font-light">{item.a}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* ===== FOOTER ===== */}
                <div className="p-4 sm:p-6 border-t border-white/5 bg-black/20 flex-shrink-0">
                    <a
                        href={event.original_url || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-full text-black text-center py-3 sm:py-4 rounded-xl font-bold tracking-wide flex justify-center items-center gap-2 shadow-lg hover:brightness-110 hover:scale-[1.02] active:scale-[0.98] transition-all"
                        style={styles.primaryBg}
                    >
                        View Original Listing  <ExternalLink size={16} />
                    </a>
                </div>
            </div>
        </div>
    );
};

export default EventModal;