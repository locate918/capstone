"""
Locate918 LLM Service - Test Version
Run with: uvicorn main:app --reload --port 8001
"""

import os
import json
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import google.generativeai as genai

# =============================================================================
# CONFIG
# =============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    print("⚠️  WARNING: GEMINI_API_KEY not set - using mock responses")
    model = None

app = FastAPI(title="Locate918 LLM Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# MODELS
# =============================================================================

class NormalizeRequest(BaseModel):
    raw_content: str
    source_url: str
    source_name: str

class NormalizeResponse(BaseModel):
    count: int
    events: List[dict]

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    events: List[dict]
    parsed: dict

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    events: List[dict]
    conversation_id: str

# =============================================================================
# HELPERS
# =============================================================================

def parse_date_reference(text: str) -> tuple[Optional[str], Optional[str]]:
    """Convert natural language dates to ISO format"""
    today = datetime.now()
    text_lower = text.lower()

    if "tonight" in text_lower or "today" in text_lower:
        return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif "tomorrow" in text_lower:
        tomorrow = today + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d"), tomorrow.strftime("%Y-%m-%d")
    elif "this weekend" in text_lower or "weekend" in text_lower:
        days_until_friday = (4 - today.weekday()) % 7
        friday = today + timedelta(days=days_until_friday)
        sunday = friday + timedelta(days=2)
        return friday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")
    elif "this week" in text_lower:
        end_of_week = today + timedelta(days=(6 - today.weekday()))
        return today.strftime("%Y-%m-%d"), end_of_week.strftime("%Y-%m-%d")
    elif "next week" in text_lower:
        start = today + timedelta(days=(7 - today.weekday()))
        end = start + timedelta(days=6)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    return None, None

async def call_gemini(prompt: str) -> str:
    """Call Gemini API or return mock response"""
    if model is None:
        return '{"error": "No API key - mock response"}'

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def query_backend(params: dict) -> List[dict]:
    """Query the Rust backend for events"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Filter out None values
            clean_params = {k: v for k, v in params.items() if v is not None}
            response = await client.get(
                f"{BACKEND_URL}/api/events/search",
                params=clean_params,
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Backend error: {response.status_code}")
                return []
    except Exception as e:
        print(f"Backend connection error: {e}")
        return []


def clean_event_for_backend(event: dict) -> dict:
    """
    Clean up event data before sending to Rust backend.

    Fixes:
    - Convert null booleans to false (Rust can't deserialize null -> bool)
    - Ensure start_time has timezone info
    - Remove any fields that shouldn't be sent
    """
    cleaned = event.copy()

    # Fix boolean fields - Rust expects bool, not null
    if cleaned.get("outdoor") is None:
        cleaned["outdoor"] = False
    if cleaned.get("family_friendly") is None:
        cleaned["family_friendly"] = False

    # Ensure booleans are actually booleans
    cleaned["outdoor"] = bool(cleaned.get("outdoor", False))
    cleaned["family_friendly"] = bool(cleaned.get("family_friendly", False))

    # Ensure start_time has timezone info (add Z if missing)
    if cleaned.get("start_time"):
        st = cleaned["start_time"]
        if isinstance(st, str) and not st.endswith("Z") and "+" not in st:
            cleaned["start_time"] = st + "Z"

    # Same for end_time
    if cleaned.get("end_time"):
        et = cleaned["end_time"]
        if isinstance(et, str) and not et.endswith("Z") and "+" not in et:
            cleaned["end_time"] = et + "Z"

    return cleaned


async def post_event_to_backend(event: dict) -> bool:
    """POST an event to the Rust backend"""
    try:
        # Clean the event data before sending
        cleaned_event = clean_event_for_backend(event)

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/events",
                json=cleaned_event,
                timeout=10.0
            )
            if response.status_code == 201:
                return True
            else:
                # Log the actual error for debugging
                print(f"Backend returned {response.status_code}: {response.text[:500]}")
                return False
    except Exception as e:
        print(f"Failed to post event: {e}")
        return False

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "gemini": model is not None}


@app.post("/api/normalize", response_model=NormalizeResponse)
async def normalize(request: NormalizeRequest):
    """
    Normalize raw scraped content into structured events.
    Called by scrapers.
    """
    prompt = f"""
Extract event information from this content. Return ONLY valid JSON array (no markdown, no explanation).
Each event should have these fields (use null for missing data, except booleans which should be true/false):
- title (string, required)
- description (string or null)
- venue (string or null)
- venue_address (string or null)
- location (string or null, e.g., "Downtown Tulsa")
- start_time (ISO 8601 datetime string with Z suffix, required, e.g., "2026-02-15T20:00:00Z")
- end_time (ISO 8601 datetime with Z suffix or null)
- categories (array of strings, e.g., ["concerts", "jazz"])
- price_min (number or null)
- price_max (number or null)
- outdoor (boolean, true or false, NOT null)
- family_friendly (boolean, true or false, NOT null)
- image_url (string or null)

Source URL: {request.source_url}
Source Name: {request.source_name}
Current date: {datetime.now().isoformat()}

Content to parse:
{request.raw_content[:4000]}

Return ONLY the JSON array, nothing else:
"""

    result_text = await call_gemini(prompt)

    # Try to parse JSON from response
    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = result_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        events = json.loads(cleaned)
        if not isinstance(events, list):
            events = [events]
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {result_text[:500]}")
        events = []

    # Add source info and post to backend
    posted_events = []
    for event in events:
        event["source_url"] = request.source_url
        event["source_name"] = request.source_name

        # Ensure required fields
        if not event.get("title") or not event.get("start_time"):
            print(f"Skipping event - missing title or start_time: {event}")
            continue

        # Post to backend
        success = await post_event_to_backend(event)
        if success:
            posted_events.append(event)
            print(f"✅ Posted: {event.get('title')}")
        else:
            print(f"❌ Failed: {event.get('title')}")

    return NormalizeResponse(count=len(posted_events), events=posted_events)


@app.post("/api/search", response_model=SearchResponse)
async def smart_search(request: SearchRequest):
    """
    Smart search - parse natural language query and return events.
    """
    query_lower = request.query.lower()

    # Extract parameters using Gemini
    parse_prompt = f"""
Parse this event search query and return ONLY valid JSON (no markdown):
{{
  "category": "concerts" or "sports" or "family" or "comedy" or "nightlife" or "food" or null,
  "q": "text keywords to search" or null,
  "location": "Downtown" or "Broken Arrow" or other location or null,
  "price_max": number or null,
  "outdoor": true or false or null,
  "family_friendly": true or false or null
}}

Query: "{request.query}"
Return ONLY the JSON:
"""

    parsed = {}
    if model:
        try:
            result = await call_gemini(parse_prompt)
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            parsed = json.loads(cleaned.strip())
        except:
            parsed = {}

    # Handle date references locally (more reliable)
    start_date, end_date = parse_date_reference(request.query)
    if start_date:
        parsed["start_date"] = start_date
    if end_date:
        parsed["end_date"] = end_date

    # Query backend
    events = await query_backend(parsed)

    return SearchResponse(events=events, parsed=parsed)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with Tully - conversational event discovery.
    """
    import uuid

    conversation_id = request.conversation_id or str(uuid.uuid4())

    # First, search for relevant events
    search_result = await smart_search(SearchRequest(query=request.message))
    events = search_result.events[:5]  # Limit to 5 for context

    # Generate conversational response
    events_context = json.dumps(events, indent=2, default=str) if events else "No events found."

    chat_prompt = f"""
You are Tully, a friendly and enthusiastic guide to events in Tulsa, Oklahoma.
You love helping people discover fun things to do!

User message: "{request.message}"

Events found (use ONLY these, do not make up events):
{events_context}

Rules:
- Be warm, friendly, and conversational
- Only mention events from the list above
- If no events found, apologize and suggest they try a different search
- Include relevant details (date, time, venue, price)
- Use emojis sparingly for personality
- Keep response concise (2-3 paragraphs max)

Respond as Tully:
"""

    if model:
        response_text = await call_gemini(chat_prompt)
    else:
        if events:
            response_text = f"Hey there! 🎉 I found {len(events)} events that might interest you!\n\n"
            for e in events[:3]:
                response_text += f"**{e.get('title', 'Event')}** at {e.get('venue', 'TBA')}\n"
        else:
            response_text = "Hmm, I couldn't find any events matching that. Try searching for something else!"

    return ChatResponse(
        message=response_text,
        events=events,
        conversation_id=conversation_id
    )


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)