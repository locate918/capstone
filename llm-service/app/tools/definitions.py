from google.genai import types

search_events_func = types.FunctionDeclaration(
    name="search_events",
    description="Search for events in the Tulsa database based on criteria like category, date, price, venue, etc.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "q": types.Schema(type="STRING", description="Keywords to search for in title or description"),
            "category": types.Schema(type="STRING", description="Category of the event (e.g., concerts, sports, comedy, theater, festivals)"),
            "venue": types.Schema(type="STRING", description="Venue name to filter by (e.g., Cain's Ballroom, BOK Center, The Vanguard)"),
            "start_date": types.Schema(type="STRING", description="ISO 8601 start date - find events ON or after this date"),
            "end_date": types.Schema(type="STRING", description="ISO 8601 end date - find events ON or before this date"),
            "start_after": types.Schema(type="STRING", description="ISO 8601 datetime - find events starting AFTER this time (exclusive)"),
            "start_before": types.Schema(type="STRING", description="ISO 8601 datetime - find events starting BEFORE this time (exclusive)"),
            "price_max": types.Schema(type="NUMBER", description="Maximum price in dollars"),
            "location": types.Schema(type="STRING", description="City or area preference (default: Tulsa)"),
            "family_friendly": types.Schema(type="BOOLEAN", description="Filter for family friendly events"),
            "outdoor": types.Schema(type="BOOLEAN", description="Filter for outdoor events")
        }
    )
)

# This is what gemini.py imports
gemini_tools = types.Tool(function_declarations=[search_events_func])