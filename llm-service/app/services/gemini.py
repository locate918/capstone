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
        model='gemini-2.5-flash-lite',
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
    
    GUIDELINES:
    1. **Search First**: Always use `search_events` to find real data before answering.
    2. **Tulsa-Centric**: Assume all queries are for Tulsa. Do not ask for location.
    3. **Smart Dates**: Interpret "this weekend", "tonight", "next week" relative to Current Date.
    
    RESPONSE FORMATTING (Markdown):
    - **Tone**: Friendly, enthusiastic, and knowledgeable. Like a friend who knows all the cool spots.
    - **Structure**:
      - Start with a warm, brief opening.
      - List events using this Markdown format:
        *   **Event Title** (if URL exists, otherwise just bold Title)
            *   📍 **Venue**: [Venue Name]
            *   ⏰ **Time**: [Day of week], [Time]
            *   💰 **Price**: [Price range or "Free"]
            *   📝 [One sentence punchy description]
      - Use emojis relevant to the event type (🎸, 🎨, 🍔, 🎭).
    
    - **No Events Found**: If the search returns nothing, apologize and suggest specific *evergreen* local activities relevant to their query (e.g., for music -> Mercury Lounge or Cain's; for art -> Philbrook or First Friday).
    - **Closing**: End with a helpful follow-up question (e.g., "Need a dinner recommendation nearby?" or "Want to see what's happening tomorrow instead?").
    """

    client = get_client()
    chat = client.aio.chats.create(
        model='gemini-2.5-flash-lite',
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
                    "message": None,
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
    except Exception:
        text_response = "I'm having trouble formulating a response right now."

    return {"message": text_response, "tool_call": None}


async def normalize_events(raw_content: str, source_url: str, content_type: str = "html") -> List[Dict]:
    """
    Uses Gemini 2.0 Flash to extract structured event data from raw HTML or JSON.
    All times are normalized to America/Chicago (Central Time).
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    original_data = {}

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
    
    TIMEZONE RULES (CRITICAL):
    - All events are in Tulsa, Oklahoma which is America/Chicago timezone (Central Time).
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
    
    Output Format: A JSON list of objects with these exact keys:
    - title (string)
    - venue (string)
    - venue_address (string, full address if available)
    - source_url (string, the URL for this specific event page — use the input Source URL if no per-event URL exists)
    - source_name (string, human-readable name of the source website, e.g. "Cain's Ballroom", "Eventbrite")
    - start_time (ISO 8601 string WITH Central Time offset, e.g. "2025-03-15T20:00:00-05:00")
    - end_time (ISO 8601 string WITH Central Time offset, or null)
    - time_estimated (boolean, true if the time was inferred/guessed, false if explicitly stated in source)
    - price_min (number or null)
    - price_max (number or null)
    - description (string). Rules:
        1. If the source has a description, use it.
        2. If NO description exists, generate a brief summary based on the title/venue.
        3. If generated, prefix with "[AI Generated Due to Missing Description] ".
    - categories (list of strings, e.g. ["music", "jazz"])
    - outdoor (boolean or null)
    - family_friendly (boolean or null)
    - image_url (string or null)
    
    Input Data:
    """

    client = get_client()
    response = await client.aio.models.generate_content(
        model='gemini-2.5-flash-lite',
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