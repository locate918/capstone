/**
 * Header Component
 * ================
 * Fixed header with logo, search, filter dropdown, and user actions.
 * 
 * SECTIONS:
 * 1. Logo banner (hidden on mobile)
 * 2. Toolbar with search input, category filter, and action buttons
 * 
 * PROPS:
 * - query: Current search string
 * - setQuery: Function to update search
 */

import React, { useState } from 'react';
import { Search, Filter, ChevronDown, User, Bell, LogOut } from 'lucide-react';
import headerImage from '../assets/header_bg.png';

// =============================================================================
// CONFIGURATION
// =============================================================================

/** Category filter options with search keywords */
const CATEGORIES = [
    { id: "music", label: "Music", keywords: "music concert live band" },
    { id: "nature", label: "Nature & Outdoors", keywords: "nature outdoor park hiking" },
    { id: "educational", label: "Educational", keywords: "educational museum history lecture" },
    { id: "film", label: "Film", keywords: "film movie cinema screening" },
    { id: "art", label: "Arts & Culture", keywords: "art theater dance gallery performance" },
    { id: "food", label: "Food & Drink", keywords: "food dining restaurant culinary" },
    { id: "shopping", label: "Shopping & Markets", keywords: "shopping market fair expo tradeshow" },
    { id: "pets", label: "Pets", keywords: "pet dog cat animal" },
    { id: "fitness", label: "Fitness & Wellness", keywords: "fitness yoga workout gym wellness" },
    { id: "comedy", label: "Comedy", keywords: "comedy comedian standup funny" },
    { id: "family", label: "Family", keywords: "family kids children" },
    { id: "sports", label: "Sports", keywords: "sports game tournament football basketball" },
];

// =============================================================================
// COMPONENT
// =============================================================================

const Header = ({ query, setQuery, user, onOpenAuth, onSignOut }) => {
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    // Find selected category based on current query
    const selectedCategory = CATEGORIES.find(c =>
        c.keywords.split(' ').some(kw => query.toLowerCase() === kw)
    );

    const handleCategorySelect = (category) => {
        // Use the first keyword as the search term
        setQuery(category.keywords.split(' ')[0]);
        setIsDropdownOpen(false);
    };

    const handleClearFilter = () => {
        setQuery("");
        setIsDropdownOpen(false);
    };

    return (
        <div className="flex flex-col w-full shadow-sm">

            {/* ===== LOGO BANNER (Desktop only) ===== */}
            <div className="relative border-b border-[#162b4a]/10 w-full bg-[#f8f1e0] hidden md:flex justify-center items-center h-28 lg:h-36 xl:h-40">
                <div className="h-full w-full max-w-7xl mx-auto px-4 relative flex justify-center items-center">
                    <img
                        src={headerImage}
                        alt="Locate918"
                        className="h-full w-auto max-w-full object-contain py-2"
                    />
                </div>
            </div>

            {/* ===== TOOLBAR ===== */}
            <div className="w-full py-4 border-y border-[#162b4a]/20 bg-[#f8f1e0] relative z-40">
                <div className="max-w-7xl mx-auto px-4 lg:px-6">
                    <div className="flex flex-col lg:flex-row items-center justify-between gap-4 lg:gap-6 w-full">

                        {/* LEFT: Search & Filters */}
                        <div className="flex flex-col md:flex-row gap-3 lg:gap-4 w-full lg:max-w-3xl relative z-50">

                            {/* Category Filter Dropdown */}
                            <div className="relative shrink-0 md:w-52 lg:w-60 group">
                                <button
                                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                                    className="w-full h-full bg-[#162b4a] hover:bg-[#1f3a60] border border-[#162b4a] rounded-lg lg:rounded-xl py-3 lg:py-4 pl-3 lg:pl-4 pr-8 lg:pr-10 text-sm text-white flex items-center gap-2 lg:gap-3 shadow-lg transition-all duration-300"
                                >
                                    <Filter size={18} className={selectedCategory ? "text-[#d4af37]" : "text-slate-400"} />
                                    <span className={selectedCategory ? "text-white font-medium" : "text-slate-300"}>
                                        {selectedCategory ? selectedCategory.label : "All Categories"}
                                    </span>
                                    <ChevronDown
                                        className={`absolute right-3 lg:right-4 top-1/2 -translate-y-1/2 text-slate-400 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`}
                                        size={14}
                                    />
                                </button>

                                {/* Dropdown Menu */}
                                {isDropdownOpen && (
                                    <>
                                        {/* Backdrop to close dropdown */}
                                        <div className="fixed inset-0 z-10" onClick={() => setIsDropdownOpen(false)} />

                                        <div className="absolute top-full left-0 right-0 mt-2 bg-[#162b4a] border border-[#1f3a60] rounded-lg lg:rounded-xl shadow-xl overflow-hidden z-50 max-h-80 overflow-y-auto">
                                            {/* All Categories Option */}
                                            <button
                                                onClick={handleClearFilter}
                                                className="w-full text-left px-3 lg:px-4 py-2.5 lg:py-3 text-sm text-slate-300 hover:bg-[#1f3a60] hover:text-white flex items-center gap-2 lg:gap-3 transition-all duration-200 border-b border-white/5"
                                            >
                                                <Filter size={14} className="text-slate-400" />
                                                <span>All Categories</span>
                                            </button>

                                            {/* Category Options */}
                                            {CATEGORIES.map((category) => (
                                                <button
                                                    key={category.id}
                                                    onClick={() => handleCategorySelect(category)}
                                                    className={`w-full text-left px-3 lg:px-4 py-2.5 lg:py-3 text-sm flex items-center gap-2 lg:gap-3 transition-all duration-200 ${selectedCategory?.id === category.id
                                                            ? 'bg-[#1f3a60] text-white'
                                                            : 'text-slate-300 hover:bg-[#1f3a60] hover:text-white'
                                                        }`}
                                                >
                                                    <span className={`w-2 h-2 rounded-full ${selectedCategory?.id === category.id ? 'bg-[#d4af37]' : 'bg-slate-500'}`} />
                                                    <span>{category.label}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* Search Input */}
                            <div className="relative group w-full z-0">
                                <div className="absolute inset-y-0 left-3 lg:left-4 flex items-center pointer-events-none">
                                    <Search className="text-slate-400 group-focus-within:text-[#d4af37] transition-colors duration-300" size={18} />
                                </div>
                                <input
                                    type="text"
                                    className="w-full bg-[#162b4a] hover:bg-[#1f3a60] focus:bg-[#162b4a] border border-[#162b4a] focus:border-[#d4af37] rounded-lg lg:rounded-xl py-3 lg:py-4 pl-10 lg:pl-12 pr-3 lg:pr-4 text-sm text-white placeholder-slate-400 outline-none transition-all duration-300 shadow-lg focus:shadow-[0_0_20px_-5px_rgba(212,175,55,0.4)]"
                                    placeholder="Search events... (e.g., 'jazz', 'outdoor')"
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                />
                            </div>
                        </div>

                        {/* RIGHT: Actions */}
                        <div className="flex items-center gap-4 lg:gap-6 shrink-0 w-full lg:w-auto justify-between lg:justify-end border-t lg:border-t-0 border-[#162b4a]/10 pt-4 lg:pt-0">
                            {/* Notification Bell */}
                            <button className="relative p-2 text-[#162b4a] hover:bg-[#162b4a]/5 rounded-full transition-colors">
                                <Bell size={18} />
                                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-[#f8f1e0]" />
                            </button>

                            {user ? (
                                <div className="flex items-center gap-2">
                                    <span className="hidden md:inline text-xs text-slate-600 max-w-[180px] truncate">
                                        {user.email}
                                    </span>
                                    <button
                                        onClick={onSignOut}
                                        className="flex items-center gap-2 bg-[#162b4a] hover:bg-[#1f3a60] text-white px-4 lg:px-6 py-2.5 lg:py-3 rounded-lg lg:rounded-xl font-medium text-sm shadow-lg shadow-[#162b4a]/20 transition-all hover:scale-105 active:scale-95"
                                    >
                                        <LogOut size={14} />
                                        <span>Sign Out</span>
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={onOpenAuth}
                                    className="flex items-center gap-2 bg-[#162b4a] hover:bg-[#1f3a60] text-white px-4 lg:px-6 py-2.5 lg:py-3 rounded-lg lg:rounded-xl font-medium text-sm shadow-lg shadow-[#162b4a]/20 transition-all hover:scale-105 active:scale-95"
                                >
                                    <User size={14} />
                                    <span>Sign In</span>
                                </button>
                            )}
                        </div>

                    </div>
                </div>
            </div>
        </div>
    );
};

export default Header;