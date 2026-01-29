from google.generativeai.types import FunctionDeclaration, Tool

search_events_tool_schema = {
    "name": "search_events",
    "description": "Search for events in the database based on criteria like category, date, price, etc.",
    "parameters": {
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "Keywords to search for in title or description"},
            "category": {"type": "string", "description": "Event category (concerts, sports, arts, food, family)"},
            "start_date": {"type": "string", "description": "ISO date string for start range"},
            "end_date": {"type": "string", "description": "ISO date string for end range"},
            "price_max": {"type": "number", "description": "Maximum price in dollars"},
            "location": {"type": "string", "description": "Area filter (e.g., Downtown, Broken Arrow, South Tulsa)"},
            "family_friendly": {"type": "boolean", "description": "Filter for family friendly events"},
            "outdoor": {"type": "boolean", "description": "Filter for outdoor events"}
        }
    }
}

# Export as a list of Tools for the Gemini client
gemini_tools = [
    Tool(function_declarations=[FunctionDeclaration.from_dict(search_events_tool_schema)])
]