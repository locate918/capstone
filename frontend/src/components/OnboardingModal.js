/**
 * OnboardingModal.js - New User Preference Questionnaire
 * ======================================================
 * A multi-step modal to guide new users through setting up their initial preferences.
 *
 * PROPS:
 * - isOpen: Boolean to control modal visibility.
 * - onComplete: Function called with the collected preferences when the user finishes.
 * - user: The authenticated user object.
 *
 * CHANGES:
 * - CategoryStep now shows weight sliders (0-5 scale) instead of simple toggles
 * - Users can express preference strength: 0 (don't care) → 5 (love it)
 * - Visual feedback: color intensity increases with preference strength
 */
import React,
{
    useState,
    useEffect
} from 'react';
import {
    ArrowRight,
    Check,
    ChevronLeft,
    Heart,
    MapPin,
    DollarSign,
    Users,
    Sparkles,
    Star
} from 'lucide-react';

// Pre-defined categories for the user to choose from
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

// Weight labels for slider values
const WEIGHT_LABELS = {
    0: "Skip",
    1: "Maybe",
    2: "Interested",
    3: "Like it",
    4: "Love it",
    5: "Obsessed"
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================
const OnboardingModal = ({ isOpen, onComplete, user }) => {
    const [step, setStep] = useState(1);
    const [preferences, setPreferences] = useState({
        categories: {}, // Changed to object: { "Music": 3, "Comedy": 1, ... }
        location: '',
        radius: 15,
        priceMax: 50,
        familyFriendly: false,
    });
    const [isExiting, setIsExiting] = useState(false);

    // Reset state if the modal is closed and reopened
    useEffect(() => {
        if (isOpen) {
            setStep(1);
            setIsExiting(false);
            // Initialize all categories with weight 0
            const initialCategories = {};
            CATEGORIES.forEach(cat => {
                initialCategories[cat] = 0;
            });
            setPreferences({
                categories: initialCategories,
                location: 'Tulsa, OK',
                radius: 15,
                priceMax: 50,
                familyFriendly: false,
            });
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleNext = () => {
        if (step < 5) {
            setStep(s => s + 1);
        } else {
            // Final step, trigger completion
            // Convert to array format for backend: [{ category, weight }, ...]
            const categoriesArray = Object.entries(preferences.categories)
                .filter(([_, weight]) => weight > 0) // Only send categories with weight > 0
                .map(([category, weight]) => ({ category, weight }));

            const finalPrefs = {
                ...preferences,
                categories: categoriesArray
            };

            setIsExiting(true);
            setTimeout(() => onComplete(finalPrefs), 500);
        }
    };

    const handleBack = () => {
        if (step > 1) {
            setStep(s => s - 1);
        }
    };

    const setCategoeryWeight = (category, weight) => {
        setPreferences(p => ({
            ...p,
            categories: {
                ...p.categories,
                [category]: weight
            }
        }));
    };

    const renderStep = () => {
        switch (step) {
            case 1:
                return <WelcomeStep name={user?.user_metadata?.name || 'friend'} />;
            case 2:
                return <CategoryStep weights={preferences.categories} onWeightChange={setCategoeryWeight} />;
            case 3:
                return <LocationStep prefs={preferences} setPrefs={setPreferences} />;
            case 4:
                return <MiscStep prefs={preferences} setPrefs={setPreferences} />;
            case 5:
                return <ReviewStep prefs={preferences} />;
            default:
                return <WelcomeStep name={user?.user_metadata?.name || 'friend'} />;
        }
    };

    const progress = (step / 5) * 100;

    return (
        <div className={`fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[200] p-4 transition-opacity duration-500 ${isExiting ? 'opacity-0' : 'opacity-100'}`}>
            <div className={`bg-[#1a1a2e] border border-[#D4AF37]/30 rounded-2xl max-w-2xl w-full shadow-2xl shadow-[#D4AF37]/10 flex flex-col transition-transform duration-500 ${isExiting ? 'scale-95' : 'scale-100'}`}>
                {/* Header & Progress Bar */}
                <div className="p-6 border-b border-white/10">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-serif text-white">Personalize Your Experience</h2>
                        <span className="text-sm font-mono text-slate-400">Step {step} of 5</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-1.5">
                        <div className="bg-[#D4AF37] h-1.5 rounded-full transition-all duration-500" style={{ width: `${progress}%` }}></div>
                    </div>
                </div>

                {/* Step Content */}
                <div className="p-8 flex-1 min-h-[350px] max-h-[60vh] overflow-y-auto">
                    {renderStep()}
                </div>

                {/* Footer & Navigation */}
                <div className="p-6 border-t border-white/10 flex justify-between items-center">
                    <button
                        onClick={handleBack}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:bg-white/10 transition-all ${step === 1 ? 'opacity-0 cursor-not-allowed' : 'opacity-100'}`}
                        disabled={step === 1}
                    >
                        <ChevronLeft size={16} />
                        Back
                    </button>
                    <button
                        onClick={handleNext}
                        className="group inline-flex items-center gap-2 bg-[#D4AF37] hover:bg-[#C5A028] text-black px-6 py-3 rounded-xl font-semibold tracking-wide shadow-lg shadow-black/20 transition-all duration-300 hover:scale-105"
                    >
                        {step === 5 ? 'Finish Setup' : 'Next'}
                        {step === 5 ? <Check size={18} /> : <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />}
                    </button>
                </div>
            </div>
        </div>
    );
};

// =============================================================================
// STEP SUB-COMPONENTS
// =============================================================================

const WelcomeStep = ({ name }) => (
    <div className="text-center animate-fade-in">
        <Sparkles size={48} className="text-[#D4AF37] mx-auto mb-4" />
        <h3 className="text-3xl font-serif text-white mb-2">Welcome to Locate918, {name}!</h3>
        <p className="text-slate-300 max-w-md mx-auto">Let's take a moment to tailor your event recommendations. This will only take a minute.</p>
    </div>
);

const CategoryStep = ({ weights, onWeightChange }) => {
    // Sort categories by weight (highest first)
    const sortedCategories = CATEGORIES.sort((a, b) => (weights[b] || 0) - (weights[a] || 0));

    return (
        <div className="animate-fade-in">
            <h3 className="text-2xl font-serif text-white mb-1 flex items-center gap-2">
                <Heart size={20} className="text-[#D4AF37]" />
                What are you interested in?
            </h3>
            <p className="text-slate-400 mb-6">Use the sliders to show your preference level. Higher = more interested!</p>

            <div className="space-y-4">
                {sortedCategories.map(category => {
                    const weight = weights[category] || 0;
                    const label = WEIGHT_LABELS[weight];
                    const intensity = weight / 5; // 0-1 scale for color

                    // Dynamic color based on weight
                    const bgColor = weight === 0
                        ? 'bg-slate-700/30'
                        : `bg-[#D4AF37]`;
                    const textColor = weight === 0
                        ? 'text-slate-400'
                        : 'text-black';
                    const opacity = weight === 0
                        ? 'opacity-50'
                        : `opacity-${Math.ceil(intensity * 10) * 10}`; // opacity-10 to opacity-100

                    return (
                        <div
                            key={category}
                            className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/50 hover:border-slate-600 transition-all"
                        >
                            {/* Category Name + Current Weight Label */}
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="text-white font-medium">{category}</h4>
                                {weight > 0 && (
                                    <span className={`text-xs font-bold px-3 py-1 rounded-full ${bgColor} ${textColor}`}>
                                        {label}
                                    </span>
                                )}
                            </div>

                            {/* Weight Slider (0-5 scale) */}
                            <div className="flex items-center gap-4">
                                {/* Stars for visual feedback */}
                                <div className="flex gap-1">
                                    {[1, 2, 3, 4, 5].map(star => (
                                        <button
                                            key={star}
                                            onClick={() => onWeightChange(category, star)}
                                            className={`transition-all duration-200 ${weight >= star
                                                    ? 'text-[#D4AF37] scale-110'
                                                    : 'text-slate-600 hover:text-slate-500'
                                                }`}
                                            title={WEIGHT_LABELS[star]}
                                        >
                                            <Star size={18} className={weight >= star ? 'fill-current' : ''} />
                                        </button>
                                    ))}
                                </div>

                                {/* Slider for fine-tuning */}
                                <input
                                    type="range"
                                    min="0"
                                    max="5"
                                    value={weight}
                                    onChange={(e) => onWeightChange(category, parseInt(e.target.value, 10))}
                                    className="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer range-slider accent-[#D4AF37]"
                                />

                                {/* Reset button */}
                                {weight > 0 && (
                                    <button
                                        onClick={() => onWeightChange(category, 0)}
                                        className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded hover:bg-slate-700/50"
                                    >
                                        Reset
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Help Text */}
            <div className="mt-6 p-4 bg-slate-800/50 border border-slate-700 rounded-lg">
                <p className="text-xs text-slate-400">
                    💡 <strong>Tip:</strong> Events are matched based on these weights. Higher weights = more personalized recommendations!
                </p>
            </div>
        </div>
    );
};

const LocationStep = ({ prefs, setPrefs }) => (
    <div className="animate-fade-in">
        <h3 className="text-2xl font-serif text-white mb-1 flex items-center gap-2"><MapPin size={20} className="text-[#D4AF37]" />Your Location Preferences</h3>
        <p className="text-slate-400 mb-6">Where do you want to find events, and how far are you willing to travel?</p>
        <div className="space-y-6">
            <div>
                <label htmlFor="location" className="block text-sm font-medium text-slate-300 mb-2">Your preferred area</label>
                <input
                    type="text"
                    id="location"
                    value={prefs.location}
                    onChange={e => setPrefs(p => ({ ...p, location: e.target.value }))}
                    placeholder="e.g., Downtown Tulsa, Brookside"
                    className="w-full px-4 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/50"
                />
            </div>
            <div>
                <label htmlFor="radius" className="block text-sm font-medium text-slate-300 mb-2">Travel radius: <span className="font-bold text-[#D4AF37]">{prefs.radius} miles</span></label>
                <input
                    type="range"
                    id="radius"
                    min="1"
                    max="50"
                    value={prefs.radius}
                    onChange={e => setPrefs(p => ({ ...p, radius: parseInt(e.target.value, 10) }))}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer range-slider"
                />
            </div>
        </div>
    </div>
);

const MiscStep = ({ prefs, setPrefs }) => (
    <div className="animate-fade-in">
        <h3 className="text-2xl font-serif text-white mb-6">A few more details...</h3>
        <div className="space-y-6">
            <div>
                <label htmlFor="price" className="block text-sm font-medium text-slate-300 mb-2">Maximum price you're comfortable with: <span className="font-bold text-[#D4AF37]">${prefs.priceMax}</span></label>
                <div className="flex items-center gap-4">
                    <DollarSign size={20} className="text-slate-500" />
                    <input
                        type="range"
                        id="price"
                        min="0"
                        max="200"
                        step="5"
                        value={prefs.priceMax}
                        onChange={e => setPrefs(p => ({ ...p, priceMax: parseInt(e.target.value, 10) }))}
                        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer range-slider"
                    />
                </div>
            </div>
            <div className="flex items-center justify-between bg-slate-800/50 p-4 rounded-lg border border-slate-700">
                <div className="flex items-center gap-3">
                    <Users size={20} className="text-[#D4AF37]" />
                    <div>
                        <h4 className="font-medium text-white">Family-Friendly Events</h4>
                        <p className="text-sm text-slate-400">Only show events suitable for all ages.</p>
                    </div>
                </div>
                <label htmlFor="family-switch" className="flex items-center cursor-pointer">
                    <div className="relative">
                        <input type="checkbox" id="family-switch" className="sr-only" checked={prefs.familyFriendly} onChange={e => setPrefs(p => ({ ...p, familyFriendly: e.target.checked }))} />
                        <div className={`block w-14 h-8 rounded-full transition-colors ${prefs.familyFriendly ? 'bg-[#D4AF37]' : 'bg-slate-700'}`}></div>
                        <div className={`dot absolute left-1 top-1 bg-white w-6 h-6 rounded-full transition-transform ${prefs.familyFriendly ? 'translate-x-6' : ''}`}></div>
                    </div>
                </label>
            </div>
        </div>
    </div>
);

const ReviewStep = ({ prefs }) => {
    // Convert categories object back to readable format
    const selectedCategories = Object.entries(prefs.categories)
        .filter(([_, weight]) => weight > 0)
        .map(([category, weight]) => `${category} (${WEIGHT_LABELS[weight]})`)
        .join(', ');

    return (
        <div className="animate-fade-in">
            <h3 className="text-2xl font-serif text-white mb-2">All Set!</h3>
            <p className="text-slate-400 mb-6">Here's a summary of your preferences. You can always change these later in your profile.</p>
            <div className="bg-slate-800/50 p-6 rounded-lg border border-slate-700 space-y-4 text-sm">
                <div>
                    <span className="text-[#D4AF37] font-semibold">Interests:</span>
                    <p className="text-slate-200 mt-1">
                        {selectedCategories || <span className="text-slate-500 italic">None selected</span>}
                    </p>
                </div>
                <div>
                    <span className="text-[#D4AF37] font-semibold">Location:</span>
                    <p className="text-slate-200 mt-1">{prefs.location || 'Any'} within <span className="text-[#D4AF37]">{prefs.radius} miles</span></p>
                </div>
                <div>
                    <span className="text-[#D4AF37] font-semibold">Budget:</span>
                    <p className="text-slate-200 mt-1">Up to <span className="text-[#D4AF37]">${prefs.priceMax}</span> per ticket</p>
                </div>
                <div>
                    <span className="text-[#D4AF37] font-semibold">Family-Friendly:</span>
                    <p className="text-slate-200 mt-1">{prefs.familyFriendly ? 'Yes' : 'Not required'}</p>
                </div>
            </div>
        </div>
    );
};

export default OnboardingModal;