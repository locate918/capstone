/**
 * UserProfileModal.js - User Profile Modal Component
 * ===================================================
 * Modal for viewing and editing user profile information.
 * Allows editing of:
 * - Display Name
 * - Location Preference
 * - Search Radius (miles)
 * - Max Price
 * - Family Friendly Only toggle
 */

import React, { useState, useEffect } from 'react';
import { X, Save, AlertCircle, MapPin, DollarSign, Users, MapPinIcon, Brain } from 'lucide-react';
import { updateUserPreferences } from '../services/api';

const UserProfileModal = ({ isOpen, onClose, user, onUpdate }) => {
    const [formData, setFormData] = useState({
        name: '',
        location_preference: '',
        radius_miles: 15,
        price_max: null,
        family_friendly_only: false,
        use_smart_search: true,
    });

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    // Populate form with current user data
    useEffect(() => {
        if (user?.backend_user) {
            setFormData({
                name: user.name || '',
                location_preference: user.backend_user.location_preference || '',
                radius_miles: user.backend_user.radius_miles || 15,
                price_max: user.backend_user.price_max || null,
                family_friendly_only: user.backend_user.family_friendly_only || false,
                use_smart_search: user.backend_user.use_smart_search !== false, // Default to true
            });
        }
    }, [user, isOpen]);

    if (!isOpen) return null;

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked :
                type === 'number' ? (value ? parseFloat(value) : null) :
                    value
        }));
        setError(null);
    };

    const handleSave = async () => {
        setLoading(true);
        setError(null);
        setSuccess(false);

        try {
            const payload = {
                location_preference: formData.location_preference || null,
                radius_miles: formData.radius_miles,
                price_max: formData.price_max,
                family_friendly_only: formData.family_friendly_only,
                use_smart_search: formData.use_smart_search,
            };

            await updateUserPreferences(payload);
            setSuccess(true);

            // Call parent update handler
            if (onUpdate) {
                onUpdate(formData);
            }

            // Close modal after 1.5 seconds
            setTimeout(() => {
                setSuccess(false);
                onClose();
            }, 1500);
        } catch (err) {
            setError(err.message || 'Failed to save profile');
            console.error('Profile update error:', err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[150] p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#f8f1e0] border border-[#D4AF37]/30 rounded-2xl max-w-md w-full p-6 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-serif text-slate-900">
                        My Profile
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                    >
                        <X size={20} className="text-slate-500" />
                    </button>
                </div>

                {/* Success Message */}
                {success && (
                    <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                        <p className="text-sm text-green-700 font-medium">✓ Profile saved successfully!</p>
                    </div>
                )}

                {/* Error Message */}
                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex gap-2">
                        <AlertCircle size={16} className="text-red-600 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-red-700">{error}</p>
                    </div>
                )}

                {/* Email Display (Read-only) */}
                <div className="mb-6 pb-6 border-b border-slate-200">
                    <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                        Email Address
                    </label>
                    <p className="text-slate-800 font-medium">{user?.email}</p>
                    <p className="text-xs text-slate-500 mt-1">Email cannot be changed</p>
                </div>

                {/* Form Fields */}
                <div className="space-y-5">
                    {/* Location Preference */}
                    <div>
                        <label htmlFor="location" className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            <MapPin size={14} className="inline mr-1" />
                            Location Preference
                        </label>
                        <input
                            type="text"
                            id="location"
                            name="location_preference"
                            placeholder="e.g., Downtown Tulsa, Broken Arrow"
                            value={formData.location_preference}
                            onChange={handleChange}
                            className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37]"
                        />
                        <p className="text-xs text-slate-500 mt-1">Where do you prefer to look for events?</p>
                    </div>

                    {/* Search Radius */}
                    <div>
                        <label htmlFor="radius" className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            <MapPinIcon size={14} className="inline mr-1" />
                            Search Radius
                        </label>
                        <div className="flex items-center gap-3">
                            <input
                                type="range"
                                id="radius"
                                name="radius_miles"
                                min="1"
                                max="50"
                                value={formData.radius_miles}
                                onChange={handleChange}
                                className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#D4AF37]"
                            />
                            <span className="text-sm font-semibold text-slate-800 min-w-12">
                                {formData.radius_miles} mi
                            </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">How far are you willing to travel?</p>
                    </div>

                    {/* Max Price */}
                    <div>
                        <label htmlFor="price" className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            <DollarSign size={14} className="inline mr-1" />
                            Max Price Per Event
                        </label>
                        <input
                            type="number"
                            id="price"
                            name="price_max"
                            placeholder="No limit"
                            min="0"
                            step="10"
                            value={formData.price_max || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37]"
                        />
                        <p className="text-xs text-slate-500 mt-1">Leave blank for no price limit</p>
                    </div>

                    {/* Family Friendly Toggle */}
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <label className="flex items-center gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                name="family_friendly_only"
                                checked={formData.family_friendly_only}
                                onChange={handleChange}
                                className="w-4 h-4 rounded border-slate-300 text-[#D4AF37] focus:ring-[#D4AF37] cursor-pointer"
                            />
                            <span className="flex items-center gap-2 text-sm font-medium text-slate-700">
                                <Users size={14} />
                                Only show family-friendly events
                            </span>
                        </label>
                        <p className="text-xs text-slate-500 mt-2 ml-7">Filter events to family-appropriate options</p>
                    </div>

                    {/* Smart Search Toggle */}
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <label className="flex items-center gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                name="use_smart_search"
                                checked={formData.use_smart_search}
                                onChange={handleChange}
                                className="w-4 h-4 rounded border-slate-300 text-[#D4AF37] focus:ring-[#D4AF37] cursor-pointer"
                            />
                            <span className="flex items-center gap-2 text-sm font-medium text-slate-900">
                                <Brain size={14} />
                                Enable AI Smart Search
                            </span>
                        </label>
                        <p className="text-xs text-slate-600 mt-2 ml-7">Use AI to understand natural language queries like "jazz concerts under $30"</p>
                    </div>
                </div>

                {/* Footer Buttons */}
                <div className="flex gap-3 mt-8 pt-6 border-t border-slate-200">
                    <button
                        onClick={onClose}
                        disabled={loading}
                        className="flex-1 px-4 py-3 rounded-lg border border-slate-200 text-slate-700 font-medium text-sm hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={loading}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[#D4AF37] hover:bg-[#C5A028] text-white font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Save size={16} />
                        {loading ? 'Saving...' : 'Save Changes'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default UserProfileModal;