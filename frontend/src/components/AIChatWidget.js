/**
 * AIChatWidget Component
 * ----------------------
 * A collapsible chat interface for "Tully" - the AI assistant.
 * 
 * STATES:
 * - Collapsed: Shows a teaser card with "Start Chat" button
 * - Expanded: Full chat interface with message history
 * 
 * PROPS: None (self-contained)
 * 
 * API: Uses chatWithTully() from services/api.js
 */

import React, { useState, useEffect, useRef } from 'react';
import { Send, X } from 'lucide-react';
import { chatWithTully } from '../services/api';

const TULLY_AVATAR = '/assets/Tully.png';
const FALLBACK_AVATAR = 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&w=100&q=80';

const INITIAL_MESSAGE = {
  role: 'assistant',
  text: "Welcome to Tulsa! I am Tully and I can help you curate a Date Night, find Family Activities, or discover Hidden Gems. How can I assist you today?"
};

const AIChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  // Generate or retrieve a persistent guest ID
  const [userId] = useState(() => {
    const stored = localStorage.getItem('locate918_guest_id');
    if (stored) return stored;
    const newId = 'guest_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('locate918_guest_id', newId);
    return newId;
  });

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, isOpen]);

  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessage = { role: 'user', text: inputValue };
    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsTyping(true);

    // Prepare conversation history for the backend
    const conversationHistory = [...messages, userMessage].map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.text }]
    }));

    try {
      const response = await chatWithTully(inputValue, userId, conversationHistory);
      setMessages(prev => [...prev, { role: 'assistant', text: response.message }]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: "I'm having trouble connecting right now. Please try again." 
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // --- COLLAPSED STATE: Teaser Card ---
  if (!isOpen) {
    return (
      <div 
        className="w-full bg-white/60 backdrop-blur-sm rounded-2xl p-8 mb-16 flex flex-col md:flex-row items-center justify-between gap-6 hover:shadow-lg transition-all duration-300 border-l-4 border-[#D4AF37] group cursor-pointer"
        onClick={() => setIsOpen(true)}
      >
        <div className="flex items-center gap-6">
          <div className="w-24 h-24 rounded-full overflow-hidden shadow-lg border-2 border-[#D4AF37] group-hover:scale-110 transition-transform duration-300 bg-slate-900">
            <img 
              src={TULLY_AVATAR} 
              alt="Tully" 
              className="w-full h-full object-cover"
              onError={(e) => { e.target.onerror = null; e.target.src = FALLBACK_AVATAR; }}
            />
          </div>
          <div>
            <h3 className="text-2xl font-serif font-bold text-slate-900 mb-2">Need a plan? Ask Tully.</h3>
            <p className="text-slate-500">Your personal AI assistant for Date Nights, Events, and Itineraries.</p>
          </div>
        </div>
        <button className="px-8 py-3 bg-slate-900 text-white rounded-full font-bold uppercase tracking-widest text-xs hover:bg-[#C5A028] transition-colors shadow-md whitespace-nowrap">
          Start Chat
        </button>
      </div>
    );
  }

  // --- EXPANDED STATE: Chat Interface ---
  return (
    <div className="w-full bg-white/60 backdrop-blur-sm rounded-2xl overflow-hidden mb-16 border border-white/60 shadow-2xl animate-fade-up">
      {/* Header */}
      <div className="bg-slate-900 p-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-14 h-14 rounded-full overflow-hidden border border-[#D4AF37] bg-slate-900">
            <img 
              src={TULLY_AVATAR} 
              alt="Tully" 
              className="w-full h-full object-cover"
              onError={(e) => { e.target.onerror = null; e.target.src = FALLBACK_AVATAR; }}
            />
          </div>
          <div>
            <h3 className="text-white font-serif font-bold text-lg">Tully</h3>
            <span className="text-[#D4AF37] text-xs uppercase tracking-widest font-bold flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span> Online
            </span>
          </div>
        </div>
        <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white transition-colors">
          <X size={24} />
        </button>
      </div>

      {/* Messages Area */}
      <div className="h-[400px] overflow-y-auto p-6 bg-white/40 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed ${
              msg.role === 'user' 
                ? 'bg-slate-900 text-white rounded-br-none' 
                : 'bg-white text-slate-800 rounded-bl-none border border-slate-100'
            }`}>
              {msg.text}
            </div>
          </div>
        ))}
        
        {/* Typing Indicator */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-white p-4 rounded-2xl rounded-bl-none shadow-sm border border-slate-100 flex gap-1">
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></span>
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white/60 border-t border-white/50 backdrop-blur-md">
        <div className="flex gap-2">
          <input 
            type="text" 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your request (e.g., 'Plan a jazz date night downtown')..."
            className="flex-1 bg-white border border-slate-200 rounded-full px-6 py-3 text-sm focus:outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37] transition-all shadow-inner"
          />
          <button 
            onClick={handleSend}
            disabled={!inputValue.trim() || isTyping}
            className="bg-[#C5A028] text-slate-900 p-3 rounded-full hover:bg-[#D4AF37] disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AIChatWidget;
