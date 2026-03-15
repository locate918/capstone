from typing import List, Dict, Any, Optional
from datetime import datetime
import math

def calculate_relevance_score(event: Dict[str, Any], user_profile: Dict[str, Any]) -> float:
    """
    Calculates a relevance score for an event based on user preferences and interaction history.
    Higher score = more relevant.
    """
    score = 0.0
    
    # 1. Base score (e.g., recency)
    # Prefer events that haven't happened yet but are coming up soon
    if event.get("start_time"):
        try:
            start_time = datetime.fromisoformat(event["start_time"].replace("Z", "+00:00"))
            now = datetime.now(start_time.tzinfo)
            days_until = (start_time - now).days
            if days_until >= 0:
                # Bonus for upcoming events, tapering off as they get further away
                score += max(0, 10.0 - (days_until / 7.0))
        except (ValueError, TypeError):
            pass

    # 2. Explicit Preferences (User-defined weights)
    # user_profile['preferences'] is a list of {category: str, weight: int}
    event_categories = event.get("categories") or []
    preferences = {p["category"].lower(): p["weight"] for p in user_profile.get("preferences", [])}
    
    for cat in event_categories:
        cat_lower = cat.lower()
        if cat_lower in preferences:
            # Explicit preference weight (+5 to -5)
            score += preferences[cat_lower] * 2.0

    # 3. Implicit Preferences (Interaction History)
    # user_profile['recent_interactions'] is a list of interactions
    # Interaction types: 'clicked', 'saved', 'attended', 'dismissed'
    interactions = user_profile.get("recent_interactions", [])
    
    # Weight per interaction type
    interaction_weights = {
        "attended": 5.0,
        "saved": 3.0,
        "clicked": 1.0,
        "dismissed": -5.0
    }
    
    # Track interaction counts for categories and venues
    category_scores = {}
    venue_scores = {}
    
    for inter in interactions:
        i_type = inter.get("interaction_type")
        i_weight = interaction_weights.get(i_type, 0.0)
        
        # Category affinity
        i_cat = inter.get("event_category")
        if i_cat:
            i_cat = i_cat.lower()
            category_scores[i_cat] = category_scores.get(i_cat, 0.0) + i_weight
            
        # Venue affinity
        i_venue = inter.get("event_venue")
        if i_venue:
            i_venue = i_venue.lower()
            venue_scores[i_venue] = venue_scores.get(i_venue, 0.0) + i_weight

    # Apply affinity scores to current event
    for cat in event_categories:
        cat_lower = cat.lower()
        if cat_lower in category_scores:
            score += category_scores[cat_lower] * 0.5
            
    event_venue = event.get("venue")
    if event_venue:
        venue_lower = event_venue.lower()
        if venue_lower in venue_scores:
            score += venue_scores[venue_lower] * 1.0

    # 4. Global Filters (Family Friendly, etc.)
    user_settings = user_profile.get("user", {})
    if user_settings.get("family_friendly_only") and not event.get("family_friendly"):
        score -= 50.0 # Heavy penalty for non-family-friendly if requested
        
    # 5. Price Preferences
    price_max = user_settings.get("price_max")
    event_price_min = event.get("price_min")
    if price_max is not None and event_price_min is not None:
        if event_price_min > price_max:
            score -= 10.0
        elif event_price_min == 0:
            score += 2.0 # Bonus for free events if they have a price preference?

    return score

def rank_events(events: List[Dict[str, Any]], user_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ranks a list of events based on the user's profile.
    Returns the sorted list of events with an added 'relevance_score' field.
    """
    if not user_profile or not events:
        return events
        
    for event in events:
        event["relevance_score"] = calculate_relevance_score(event, user_profile)
        
    # Sort by relevance_score descending
    ranked = sorted(events, key=lambda x: x.get("relevance_score", 0.0), reverse=True)
    return ranked
