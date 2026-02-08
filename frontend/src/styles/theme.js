/**
 * Theme Configuration
 * ===================
 * Centralized color palette and style objects for consistent theming.
 * 
 * USAGE:
 * - Import THEME for color values: THEME.primary
 * - Import styles for inline style objects: styles.primaryText
 */

export const THEME = {
  // Brand Colors
  primary: '#D4AF37',        // Metallic Gold
  primaryDark: '#C5A028',    // Darker Gold
  primaryGlow: 'rgba(212, 175, 55, 0.4)',
  
  // Background Colors
  bgLight: '#f8f1e0',        // Cream background
  bgCard: '#162b4a',         // Dark navy for cards
  bgCardHover: '#1f3a60',    // Lighter navy on hover
  
  // Text Colors
  textDark: '#162b4a',       // Dark navy text
  textMuted: '#64748b',      // Muted gray text
};

/**
 * Pre-built inline style objects for common patterns.
 * Use when Tailwind classes aren't sufficient.
 */
export const styles = {
  primaryText: { color: THEME.primary },
  primaryBorder: { borderColor: THEME.primary },
  primaryBg: { backgroundColor: THEME.primary },
  cardBg: { backgroundColor: THEME.bgCard },
};
