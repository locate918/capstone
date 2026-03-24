import enum

from google.genai import types

search_places_func = types.FunctionDeclaration(
    name="search_places",
    description=(
        "Find bars, restaurants, nightclubs, breweries, and other places to eat or drink "
        "near a Tulsa venue or address. Use this when the user asks about where to grab "
        "drinks, dinner, or a nightcap near an event."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "lat": types.Schema(
                type="NUMBER",
                description="Latitude of the event venue or location"
            ),
            "lng": types.Schema(
                type="NUMBER",
                description="Longitude of the event venue or location"
            ),
            "place_type": types.Schema(
                type="STRING",
                description=(
                    "Type of place to find. One of: bar, tavern, nightclub, cocktail_bar, "
                    "brewery, wine_bar, sports_bar, karaoke_bar, restaurant, cafe. "
                    "Omit to return all types."
                )
            ),
            "radius_miles": types.Schema(
                type="NUMBER",
                description="Search radius in miles. Default 0.5. Max 2.0."
            ),
        },
        required=["lat", "lng"]
    )
)

search_events_func = types.FunctionDeclaration(
    name="search_events",
    description="Search for events in the Tulsa database based on criteria like category, date, price, venue, etc.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "q": types.Schema(type=types.Type.STRING, description="Keywords to search for in title or description"),
            "category": types.Schema(type=types.Type.STRING, description="Category of the event (e.g., concerts, sports, comedy, theater, festivals)"),
            "venue": types.Schema(type=types.Type.STRING, description="Venue name to filter by (e.g., Cain's Ballroom, BOK Center, The Vanguard)"),
            "start_date": types.Schema(type=types.Type.STRING, description="ISO 8601 start date - find events ON or after this date"),
            "end_date": types.Schema(type=types.Type.STRING, description="ISO 8601 end date - find events ON or before this date"),
            "start_after": types.Schema(type=types.Type.STRING, description="ISO 8601 datetime - find events starting AFTER this time (exclusive)"),
            "start_before": types.Schema(type=types.Type.STRING, description="ISO 8601 datetime - find events starting BEFORE this time (exclusive)"),
            "price_max": types.Schema(type=types.Type.NUMBER, description="Maximum price in dollars"),
            "location": types.Schema(type=types.Type.STRING, description="City or area preference (default: Tulsa)"),
            "family_friendly": types.Schema(type=types.Type.BOOLEAN, description="Filter for family friendly events"),
            "outdoor": types.Schema(type=types.Type.BOOLEAN, description="Filter for outdoor events")
        }
    )
)

# This is what gemini.py imports
gemini_tools = types.Tool(function_declarations=[search_events_func])

class Categories(enum.Enum):
    MUSIC = "Music"
