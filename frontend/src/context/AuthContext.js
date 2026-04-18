import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import { supabase } from "../lib/supabaseClient";

const RUST_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:3000";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [session, setSession] = useState(null);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;

        const loadSession = async () => {
            const { data, error } = await supabase.auth.getSession();
            if (error) {
                console.error("Failed to load Supabase session:", error.message);
            }
            if (isMounted) {
                setSession(data?.session ?? null);
                setLoading(false);
            }
        };

        loadSession();

        const { data: authListener } = supabase.auth.onAuthStateChange((_, nextSession) => {
            setSession(nextSession);
            setLoading(false);
        });

        return () => {
            isMounted = false;
            authListener?.subscription?.unsubscribe();
        };
    }, []);

    /**
     * Fetch the latest user profile from backend.
     * Called after onboarding completes to refresh the has_completed_onboarding flag.
     * Merges backend user data with Supabase auth user.
     */
    const refreshUser = useCallback(async () => {
        if (!session?.user) {
            console.warn("[DEBUG] No active session to refresh user");
            return;
        }

        try {
            const token = session.access_token;
            const response = await fetch(`${RUST_BACKEND_URL}/api/users/me`, {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const backendUser = await response.json();
            console.log("[DEBUG] User refreshed from backend:", backendUser);

            // Build merged user directly
            const mergedUser = {
                ...session.user,
                name: backendUser.name || session.user.user_metadata?.name || '',
                backend_user: backendUser,
                user_metadata: {
                    has_completed_onboarding: backendUser.has_completed_onboarding,
                    location_preference: backendUser.location_preference,
                    radius_miles: backendUser.radius_miles,
                    price_max: backendUser.price_max,
                    family_friendly_only: backendUser.family_friendly_only,
                },
            };

            setUser(mergedUser);
            console.log("[DEBUG] User state updated with backend data:", mergedUser.user_metadata);
        } catch (error) {
            console.error("Failed to refresh user:", error);
        }
    }, [session]);

    // Only initialize user when session first loads, DON'T run on user changes
    useEffect(() => {
        if (session?.user) {
            // First time session loads - initialize with auth metadata only
            // (backend data will come from refreshUser call in App.js)
            const initialUser = {
                ...session.user,
                name: session.user.user_metadata?.name || '',
                user_metadata: {
                    has_completed_onboarding: session.user.user_metadata?.has_completed_onboarding ?? false,
                    location_preference: session.user.user_metadata?.location_preference,
                    radius_miles: session.user.user_metadata?.radius_miles,
                    price_max: session.user.user_metadata?.price_max,
                    family_friendly_only: session.user.user_metadata?.family_friendly_only ?? false,
                },
            };
            setUser(initialUser);
        } else {
            setUser(null);
        }
    }, [session?.user?.id]); // Only run when session user ID changes, not on every render

    const value = useMemo(
        () => ({
            session,
            user,
            loading,
            refreshUser,
            signInWithPassword: async (email, password) => {
                return supabase.auth.signInWithPassword({ email, password });
            },
            signUpWithPassword: async (email, password, fullName = '') => {
                const result = await supabase.auth.signUp({
                    email,
                    password,
                    options: {
                        emailRedirectTo: window.location.origin,
                        data: {
                            name: fullName, // Store name in user metadata
                        },
                    },
                });
                return result;
            },
            signInWithGoogle: async () => {
                return supabase.auth.signInWithOAuth({
                    provider: "google",
                    options: { redirectTo: window.location.origin },
                });
            },
            signOut: async () => {
                return supabase.auth.signOut();
            },
        }),
        [session, user, loading, refreshUser]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used inside <AuthProvider>");
    }
    return context;
}