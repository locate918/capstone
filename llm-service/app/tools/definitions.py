from google.genai import types

search_events_func = types.FunctionDeclaration(
    name="search_events",
    description="Search for events in the database based on criteria like category, date, price, etc.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "q": types.Schema(type="STRING", description="Keywords to search for in title or description"),
            "category": types.Schema(type="STRING", description="Category of the event (e.g., concerts, sports)"),
            "start_date": types.Schema(type="STRING", description="ISO 8601 start date"),
            "end_date": types.Schema(type="STRING", description="ISO 8601 end date"),
            "price_max": types.Schema(type="NUMBER", description="Maximum price"),
            "location": types.Schema(type="STRING", description="City or area preference"),
            "family_friendly": types.Schema(type="BOOLEAN", description="Filter for family friendly events"),
            "outdoor": types.Schema(type="BOOLEAN", description="Filter for outdoor events")
        }
    )
)

# This is what gemini.py imports
gemini_tools = types.Tool(function_declarations=[search_events_func])