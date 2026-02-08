/**
 * Header Component
 * ================
 * Fixed header with logo, search, filter dropdown, and user actions.
 * 
 * SECTIONS:
 * 1. Logo banner (hidden on mobile)
 * 2. Toolbar with search input, vibe filter, and action buttons
 * 
 * PROPS:
 * - query: Current search string
 * - setQuery: Function to update search
 */

import React, { useState } from 'react';
import { Search, Filter, ChevronDown, User, Bell } from 'lucide-react';
import headerImage from '../assets/header_bg.png'; 

// =============================================================================
// CONFIGURATION
// =============================================================================

/** Vibe filter categories that map to backend search categories */
const VIBES = [
  { id: "exclusive", label: "Exclusive", category: "business" },
  { id: "nightlife", label: "Nightlife", category: "concerts" },
  { id: "business", label: "Business", category: "business" },
  { id: "chill", label: "Chill", category: "family" }
];

// =============================================================================
// COMPONENT
// =============================================================================

const Header = ({ query, setQuery }) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Find selected vibe based on current query
  const selectedVibe = VIBES.find(v => v.category === query);

  const handleVibeSelect = (category) => {
    setQuery(category);
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
                
              {/* Vibe Filter Dropdown */}
              <div className="relative shrink-0 md:w-48 lg:w-56 group">
                <button 
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                  className="w-full h-full bg-[#162b4a] hover:bg-[#1f3a60] border border-[#162b4a] rounded-lg lg:rounded-xl py-3 lg:py-4 pl-3 lg:pl-4 pr-8 lg:pr-10 text-sm text-white flex items-center gap-2 lg:gap-3 shadow-lg transition-all duration-300"
                >
                  <Filter size={18} className={selectedVibe ? "text-[#d4af37]" : "text-slate-400"} />
                  <span className={selectedVibe ? "text-white font-medium" : "text-slate-300"}>
                    {selectedVibe ? selectedVibe.label : "All Vibes"}
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
                    
                    <div className="absolute top-full left-0 right-0 mt-2 bg-[#162b4a] border border-[#1f3a60] rounded-lg lg:rounded-xl shadow-xl overflow-hidden z-50">
                      {/* All Vibes Option */}
                      <button
                        onClick={handleClearFilter}
                        className="w-full text-left px-3 lg:px-4 py-2.5 lg:py-3 text-sm text-slate-300 hover:bg-[#1f3a60] hover:text-white flex items-center gap-2 lg:gap-3 transition-all duration-200 border-b border-white/5"
                      >
                        <Filter size={14} className="text-slate-400" />
                        <span>All Vibes</span>
                      </button>

                      {/* Vibe Options */}
                      {VIBES.map((vibe) => (
                        <button
                          key={vibe.id}
                          onClick={() => handleVibeSelect(vibe.category)}
                          className={`w-full text-left px-3 lg:px-4 py-2.5 lg:py-3 text-sm flex items-center gap-2 lg:gap-3 transition-all duration-200 ${
                            query === vibe.category 
                              ? 'bg-[#1f3a60] text-white' 
                              : 'text-slate-300 hover:bg-[#1f3a60] hover:text-white'
                          }`}
                        >
                          <span className={`w-2 h-2 rounded-full ${query === vibe.category ? 'bg-[#d4af37]' : 'bg-slate-500'}`} />
                          <span>{vibe.label}</span>
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
                  placeholder="Search events... (e.g., 'jazz')"
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

              {/* Sign In Button */}
              <button className="flex items-center gap-2 bg-[#162b4a] hover:bg-[#1f3a60] text-white px-4 lg:px-6 py-2.5 lg:py-3 rounded-lg lg:rounded-xl font-medium text-sm shadow-lg shadow-[#162b4a]/20 transition-all hover:scale-105 active:scale-95">
                <User size={14} />
                <span>Sign In</span>
              </button>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};

export default Header;