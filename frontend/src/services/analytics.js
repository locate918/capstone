// =============================================================================
// Click Analytics (venue traffic)
// =============================================================================
//
// Dedicated, fire-and-forget click tracking — SEPARATE from `recordInteraction`
// in api.js. recordInteraction feeds the ML preference model and only runs for
// logged-in users; this records raw click traffic for EVERY visitor (anonymous
// via a localStorage id) so we can measure per-venue traffic.
//
// Affiliate link rewriting is intentionally NOT here yet (no network enrollment).
// When that lands, the only addition is a resolveOutboundUrl() helper; the
// payload already carries `provider` + `click_uid` for reconciliation.

import { supabase } from "../lib/supabaseClient";

const RUST_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:3000";
const ANON_KEY = "locate918_anon_id";

// RFC4122-ish v4; prefers crypto.randomUUID when available.
const uuid = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
};

// Stable per-browser anonymous id. Created on first use, then reused.
export const getAnonId = () => {
    try {
        let id = localStorage.getItem(ANON_KEY);
        if (!id) {
            id = uuid();
            localStorage.setItem(ANON_KEY, id);
        }
        return id;
    } catch {
        // Private mode / storage disabled — degrade gracefully.
        return "anon-unavailable";
    }
};

// Known ticketing / aggregator hosts for the `provider` analytics dimension.
const TICKET_HOSTS = {
    ticketmaster: ["ticketmaster.com", "livenation.com", "ticketweb.com"],
    stubhub: ["stubhub.com"],
    eventbrite: ["eventbrite.com", "eventbrite.co.uk", "evbuc.com"],
};
const AGGREGATOR_HOSTS = [
    "visittulsa.com", "bit918.com", "do918.com", "allevents.in",
    "events.com", "eventful.com", "meetup.com", "facebook.com",
];

// Classify a destination URL into a provider bucket. Anything that isn't a known
// ticketer or aggregator is treated as a direct venue/source link.
export const classifyProvider = (url) => {
    if (!url) return "unknown";
    let host;
    try {
        host = new URL(url).hostname.replace(/^www\./, "");
    } catch {
        return "unknown";
    }
    const matches = (list) => list.some((d) => host === d || host.endsWith("." + d));
    for (const [provider, hosts] of Object.entries(TICKET_HOSTS)) {
        if (matches(hosts)) return provider;
    }
    if (matches(AGGREGATOR_HOSTS)) return "aggregator";
    return "venue_direct";
};

/**
 * Record a click. Fire-and-forget — never blocks the caller or the navigation,
 * never throws. Outbound links open in a new tab so the page stays alive long
 * enough for the request; `keepalive` covers same-tab edge cases.
 *
 * @param {Object}  p
 * @param {string=} p.clickType        outbound_ticket | outbound_venue | event_detail
 * @param {string=} p.eventId
 * @param {number=} p.venueId
 * @param {string=} p.destinationUrl
 * @param {string=} p.provider         overrides classifyProvider(destinationUrl)
 */
export const trackClick = (p) => {
    _send(p).catch(() => {});
};

async function _send({ clickType, eventId, venueId, destinationUrl, provider }) {
    const body = JSON.stringify({
        anon_id: getAnonId(),
        click_uid: uuid(),
        click_type: clickType,
        provider: provider ?? classifyProvider(destinationUrl),
        event_id: eventId ?? null,
        venue_id: venueId ?? null,
        destination_url: destinationUrl ?? null,
        referrer: (typeof document !== "undefined" && document.referrer) || null,
    });

    const headers = { "Content-Type": "application/json" };
    // Attach the session token when present so logged-in clicks get a user_id.
    try {
        const { data } = await supabase.auth.getSession();
        const token = data?.session?.access_token;
        if (token) headers["Authorization"] = `Bearer ${token}`;
    } catch {
        // No session — record as anonymous.
    }

    await fetch(`${RUST_BACKEND_URL}/api/analytics/click`, {
        method: "POST",
        headers,
        body,
        keepalive: true,
    });
}