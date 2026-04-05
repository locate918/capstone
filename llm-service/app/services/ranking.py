from typing import List, Dict, Any, Optional
from datetime import datetime
import math

def get_interaction_weight(interaction_type: str) -> float:
    """Returns the weight for a given interaction type."""
    weights = {
        "clicked": 0.1,
        "saved": 0.2,
        "dismissed": -0.1,
        "clicked on og post": 0.3,
    }
    return weights.get(interaction_type, 0)

def score_categories_from_interaction(
    user_id: str,
    event_categories: List[str],
    interaction_type: str,
    user_preferences: Dict[str, int],
) -> Dict[str, int]:
    """
    Calculates the new scores for categories affected by an interaction.
    Returns a dictionary containing only the updated categories and their new scores.
    Scores are capped to a reasonable range to prevent runaway values.
    """
    weight = get_interaction_weight(interaction_type)
    updated_categories = {}
    for category in event_categories:
        current_score = user_preferences.get(category, 0)
        new_score = current_score + weight
        # Cap the score to maintain a reasonable preference scale (e.g., -10 to +10)
        capped_score = max(-10.0, min(10.0, new_score))
        updated_categories[category] = capped_score
    return updated_categories

def score_all_categories(
    user_interactions: List[Dict[str, Any]],
    user_preferences: Dict[str, float],
) -> dict[str, float]:
    """
    Updates user category preferences based on all of their interactions.
    """
    for interaction in user_interactions:
        event_categories = interaction.get("categories", [])
        interaction_type = interaction.get("interaction_type")
        if event_categories and interaction_type:
            weight = get_interaction_weight(interaction_type)
            for category in event_categories:
                user_preferences[category] = user_preferences.get(category, 0) + weight
    return user_preferences


def calculate_relevance_score(event: Dict[str, Any], user_profile: Dict[str, Any]) -> float:
    """
    Calculates a relevance score for an event based on user preferences and interaction history.
    Higher score = more relevant.
    """
    # Start with a base score
    score = 0.0

    # Get user preferences from their profile, or initialize if not present
    user_preferences = user_profile.get("preferences", {})

    # If the user has interactions, calculate their preferences from them
    if "interactions" in user_profile:
        user_preferences = score_all_categories(user_profile["interactions"], user_preferences)

    # Add points for matching categories
    if "categories" in event and user_preferences:
        for category in event["categories"]:
            score += user_preferences.get(category, 0)

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
