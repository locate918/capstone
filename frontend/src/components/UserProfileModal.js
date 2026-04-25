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
 * - Category Preferences (Interests)
 */

import React, { useState, useEffect } from 'react';
import { X, Save, AlertCircle, MapPin, DollarSign, Users, MapPinIcon, Brain, Heart, Star, ChevronDown, ChevronUp } from 'lucide-react';
import { updateUserPreferences, addUserPreference } from '../services/api';

const CATEGORIES = [
    "Music",
    "Comedy",
    "Art & Theater",
    "Festival",
    "Film",
    "Food & Drink",
    "Nightlife",
    "Sports & Fitness",
    "Family",
    "Educational",
    "Nature & Outdoors",
    "Community"
];

const WEIGHT_LABELS = {
    0: "Skip",
    1: "Maybe",
    2: "Interested",
    3: "Like it",
    4: "Love it",
    5: "Obsessed"
};

const UserProfileModal = ({ isOpen, onClose, user, onUpdate }) => {
    const [formData, setFormData] = useState({
        name: '',
        location_preference: '',
        radius_miles: 15,
        price_max: null,
        family_friendly_only: false,
        use_smart_search: true,
        categories: {},
    });

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const [showCategorySection, setShowCategorySection] = useState(false);
    const [expandedCategory, setExpandedCategory] = useState(null);

    // Populate form with current user data
    useEffect(() => {
        if (user?.backend_user) {
            // Initialize categories from user preferences
            const categoryWeights = {};
            CATEGORIES.forEach(cat => {
                categoryWeights[cat] = 0;
            });

            // If user has preferences, populate them
            if (user.backend_user.preferences) {
                user.backend_user.preferences.forEach(pref => {
                    categoryWeights[pref.category] = pref.weight;
                });
            }

            const newFormData = {
                name: user.name || '',
                location_preference: user.backend_user.location_preference || '',
                radius_miles: user.backend_user.radius_miles || 15,
                price_max: user.backend_user.price_max ?? null,  // ← Use ?? instead of ||
                family_friendly_only: user.backend_user.family_friendly_only || false,
                use_smart_search: user.backend_user.use_smart_search !== false,
                categories: categoryWeights,
            };
            
            // DEBUG: Log what we're loading from backend
            console.log('[DEBUG] UserProfileModal useEffect - loading from backend:', {
                backend_price_max: user.backend_user.price_max,
                derived_price_max: newFormData.price_max,
                type: typeof user.backend_user.price_max
            });
            
            setFormData(newFormData);
        }
    }, [user, isOpen]);  // ← This dependency array is correct

    if (!isOpen) return null;

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked :
                (type === 'number' || type === 'range') ? (value ? parseFloat(value) : null) :
                    value
        }));
        setError(null);
    };

    const handleCategoryWeightChange = (category, weight) => {
        setFormData(prev => ({
            ...prev,
            categories: {
                ...prev.categories,
                [category]: weight
            }
        }));
        setError(null);
    };

    const handleSave = async () => {
        setLoading(true);
        setError(null);
        setSuccess(false);

        try {
            // Update general preferences
            const payload = {
                location_preference: formData.location_preference || null,
                radius_miles: formData.radius_miles,
                price_max: formData.price_max,
                family_friendly_only: formData.family_friendly_only,
                use_smart_search: formData.use_smart_search,
            };

            // DEBUG: Log what we're sending
            console.log('[DEBUG] handleSave - sending payload:', payload);
            console.log('[DEBUG] price_max value:', {
                value: payload.price_max,
                type: typeof payload.price_max,
                isNull: payload.price_max === null,
                isFalsy: !payload.price_max
            });

            await updateUserPreferences(payload);
            
            console.log('[DEBUG] handleSave - updateUserPreferences succeeded');

            // Update ALL category preferences (including zeros to clear them)
            const categoryUpdates = Object.entries(formData.categories).map(([category, weight]) => ({
                category,
                weight: Math.max(0, weight)
            }));

            for (const categoryPref of categoryUpdates) {
                try {
                    await addUserPreference({
                        category: categoryPref.category,
                        weight: categoryPref.weight
                    });
                } catch (err) {
                    console.warn(`Failed to update ${categoryPref.category}:`, err);
                }
            }

            setSuccess(true);

            // Call parent update handler - WAIT for it to complete
            if (onUpdate) {
                console.log('[DEBUG] Calling onUpdate callback');
                await onUpdate(formData);
                console.log('[DEBUG] onUpdate callback completed');
            }

            // Close modal after 1.5 seconds (gives time for refreshUser to finish)
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
            className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[150] p-2 sm:p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#f8f1e0] border border-[#D4AF37]/30 rounded-xl sm:rounded-2xl w-full max-w-lg sm:max-w-2xl p-4 sm:p-6 md:p-8 shadow-2xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-4 sm:mb-6">
                    <h2 className="text-xl sm:text-2xl font-serif text-slate-900">
                        My Profile
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0"
                    >
                        <X size={20} className="text-slate-500" />
                    </button>
                </div>

                {/* Success Message */}
                {success && (
                    <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                        <p className="text-xs sm:text-sm text-green-700 font-medium">✓ Profile saved successfully!</p>
                    </div>
                )}

                {/* Error Message */}
                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex gap-2">
                        <AlertCircle size={16} className="text-red-600 flex-shrink-0 mt-0.5" />
                        <p className="text-xs sm:text-sm text-red-700">{error}</p>
                    </div>
                )}

                {/* Email Display (Read-only) */}
                <div className="mb-4 sm:mb-6 pb-4 sm:pb-6 border-b border-slate-200">
                    <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                        Email Address
                    </label>
                    <p className="text-sm sm:text-base text-slate-800 font-medium break-all">{user?.email}</p>
                    <p className="text-xs text-slate-500 mt-1">Email cannot be changed</p>
                </div>

                {/* Form Fields */}
                <div className="space-y-4 sm:space-y-5">
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
                            className="w-full px-3 sm:px-4 py-2 sm:py-3 rounded-lg sm:rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37]"
                        />
                        <p className="text-xs text-slate-500 mt-1">Where do you prefer to look for events?</p>
                    </div>

                    {/* Search Radius */}
                    <div>
                        <label htmlFor="radius" className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            <MapPinIcon size={14} className="inline mr-1" />
                            Search Radius
                        </label>
                        <div className="flex items-center gap-2 sm:gap-3">
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
                            <span className="text-sm font-semibold text-slate-800 min-w-10 sm:min-w-12 text-right">
                                {formData.radius_miles} mi
                            </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">How far are you willing to travel?</p>
                    </div>

                    {/* Max Price */}
                    <div className="bg-slate-50 p-3 sm:p-4 rounded-lg sm:rounded-xl border border-slate-200">
                        <div className="flex items-center justify-between gap-2 mb-3">
                            <label htmlFor="price" className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                                <DollarSign size={14} className="inline mr-1" />
                                Max Price Per Event
                            </label>
                            <button
                                onClick={() => setFormData(prev => ({
                                    ...prev,
                                    price_max: prev.price_max === null ? 50 : null
                                }))}
                                className={`text-xs font-semibold px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-full transition-all whitespace-nowrap ${formData.price_max === null
                                    ? 'bg-[#D4AF37] text-black shadow-lg shadow-[#D4AF37]/30'
                                    : 'bg-white text-slate-600 border border-slate-200 hover:border-[#D4AF37]/50 hover:text-[#D4AF37]'
                                    }`}
                                title="Click to set no price preference"
                            >
                                No Preference
                            </button>
                        </div>

                        {formData.price_max !== null ? (
                            <input
                                type="number"
                                id="price"
                                name="price_max"
                                placeholder="No limit"
                                min="0"
                                step="10"
                                value={formData.price_max || ''}
                                onChange={handleChange}
                                className="w-full px-3 sm:px-4 py-2 sm:py-3 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50 focus:border-[#D4AF37]"
                            />
                        ) : (
                            <div className="p-3 sm:p-4 bg-gradient-to-r from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/30 rounded-lg text-center">
                                <p className="text-sm font-medium text-[#D4AF37]">
                                    ✨ Price won't be a factor in your recommendations!
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Family Friendly Toggle */}
                    <div className="bg-slate-50 p-3 sm:p-4 rounded-lg sm:rounded-xl border border-slate-200">
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
                    <div className="bg-slate-50 p-3 sm:p-4 rounded-lg sm:rounded-xl border border-slate-200">
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

                    {/* Category Preferences (Collapsible) */}
                    <div className="border border-slate-200 rounded-lg sm:rounded-xl overflow-hidden">
                        <button
                            onClick={() => setShowCategorySection(!showCategorySection)}
                            className="w-full flex items-center justify-between gap-3 p-3 sm:p-4 bg-slate-50 hover:bg-slate-100 transition-colors"
                        >
                            <span className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                                <Heart size={16} className="text-[#D4AF37]" />
                                Adjust Your Interests
                            </span>
                            {showCategorySection ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                        </button>

                        {showCategorySection && (
                            <div className="p-3 sm:p-4 bg-white space-y-2.5 sm:space-y-3 border-t border-slate-200">
                                {CATEGORIES.map(category => {
                                    const weight = formData.categories[category] || 0;
                                    const label = WEIGHT_LABELS[weight];
                                    const isExpanded = expandedCategory === category;

                                    const bgColor = weight === 0
                                        ? 'bg-slate-50'
                                        : 'bg-[#D4AF37]/10';
                                    const textColor = weight === 0
                                        ? 'text-slate-500'
                                        : 'text-[#D4AF37]';

                                    return (
                                        <div key={category} className={`p-2.5 sm:p-3 rounded-lg border border-slate-200 ${bgColor} transition-all`}>
                                            {/* Category Header - Always visible */}
                                            <div className="flex items-center justify-between mb-2 gap-2">
                                                <h4 className="text-xs sm:text-sm font-medium text-slate-800 truncate flex-1">{category}</h4>
                                                {weight > 0 && (
                                                    <span className={`text-[10px] sm:text-xs font-bold px-1.5 sm:px-2 py-0.5 rounded-full flex-shrink-0 ${textColor}`}>
                                                        {label}
                                                    </span>
                                                )}
                                                {/* Expand/Collapse Icon on Mobile */}
                                                <button
                                                    onClick={() => setExpandedCategory(isExpanded ? null : category)}
                                                    className="p-1 sm:hidden text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
                                                >
                                                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                                </button>
                                            </div>

                                            {/* Mobile: Show only when expanded */}
                                            {isExpanded && (
                                                <div className="flex flex-col gap-2.5 sm:hidden">
                                                    {/* Stars */}
                                                    <div className="flex gap-1 justify-center">
                                                        {[1, 2, 3, 4, 5].map(star => (
                                                            <button
                                                                key={star}
                                                                onClick={() => handleCategoryWeightChange(category, star)}
                                                                className={`transition-all duration-200 p-1 ${weight >= star
                                                                    ? 'text-[#D4AF37] scale-110'
                                                                    : 'text-slate-300 hover:text-slate-400'
                                                                    }`}
                                                                title={WEIGHT_LABELS[star]}
                                                            >
                                                                <Star size={16} className={weight >= star ? 'fill-current' : ''} />
                                                            </button>
                                                        ))}
                                                    </div>

                                                    {/* Reset Button */}
                                                    {weight > 0 && (
                                                        <button
                                                            onClick={() => handleCategoryWeightChange(category, 0)}
                                                            className="w-full text-xs text-slate-500 hover:text-slate-700 transition-colors py-1.5 rounded hover:bg-slate-100 font-medium"
                                                        >
                                                            Reset
                                                        </button>
                                                    )}
                                                </div>
                                            )}

                                            {/* Desktop: Always show controls */}
                                            <div className="hidden sm:flex items-center gap-3">
                                                <div className="flex gap-0.5">
                                                    {[1, 2, 3, 4, 5].map(star => (
                                                        <button
                                                            key={star}
                                                            onClick={() => handleCategoryWeightChange(category, star)}
                                                            className={`transition-all duration-200 ${weight >= star
                                                                ? 'text-[#D4AF37] scale-110'
                                                                : 'text-slate-300 hover:text-slate-400'
                                                                }`}
                                                            title={WEIGHT_LABELS[star]}
                                                        >
                                                            <Star size={14} className={weight >= star ? 'fill-current' : ''} />
                                                        </button>
                                                    ))}
                                                </div>

                                                <input
                                                    type="range"
                                                    min="0"
                                                    max="5"
                                                    value={weight}
                                                    onChange={(e) => handleCategoryWeightChange(category, parseInt(e.target.value, 10))}
                                                    className="flex-1 h-1.5 bg-slate-300 rounded-lg appearance-none cursor-pointer accent-[#D4AF37]"
                                                />

                                                {weight > 0 && (
                                                    <button
                                                        onClick={() => handleCategoryWeightChange(category, 0)}
                                                        className="text-xs text-slate-400 hover:text-slate-600 transition-colors px-2 py-1 rounded hover:bg-slate-100 flex-shrink-0"
                                                    >
                                                        Reset
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer Buttons */}
                <div className="flex gap-2 sm:gap-3 mt-6 sm:mt-8 pt-4 sm:pt-6 border-t border-slate-200">
                    <button
                        onClick={onClose}
                        disabled={loading}
                        className="flex-1 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg text-sm font-medium border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={loading}
                        className="flex-1 flex items-center justify-center gap-2 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg text-sm font-medium bg-[#D4AF37] hover:bg-[#C5A028] text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Save size={16} />
                        <span className="hidden sm:inline">{loading ? 'Saving...' : 'Save Changes'}</span>
                        <span className="sm:hidden">{loading ? 'Saving...' : 'Save'}</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

export default UserProfileModal;