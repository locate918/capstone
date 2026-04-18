/**
 * Footer Component
 * ================
 * Sticky footer with copyright, beta disclaimer, and contact button.
 */

import React from 'react';
import { Mail } from 'lucide-react';

const Footer = () => {
    const currentYear = new Date().getFullYear();

    return (
        <footer className="w-full bg-[#f8f1e0] py-8 mt-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col md:flex-row items-center justify-center gap-6 text-center md:text-left">
                    
                    {/* Copyright and Info */}
                    <div className="flex flex-col gap-2">
                        <p className="text-slate-500 text-xs sm:text-sm">
                            &copy; {currentYear} Locate918. All rights reserved.
                        </p>
                    </div>

                    {/* Contact Button */}
                    <div>
                        <a
                            href="mailto:support@locate918.com"
                            className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#162b4a] text-white rounded-full text-sm font-bold hover:bg-[#1c355c] transition-all shadow-md hover:shadow-lg active:scale-95"
                        >
                            <Mail size={16} />
                            Contact Us
                        </a>
                    </div>

                </div>
            </div>
        </footer>
    );
};

export default Footer;
