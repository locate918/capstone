/**
 * SavedEventsModal Component
 * ========================
 * Displays the user's bookmarked/saved events in a modal dialog.
 *
 * PROPS:
 * - isOpen: Boolean to control modal visibility
 * - onClose: Function called when modal should close
 * - user: Authenticated user object
 */

import React, { useEffect, useState } from 'react';
import { X, Heart, MapPin, Calendar } from 'lucide-react';
import { THEME, styles } from '../styles/theme';
import { fetchSavedEvents } from '../services/api';
import EventCard from './EventCard';

const SavedEventsModal = ({ isOpen, onClose, user }) => {
    const [savedEvents, setSavedEvents] = useState([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (isOpen && user) {
            loadSavedEvents();
        }
    }, [isOpen, user]);

    const loadSavedEvents = async () => {
        setIsLoading(true);
        try {
            const events = await fetchSavedEvents();
            setSavedEvents(events);
            console.log(`[DEBUG] Loaded ${events.length} saved events`);
        } catch (error) {
            console.error('Failed to load saved events:', error);
            setSavedEvents([]);
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[150] p-4">
            <div
                className="bg-[#1a1a2e] border border-[#D4AF37]/30 rounded-2xl max-w-4xl w-full shadow-2xl shadow-[#D4AF37]/10 flex flex-col max-h-[90vh]"
            >
                {/* Header */}
                <div className="p-6 border-b border-white/10 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <Heart size={24} className="text-[#D4AF37]" />
                        <h2 className="text-2xl font-serif text-white">Saved Events</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-white transition-colors"
                        title="Close"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 flex-1 overflow-y-auto">
                    {isLoading ? (
                        <div className="flex justify-center items-center h-32">
                            <div className="text-slate-400">Loading saved events...</div>
                        </div>
                    ) : savedEvents.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-32">
                            <Heart size={48} className="text-slate-600 mb-3" />
                            <p className="text-slate-400">No saved events yet</p>
                            <p className="text-sm text-slate-500">
                                Click the heart icon on events to save them
                            </p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {savedEvents.map((event, index) => (
                                <EventCard
                                    key={event.id}
                                    event={event}
                                    onClick={() => {
                                        // You can add navigation or modal action here
                                        console.log('Clicked saved event:', event.title);
                                    }}
                                    index={index}
                                    user={user}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10">
                    <button
                        onClick={onClose}
                        className="w-full px-6 py-2 bg-[#D4AF37]/10 hover:bg-[#D4AF37]/20 text-[#D4AF37] border border-[#D4AF37]/30 rounded-lg font-medium transition-all"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SavedEventsModal;