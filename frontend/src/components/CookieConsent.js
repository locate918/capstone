/**
 * CookieConsent Component
 * =======================
 * Dismissible bottom banner disclosing our use of local storage + anonymous,
 * aggregate usage analytics (see services/analytics.js). Shown once per browser
 * until acknowledged; the choice is persisted in localStorage.
 *
 * This is a disclosure/notice banner. Our analytics are first-party and
 * anonymous (no PII, no cross-site tracking), so tracking is not gated on
 * acknowledgement — but the user is always informed and can read why.
 */

import React, { useEffect, useState } from 'react';
import { Cookie, X } from 'lucide-react';

const CONSENT_KEY = 'locate918_cookie_consent';

const CookieConsent = () => {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        try {
            if (!localStorage.getItem(CONSENT_KEY)) {
                setVisible(true);
            }
        } catch {
            // Storage unavailable (private mode) — don't nag; just stay hidden.
        }
    }, []);

    const acknowledge = () => {
        try {
            localStorage.setItem(CONSENT_KEY, 'acknowledged');
        } catch {
            // ignore — banner still dismisses for this session
        }
        setVisible(false);
    };

    if (!visible) return null;

    return (
        <div className="fixed bottom-0 inset-x-0 z-[150] p-3 sm:p-4 flex justify-center pointer-events-none">
            <div className="pointer-events-auto bg-[#1a1a2e] border border-[#D4AF37]/30 rounded-2xl shadow-2xl shadow-black/40 max-w-3xl w-full p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
                <div className="flex items-start gap-3 flex-1">
                    <div className="bg-[#D4AF37]/15 p-2 rounded-full shrink-0">
                        <Cookie size={20} className="text-[#D4AF37]" />
                    </div>
                    <p className="text-slate-300 text-xs sm:text-sm leading-relaxed">
                        We use local storage to keep you signed in and to measure{' '}
                        <span className="text-white">anonymous, aggregate traffic</span> so we can
                        improve Locate918. We don&apos;t sell your data or track you across other sites.
                    </p>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                    <button
                        onClick={acknowledge}
                        className="bg-[#D4AF37] hover:bg-[#C5A028] text-black font-bold text-sm px-5 py-2.5 rounded-xl transition-all duration-300 hover:scale-[1.03] active:scale-[0.97] shadow-lg"
                    >
                        Got it
                    </button>
                    <button
                        onClick={acknowledge}
                        aria-label="Dismiss"
                        className="text-slate-500 hover:text-slate-300 p-2 rounded-lg transition-colors"
                    >
                        <X size={18} />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default CookieConsent;
