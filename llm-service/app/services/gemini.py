"""
Locate918 LLM Service - Gemini Integration
==========================================
Owner: Ben (AI Engineer)

Core integration with Google's Gemini API.

Setup:
1. Get API key at https://makersuite.google.com/app/apikey
2. pip install google-genai
3. Add GEMINI_API_KEY to .env

Functions to implement:
- parse_user_intent(message) → SearchParams
- generate_chat_response(message, events, user_profile) → str
- normalize_events(raw_events) → List[NormalizedEvent]

See backend/src/services/llm.rs for the Rust client that calls these.
"""

import os
import json
import time
import httpx
from typing import List, Dict, Any
from datetime import datetime
from google import genai
from google.genai import types
from app.models.schemas import NormalizedEvent
from app.tools.definitions import gemini_tools
from dotenv import load_dotenv

load_dotenv()

_client = None

# ── Venue Name Cache ──────────────────────────────────────────────────────────
# Fetches canonical venue names from Supabase so Gemini can match against them.
# Refreshes every hour to pick up newly added venues.

_venue_cache: List[str] = []
_venue_cache_time: float = 0
VENUE_CACHE_TTL = 3600  # 1 hour


async def get_venue_names() -> List[str]:
    """Fetch canonical venue names from Supabase, cached for 1 hour."""
    global _venue_cache, _venue_cache_time

    if _venue_cache and (time.time() - _venue_cache_time) < VENUE_CACHE_TTL:
        return _venue_cache

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key:
        print("[VenueCache] SUPABASE_URL or SUPABASE_KEY not set, skipping venue list")
        return _venue_cache

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/venues?select=name&order=name",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                timeout=10,
            )
            resp.raise_for_status()
            _venue_cache = [v["name"] for v in resp.json() if v.get("name")]
            _venue_cache_time = time.time()
            print(f"[VenueCache] Loaded {len(_venue_cache)} venue names")
    except Exception as e:
        print(f"[VenueCache] Failed to fetch venues: {e}")

    return _venue_cache


def get_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    _client = genai.Client(api_key=api_key)
    return _client


async def parse_user_intent(message: str) -> Dict[str, Any]:
    """
    Uses Gemini 2.0 Flash to extract search parameters from natural language.
    Returns a JSON object compatible with the backend search API.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    base_prompt = f"""
    Extract search parameters from the user query provided below.
    Current Date: {current_date}
    
    Output a valid JSON object with any of the following keys based on the query: 
    q, category, start_date, end_date, price_max, location, family_friendly, outdoor.
    Use null for missing fields.
    IMPORTANT: If the query contains keywords that are not categories or dates, map them to 'q'. Do not ignore short words like "bad" or "fun".
    Do not infer categories or dates from proper nouns (e.g. band names, venues). Only extract categories if words like 'concert', 'festival', 'music' appear explicitly.
    For dates, convert "this weekend" or "tomorrow" to approximate ISO dates based on current context.
    """

    client = get_client()
    response = await client.aio.models.generate_content(
        model='gemini-2.0-flash',
        contents=[base_prompt, message],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"q": message}


async def generate_chat_response(message: str, history: List[Dict], user_profile: Dict, tool_functions: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Uses Gemini 2.0 Flash for conversation. Handles tool calling.
    Returns a dictionary containing the text response and any tool calls to be executed.
    """

    current_time = datetime.now().strftime("%A, %B %d, %Y")

    # Construct system prompt with user context
    system_instruction = f"""
    You are Tully, the ultimate insider and event concierge for Tulsa, OK (918).
    You know every corner of the city, from the Blue Dome District to the Gathering Place.
    Your goal is to curate the perfect local experience for the user.
    
    Current Context:
    - Today's Date: {current_time}
    - User Profile: {json.dumps(user_profile)}
    
    CRITICAL - YOUR DATA SOURCE:
    You have access to a REAL PostgreSQL database containing events scraped from 60+ Tulsa venues
    and event sources. When you call search_events, it queries this live database via the Rust 
    backend API on port 3000. You are NOT making things up — you are returning real scraped data.
    Never tell users you "can't access databases" or "don't have access to Supabase" — you DO 
    query the actual production database through your search_events tool.

    You also have access to a `search_places` tool containing 500+ real bars, restaurants,
    nightclubs, breweries, and cafes across the Tulsa metro — seeded from Google Places.
    Use this whenever a user asks about drinks, dinner, nightlife, or anywhere to go before/after
    an event. You MUST provide the venue's lat/lng coordinates to use it.
    
    GUIDELINES:
    1. **Search First**: Always use `search_events` to find real data before answering.
    2. **Tulsa-Centric**: Assume all queries are for Tulsa. Do not ask for location.
    3. **Smart Dates**: Interpret "this weekend", "tonight", "next week" relative to Current Date.
       - "tonight" = today's date, events from now onward
       - "tomorrow" = the next calendar day
       - "this weekend" = upcoming Saturday and Sunday
    4. **Imaginative Search**: Users often ask for "vibes" rather than keywords. Translate these:
       - "Date Ideas" -> Search for `q="jazz"`, `q="comedy"`, `q="wine"`, `q="dinner"`, `q="theatre"`, or `category="Arts"`. Do NOT just set `family_friendly=False`.
       - "Family Fun" -> `family_friendly=True` is good, but also try `q="festival"`, `q="market"`, `q="zoo"`.
       - "Nightlife" -> `q="concert"`, `q="dj"`, `q="party"`, `q="cocktail"`.
       - "Chill" -> `q="acoustic"`, `q="poetry"`, `q="yoga"`.
    5. **Places (Bars & Restaurants)**: Use `search_places` whenever a user asks about:
       - Where to get drinks, dinner, or food near an event
       - Bars, restaurants, breweries, or nightlife near a venue
       - A "date night" or "night out" that combines an event + food/drinks
       - Anything to do before or after a show
       To use it you need the venue's coordinates. Use these known coords for common venues:
         - Cain's Ballroom: 36.1563, -95.9929
         - BOK Center: 36.1540, -95.9944
         - Tulsa Theater: 36.1557, -95.9882
         - Circle Cinema: 36.1393, -95.9792
         - Philbrook Museum: 36.1182, -95.9717
         - Gathering Place: 36.1282, -95.9559
         - Hard Rock Tulsa: 36.1887, -95.7449
         - Brady Arts District (general): 36.1547, -95.9850
         - Blue Dome District (general): 36.1450, -95.9950
       For other venues, estimate from the address or use the neighborhood center.
    6. **Links**: ALWAYS link the **Event Title** to the `source_url` if available. 
       If `source_url` is missing, use `venue_website`. Link the **Venue Name** to `venue_website` if available.
       For places, link the place name to `website` or `google_maps` if available.
    7. **Times**: Display times in 12-hour format with AM/PM in Central Time. 
       The database stores times in UTC — convert by subtracting 6 hours (CST) or 5 hours (CDT).
       If a time seems wrong (e.g. midnight for a concert), note it may be estimated.
    7. **Search Fallback Protocol (Strict)**: 
       If a search returns 0 results, do NOT report failure until you have attempted these steps:
       - **Step 1**: Remove specific category filters but keep keywords.
       - **Step 2**: Remove keywords and search the Date Range globally.
       - **Step 3**: Expand the date range by +/- 3 days.
       - **Step 4**: If still 0 results, provide 2 "Evergreen" suggestions (e.g., Gathering Place, Philbrook Museum) based on the user's intent.
    8. **Venue Proximity (The "Dinner & A Show" Rule)**: 
       - When a user asks for restaurants near a venue, identify the venue's neighborhood first (e.g., "Since the Mabee Center is in South Tulsa...").
       - Recommend at least 3 permanent restaurants in that specific area (e.g., near 71st/81st & Lewis for Mabee Center; near the Arts District for Cain's Ballroom). 
       - DO NOT say "There are no restaurant events." Restaurants are businesses, not events.
    9. **Links (Strict)**: You MUST ALWAYS link [Event Title](source_url) and [Venue Name](venue_website) without fail.
    
    RESPONSE FORMATTING (Markdown):
    - **Tone**: Friendly, enthusiastic, and knowledgeable. Like a friend who knows all the cool spots.
    - **Structure**:
      - Start with a warm, brief opening.
      - List events using this Markdown format:
        *   [**Event Title**](source_url) (Use Markdown link syntax. Do NOT show raw URL.)
            *   📍 **Venue**: [Venue Name](venue_website) (Use Markdown link syntax. Do NOT show raw URL.)
            *   ⏰ **Time**: [Day of week], [Time in Central Time]
            *   💰 **Price**: [Price range or "Free"]
            *   📝 [One sentence punchy description]
      - Use emojis relevant to the event type (🎸, 🎨, 🍔, 🎭).
    
    - **No Events Found**: If the search returns nothing, try a broader search before giving up.
      If still nothing, suggest specific *evergreen* local activities relevant to their query 
      (e.g., for music -> Mercury Lounge or Cain's; for art -> Philbrook or First Friday).
    - **Closing**: End with a helpful follow-up question (e.g., "Want me to find bars nearby?", "Need a dinner spot close to the venue?", or "Want to see what's happening tomorrow instead?").
    """

    client = get_client()
    chat = client.aio.chats.create(
        model='gemini-2.0-flash',
        config=types.GenerateContentConfig(
            tools=[gemini_tools],
            system_instruction=system_instruction
        ),
        history=history
    )

    response = await chat.send_message(message)

    # Handle multi-turn tool execution loop
    while response.function_calls:
        tool_outputs = []

        for fc in response.function_calls:
            func_name = fc.name
            func_args = dict(fc.args) if fc.args else {}

            if tool_functions and func_name in tool_functions:
                # Execute the tool
                tool_result = await tool_functions[func_name](func_args)

                # Add the result to the list of outputs
                tool_outputs.append(
                    types.Part.from_function_response(
                        name=func_name,
                        response={"result": tool_result}
                    )
                )
            else:
                # If no handler is provided, return the tool call to the client
                return {
                    "message": "I tried to perform an action that isn't supported. Please ask something else.",
                    "tool_call": {
                        "name": func_name,
                        "args": func_args
                    }
                }

        # Send all tool outputs back to Gemini
        if tool_outputs:
            response = await chat.send_message(tool_outputs)
        else:
            break

    try:
        text_response = response.text
        if not text_response:
            text_response = "I checked the events but couldn't generate a response. Please try asking differently."
    except Exception as e:
        print(f"Gemini Response Error: {e}")
        text_response = "I'm having trouble formulating a response right now."

    return {"message": text_response, "tool_call": None}


async def normalize_events(raw_content: str, source_url: str, content_type: str = "html") -> List[Dict]:
    """
    Uses Gemini 2.0 Flash to extract structured event data from raw HTML or JSON.
    All times are normalized to America/Chicago (Central Time).
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    original_data = {}

    # Fetch canonical venue names for matching
    venue_names = await get_venue_names()
    venue_block = ""
    if venue_names:
        venue_list = "\n".join(f"  - {name}" for name in venue_names)
        venue_block = f"""
    VENUE NAME MATCHING (CRITICAL):
    Below is the list of canonical venue names in our database. When you encounter a venue
    in the raw data, you MUST match it to one of these names if it refers to the same place.
    Use case-insensitive matching. Handle common variations:
    - "The Shrine" → "shrine" (drop "The", match case of canonical)
    - "The Vanguard Tulsa" → "The Vanguard" (drop city suffix)
    - "Hard Rock Casino Tulsa" → "Hard Rock Hotel & Casino Tulsa" (match closest)
    - "Loony Bin Comedy Club" → "Loony Bin" (match shorter canonical form)
    If the venue does NOT match any name below, output it as-is — do not force a bad match.
    
    Known venues:
{venue_list}
    """

    # 1. Parse JSON input to preserve IDs and metadata
    if content_type.lower() == "json":
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, dict):
                original_data = parsed

                # 2. If description is missing, try to fetch the source URL
                if not original_data.get("description"):
                    target_url = original_data.get("source_url") or source_url
                    if target_url and target_url.startswith("http"):
                        print(f"DEBUG: Fetching missing description from {target_url}...")
                        async with httpx.AsyncClient() as client:
                            try:
                                response = await client.get(target_url, follow_redirects=True, timeout=10.0, headers={"User-Agent": "Locate918-Bot/1.0"})
                                if response.status_code == 200:
                                    raw_content = response.text
                                    content_type = "html"  # Switch to HTML extraction mode
                            except Exception as e:
                                print(f"DEBUG: Failed to fetch source URL: {e}")
        except Exception:
            pass

    if content_type.lower() == "json":
        instruction = "Map the following raw JSON data into the standardized event format below. Handle nested structures and different field names intelligently."
    else:
        instruction = "Extract distinct events from the following HTML content. Ignore navigation, footers, and unrelated text."

    base_prompt = f"""
    {instruction}
    Source URL: {source_url}
    Current Date: {current_date}
    {venue_block}
    
    TIMEZONE RULES (CRITICAL):
    - All events are in the Tulsa area, Oklahoma which is America/Chicago timezone (Central Time).
    - Output ALL start_time and end_time values with the Central Time UTC offset.
    - Use -06:00 for CST (November-March) or -05:00 for CDT (March-November).
    - Example: "2025-03-15T19:00:00-05:00" (CDT) or "2025-01-15T19:00:00-06:00" (CST).
    - If the source gives a time in UTC or another timezone, CONVERT it to Central Time.
    - NEVER output times without a timezone offset. NEVER use "Z" suffix.
    
    TIME INFERENCE RULES:
    - If only a date is given with no time, infer a reasonable start time based on event type:
      - Concerts/nightlife/bar events → 20:00 (8 PM)
      - Theater/performing arts → 19:30 (7:30 PM)
      - Festivals/outdoor daytime → 10:00 (10 AM)
      - Brunches/morning events → 10:00 (10 AM)
      - Generic/unknown → 19:00 (7 PM)
    - If "doors at 7" and "show at 8" are given, use the SHOW time as start_time.
    - Set time_estimated = true whenever you infer or guess a time.
    - Set time_estimated = false when the source explicitly provides a time.

    RELATIVE DATE RULES:
    - "This Saturday" means the upcoming Saturday relative to Current Date ({current_date}).
    - "Next week" means 7 days from Current Date.
    - Always resolve relative dates to actual ISO 8601 dates.
    
    CATEGORIZATION RULES:
    You MUST only use categories from this exact canonical list. Do not invent new categories or use variations.

    CANONICAL CATEGORIES (use these exact strings):
      "Music"             — concerts, live bands, DJ sets, open mics, any live musical performance
      "Comedy"            — stand-up comedy, improv, comedy shows, comedians performing live
      "Arts & Theater"    — theater, ballet, dance, opera, symphony, orchestra, art exhibits, visual art, drag, circus
      "Festival"          — multi-day festivals, street festivals, cultural celebrations, fairs with multiple activities (Rocklahoma, Oktoberfest, Mayfest, etc.)
      "Film"              — movie screenings, film festivals, cinema events, documentaries
      "Food & Drink"      — food tastings, cooking classes, brewery events, wine/beer/cocktail events, brunch series, food trucks, farmers markets
      "Nightlife"         — bar events, club nights, DJ nights, 21+ events, late-night parties, happy hours, trivia nights
      "Sports & Fitness"  — athletic events, races, cycling, yoga, fitness classes, spectator sports, recreational leagues
      "Family"            — events explicitly for kids or families, all-ages events, storytime, children's programming
      "Educational"       — lectures, workshops, library programs, museum programs, classes, seminars, book events
      "Nature & Outdoors" — hiking, nature walks, outdoor recreation, park events (only if primarily outdoors)
      "Community"         — nonprofit events, fundraisers, volunteer events, neighborhood gatherings, markets, vendor fairs, tradeshows

    ASSIGNMENT RULES — these are non-negotiable:
    - A comedian performing live → ["Comedy"] NEVER "Music" or "Arts & Theater"
    - A concert or live band → ["Music"]
    - A symphony, ballet, or opera → ["Arts & Theater"] NEVER "Music"
    - A bar hosting live music → ["Music", "Nightlife"]
    - A multi-day outdoor festival → ["Festival"]
    - A food festival → ["Festival", "Food & Drink"]
    - A library storytime → ["Family", "Educational"]
    - A brewery trivia night → ["Nightlife", "Food & Drink"]
    - An outdoor yoga class → ["Sports & Fitness", "Nature & Outdoors"]
    - A farmers market → ["Community", "Food & Drink"]
    - Assign 1-3 categories maximum. Do not pile on categories.
    
    OUTDOOR / FAMILY FRIENDLY RULES:
    - Set outdoor=true if the venue is a Park, Garden, Green, Amphitheater, Zoo, or if the description mentions "open air", "patio", "lawn".
    - Set outdoor=false if the venue is a Hall, Center, Arena, Club, Theater, Museum (unless specified otherwise).
    - Set family_friendly=true if the event mentions "kids", "children", "all ages", "family", or is at a Library, Zoo, or Park.
    - Set family_friendly=false if the event is 18+, 21+, at a Bar/Nightclub (unless "all ages" is stated), or involves burlesque/adult themes.

    Output Format: A JSON list of objects with these exact keys:
    - title (string)
    - venue (string — MUST match a known venue name from the list above if the place is the same, otherwise use the name as-is)
    - venue_address (string, full address if available)
    - source_url (string, the URL for this specific event page — use the input Source URL if no per-event URL exists)
    - source_name (string, human-readable name of the source website, e.g. "Cain's Ballroom", "Eventbrite")
    - start_time (ISO 8601 string WITH Central Time offset, e.g. "2025-03-15T20:00:00-05:00")
    - end_time (ISO 8601 string WITH Central Time offset, or null)
    - time_estimated (boolean, true if the time was inferred/guessed, false if explicitly stated in source)
    - price_min (number or null)
    - price_max (number or null)
    - description (string). Rules:
        1. ALWAYS generate a concise, engaging summary (max 2-3 sentences) based on the available text and event attributes.
        2. Do NOT copy long descriptions verbatim. Clean up HTML, remove promotional fluff, and focus on what the event is.
    - categories (list of strings, e.g. ["music", "jazz"])
    - outdoor (boolean or null)
    - family_friendly (boolean or null)
    - image_url (string or null)
    
    Input Data:
    """

    client = get_client()
    response = await client.aio.models.generate_content(
        model='gemini-2.0-flash',
        contents=[base_prompt, raw_content[:150000]],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    try:
        raw_data = json.loads(response.text)
        valid_events = []

        if isinstance(raw_data, list):
            for item in raw_data:
                try:
                    # Merge original data with LLM data (LLM data takes precedence for normalized fields)
                    if original_data:
                        # Create a merged dictionary: original fields + normalized fields
                        item = {**original_data, **item}

                    # Validate against the Pydantic schema. This drops invalid items
                    valid_events.append(NormalizedEvent(**item).model_dump())
                except Exception as e:
                    print(f"DEBUG: Normalization validation error: {e}")
                    continue

        return valid_events
    except json.JSONDecodeError:
        # If the model output is not valid JSON, return an empty list.
        return []