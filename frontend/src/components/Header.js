/**
 * Header Component
 * ================
 * Fixed header with logo, search, filter dropdown, and user actions.
 * Optimized for both mobile and desktop experiences.
 */

import React, { useState } from 'react';
import { Search, Filter, ChevronDown, User, Bell, LogOut, Menu, X } from 'lucide-react';
import headerImage from '../assets/header_bg.png';

// =============================================================================
// CONFIGURATION
// =============================================================================

const CATEGORIES = [
    { id: "music",      label: "Music",             keywords: "music concert live band" },
    { id: "comedy",     label: "Comedy",             keywords: "comedy comedian standup funny" },
    { id: "art",        label: "Arts & Theater",     keywords: "art theater dance ballet opera gallery performance" },
    { id: "festival",   label: "Festival",           keywords: "festival fair outdoor celebration" },
    { id: "film",       label: "Film",               keywords: "film movie cinema screening" },
    { id: "food",       label: "Food & Drink",       keywords: "food dining restaurant beer wine cocktail brunch" },
    { id: "nightlife",  label: "Nightlife",          keywords: "nightlife bar club dj party" },
    { id: "sports",     label: "Sports & Fitness",   keywords: "sports fitness yoga workout cycling marathon game" },
    { id: "family",     label: "Family",             keywords: "family kids children all ages storytime" },
    { id: "educational",label: "Educational",        keywords: "educational museum history lecture workshop library" },
    { id: "nature",     label: "Nature & Outdoors",  keywords: "nature outdoor park hiking trail garden" },
    { id: "community",  label: "Community",          keywords: "community market vendor nonprofit fundraiser" },
];

// =============================================================================
// COMPONENT
// =============================================================================

const Header = ({ query, setQuery, user, onOpenAuth, onSignOut }) => {
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    const selectedCategory = CATEGORIES.find(c =>
        c.label.toLowerCase() === query.toLowerCase()
    );

    const handleCategorySelect = (category) => {
        setQuery(category.label);
        setIsDropdownOpen(false);
    };

    const handleClearFilter = () => {
        setQuery("");
        setIsDropdownOpen(false);
    };

    return (
        <div className="flex flex-col w-full shadow-sm">

            {/* ===== LOGO BANNER (Desktop only) ===== */}
            <div className="relative border-b border-[#162b4a]/10 w-full bg-[#f8f1e0] hidden md:flex justify-center items-center h-32 lg:h-40 xl:h-44">
                <div className="h-full w-full max-w-7xl mx-auto px-4 relative flex justify-center items-center">
                    <img
                        src={headerImage}
                        alt="Locate918"
                        className="h-full w-auto max-w-full object-contain py-2"
                    />
                </div>
            </div>

            {/* ===== MOBILE HEADER BAR ===== */}
            <div className="md:hidden flex items-center justify-between px-4 py-3 bg-[#f8f1e0] border-b border-[#162b4a]/10">
                <img
                    src={headerImage}
                    alt="Locate918"
                    className="h-10 w-auto object-contain"
                />
                <div className="flex items-center gap-2">
                    {/* Notification Bell - Mobile */}
                    <button className="relative p-2.5 text-[#162b4a] hover:bg-[#162b4a]/5 rounded-full transition-colors">
                        <Bell size={20} />
                        <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-[#f8f1e0]" />
                    </button>
                    {/* Mobile Menu Toggle */}
                    <button
                        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                        className="p-2.5 text-[#162b4a] hover:bg-[#162b4a]/5 rounded-full transition-colors"
                    >
                        {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
                    </button>
                </div>
            </div>

            {/* ===== MOBILE MENU OVERLAY ===== */}
            {isMobileMenuOpen && (
                <div className="md:hidden fixed inset-0 z-50 bg-black/50" onClick={() => setIsMobileMenuOpen(false)}>
                    <div
                        className="absolute right-0 top-0 h-full w-72 bg-[#f8f1e0] shadow-2xl p-6 overflow-y-auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex justify-end mb-6">
                            <button
                                onClick={() => setIsMobileMenuOpen(false)}
                                className="p-2 text-slate-500 hover:text-slate-700"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        {user ? (
                            <div className="space-y-4 mb-8">
                                <p className="text-sm text-slate-600 truncate">{user.email}</p>
                                <button
                                    onClick={() => {
                                        onSignOut();
                                        setIsMobileMenuOpen(false);
                                    }}
                                    className="w-full flex items-center justify-center gap-2 bg-[#162b4a] text-white px-4 py-3 rounded-xl font-medium text-sm"
                                >
                                    <LogOut size={16} />
                                    Sign Out
                                </button>
                            </div>
                        ) : (
                            <button
                                onClick={() => {
                                    onOpenAuth();
                                    setIsMobileMenuOpen(false);
                                }}
                                className="w-full flex items-center justify-center gap-2 bg-[#162b4a] text-white px-4 py-3 rounded-xl font-medium text-sm mb-8"
                            >
                                <User size={16} />
                                Sign In
                            </button>
                        )}

                        {/* Categories in Mobile Menu */}
                        <div className="space-y-1">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Categories</p>
                            <button
                                onClick={() => {
                                    handleClearFilter();
                                    setIsMobileMenuOpen(false);
                                }}
                                className={`w-full text-left px-3 py-3 rounded-lg text-sm transition-colors ${!selectedCategory ? 'bg-[#162b4a] text-white' : 'text-slate-700 hover:bg-slate-100'}`}
                            >
                                All Categories
                            </button>
                            {CATEGORIES.map((category) => (
                                <button
                                    key={category.id}
                                    onClick={() => {
                                        handleCategorySelect(category);
                                        setIsMobileMenuOpen(false);
                                    }}
                                    className={`w-full text-left px-3 py-3 rounded-lg text-sm transition-colors ${selectedCategory?.id === category.id ? 'bg-[#162b4a] text-white' : 'text-slate-700 hover:bg-slate-100'}`}
                                >
                                    {category.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* ===== TOOLBAR ===== */}
            <div className="w-full py-3 md:py-4 border-b md:border-y border-[#162b4a]/20 bg-[#f8f1e0] relative z-40">
                <div className="max-w-7xl mx-auto px-4 lg:px-6">
                    <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 md:gap-6 w-full">

                        {/* Search & Filters */}
                        <div className="flex gap-2 md:gap-4 w-full lg:max-w-3xl relative z-50">

                            {/* Category Filter Dropdown - Hidden on mobile (use menu instead) */}
                            <div className="relative shrink-0 hidden md:block md:w-52 lg:w-60 group">
                                <button
                                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                                    className="w-full h-full bg-[#162b4a] hover:bg-[#1f3a60] border border-[#162b4a] rounded-xl py-3 lg:py-4 pl-4 pr-10 text-sm text-white flex items-center gap-3 shadow-lg transition-all duration-300"
                                >
                                    <Filter size={18} className={selectedCategory ? "text-[#d4af37]" : "text-slate-400"} />
                                    <span className={selectedCategory ? "text-white font-medium" : "text-slate-300"}>
                                        {selectedCategory ? selectedCategory.label : "All Categories"}
                                    </span>
                                    <ChevronDown
                                        className={`absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`}
                                        size={14}
                                    />
                                </button>

                                {/* Dropdown Menu */}
                                {isDropdownOpen && (
                                    <>
                                        <div className="fixed inset-0 z-10" onClick={() => setIsDropdownOpen(false)} />
                                        <div className="absolute top-full left-0 right-0 mt-2 bg-[#162b4a] border border-[#1f3a60] rounded-xl shadow-xl overflow-hidden z-50 max-h-80 overflow-y-auto">
                                            <button
                                                onClick={handleClearFilter}
                                                className="w-full text-left px-4 py-3 text-sm text-slate-300 hover:bg-[#1f3a60] hover:text-white flex items-center gap-3 transition-all duration-200 border-b border-white/5"
                                            >
                                                <Filter size={14} className="text-slate-400" />
                                                <span>All Categories</span>
                                            </button>
                                            {CATEGORIES.map((category) => (
                                                <button
                                                    key={category.id}
                                                    onClick={() => handleCategorySelect(category)}
                                                    className={`w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-all duration-200 ${selectedCategory?.id === category.id
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

                            {/* Search Input - Full width on mobile */}
                            <div className="relative group w-full">
                                <div className="absolute inset-y-0 left-3 md:left-4 flex items-center pointer-events-none">
                                    <Search className="text-slate-400 group-focus-within:text-[#d4af37] transition-colors duration-300" size={18} />
                                </div>
                                <input
                                    type="text"
                                    className="w-full bg-[#162b4a] hover:bg-[#1f3a60] focus:bg-[#162b4a] border border-[#162b4a] focus:border-[#d4af37] rounded-xl py-3 md:py-4 pl-10 md:pl-12 pr-4 text-sm text-white placeholder-slate-400 outline-none transition-all duration-300 shadow-lg focus:shadow-[0_0_20px_-5px_rgba(212,175,55,0.4)]"
                                    placeholder="Search events..."
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                />
                            </div>
                        </div>

                        {/* Desktop Actions - Hidden on mobile */}
                        <div className="hidden md:flex items-center gap-6 shrink-0">
                            <button className="relative p-2 text-[#162b4a] hover:bg-[#162b4a]/5 rounded-full transition-colors">
                                <Bell size={18} />
                                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-[#f8f1e0]" />
                            </button>

                            {user ? (
                                <div className="flex items-center gap-2">
                                    <span className="hidden lg:inline text-xs text-slate-600 max-w-[180px] truncate">
                                        {user.email}
                                    </span>
                                    <button
                                        onClick={onSignOut}
                                        className="flex items-center gap-2 bg-[#162b4a] hover:bg-[#1f3a60] text-white px-6 py-3 rounded-xl font-medium text-sm shadow-lg shadow-[#162b4a]/20 transition-all hover:scale-105 active:scale-95"
                                    >
                                        <LogOut size={14} />
                                        <span>Sign Out</span>
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={onOpenAuth}
                                    className="flex items-center gap-2 bg-[#162b4a] hover:bg-[#1f3a60] text-white px-6 py-3 rounded-xl font-medium text-sm shadow-lg shadow-[#162b4a]/20 transition-all hover:scale-105 active:scale-95"
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