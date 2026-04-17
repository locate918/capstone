import os
import httpx
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.services import gemini, ranking

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")
try:
    CENTRAL = ZoneInfo("America/Chicago")
except ZoneInfoNotFoundError:
    # Some Windows Python installs do not ship IANA timezone data.
    # Keep service booting and rely on UTC formatting until tzdata is installed.
    CENTRAL = timezone.utc

async def get_user_profile(user_id: str, auth_header: str):
    if not auth_header:
        print(f"DEBUG: No auth header for user {user_id}, using fallback profile.")
        # Fallback default profile
        return {
            "user": {
                "id": user_id,
                "location_preference": "Tulsa",
                "family_friendly_only": False,
                "email": "guest@locate918.com"
            },
            "preferences": [],
            "recent_interactions": []
        }
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": auth_header}
            response = await client.get(f"{BACKEND_URL}/api/users/me/profile", headers=headers)
            if response.status_code == 200:
                profile_data = response.json()
                print(f"DEBUG: Loaded profile for user {user_id} ({profile_data.get('user', {}).get('email', 'unknown')})")
                return profile_data
            else:
                print(f"DEBUG: Backend returned {response.status_code} for user {user_id} profile")
        except Exception as e:
            print(f"DEBUG: Failed to load profile for {user_id}: {e}")
            pass

    # Fallback default profile
    print(f"DEBUG: Using fallback profile for user {user_id}")
    return {
        "user": {
            "id": user_id,
            "location_preference": "Tulsa",
            "family_friendly_only": False,
            "email": "guest@locate918.com"
        },
        "preferences": [],
        "recent_interactions": []
    }

async def execute_search_places(args: dict):
    """
    Executes the search_places tool by calling places_nearby() in Supabase.
    Returns bars, restaurants, etc. near a given lat/lng.
    """
    lat          = args.get("lat")
    lng          = args.get("lng")
    place_type   = args.get("place_type")
    radius_miles = args.get("radius_miles", 0.5)

    if not lat or not lng:
        return {"error": "lat and lng are required"}

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key:
        return {"error": "Supabase not configured"}

    # Build the PostgREST RPC call to places_nearby()
    params = {
        "lat":          lat,
        "lng":          lng,
        "radius_miles": min(float(radius_miles), 2.0),  # cap at 2 miles
    }

    headers = {
        "apikey":        supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type":  "application/json",
    }

    print(f"DEBUG: Calling places_nearby({lat}, {lng}, {radius_miles}mi) type={place_type}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{supabase_url}/rest/v1/rpc/places_nearby",
                json=params,
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            places = resp.json()

        # Filter by place_type if specified
        if place_type:
            places = [p for p in places if p.get("place_type") == place_type]

        # Simplify for Gemini context (keep it lean)
        simplified = []
        for p in places[:8]:
            price = p.get("price_level")
            price_str = "$" * price if price else None
            simplified.append({
                "name":          p.get("name"),
                "type":          p.get("place_type"),
                "address":       p.get("address"),
                "neighborhood":  p.get("neighborhood"),
                "distance":      f"{p.get('distance_miles')} miles",
                "price":         price_str,
                "rating":        p.get("rating"),
                "tags":          p.get("tags", []),
                "description":   p.get("description"),
                "website":       p.get("website"),
                "google_maps":   p.get("google_maps_url"),
            })

        return {"places": simplified, "count": len(simplified)}

    except Exception as e:
        print(f"DEBUG: places_nearby error: {e}")
        return {"error": str(e)}


async def execute_search_events(args: dict, user_profile=None):
    """Executes the search_events tool by calling the backend API."""
    # Pad bare dates (YYYY-MM-DD) to full ISO 8601 with Central Time offset.
    # Tulsa is UTC-6 (CST), so "Feb 27" in Central = Feb 27 06:00 UTC to Feb 28 06:00 UTC.
    # Without this shift, evening events stored in UTC get missed.
    if args.get("start_date") and len(str(args["start_date"])) == 10:
        args["start_date"] = f"{args['start_date']}T06:00:00Z"
    if args.get("end_date") and len(str(args["end_date"])) == 10:
        end_dt = datetime.fromisoformat(f"{args['end_date']}T06:00:00+00:00")
        end_dt += timedelta(days=1)
        args["end_date"] = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Remap Gemini tool param names to match Rust backend query params
    if "start_date" in args:
        args["start_after"] = args.pop("start_date")
    if "end_date" in args:
        args["start_before"] = args.pop("end_date")

    # Filter out null values to keep the query clean
    params = {k: v for k, v in args.items() if v is not None}

    print(f"DEBUG: Connecting to Backend at {BACKEND_URL}/api/events/search with params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/events/search", params=params)
            if response.status_code == 200:
                events = response.json()

                # Rank events based on user profile if available
                if user_profile:
                    events = ranking.rank_events(events, user_profile)

                # Simplify event data to save tokens and avoid 429 errors
                simplified_events = []
                for e in events[:5]:  # Limit to 5 events
                    # Convert UTC start_time to Central Time for display
                    # so Gemini doesn't have to do timezone math
                    raw_time = e.get("start_time")
                    display_time = raw_time
                    if raw_time:
                        try:
                            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                            local_dt = dt.astimezone(CENTRAL)
                            display_time = local_dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")
                        except Exception:
                            pass

                    simplified_events.append({
                        "id": e.get("id"),
                        "title": e.get("title"),
                        "start_time": display_time,
                        "venue": e.get("venue"),
                        "venue_website": e.get("venue_website"),
                        "price": f"{e.get('price_min')} - {e.get('price_max')}",
                        "description": (e.get("description") or "")[:500] + ("..." if len(e.get("description") or "") > 500 else ""),
                        "categories": e.get("categories"),
                        "source_url": e.get("source_url")
                    })

                return {"events": simplified_events, "count": len(events)}
            print(f"DEBUG: Backend Error {response.status_code}: {response.text}")
            return {"error": f"Backend returned status {response.status_code}"}
        except Exception as e:
            print(f"DEBUG: Connection Exception: {e}")
            return {"error": str(e)}

def sanitize_history(history: list) -> list:
    """
    Ensures history is in the format expected by Google GenAI SDK.
    Converts 'assistant' -> 'model' and 'content' -> 'parts'.
    """
    if history is None:
        return []
    sanitized = []
    for msg in history:
        role = msg.get("role")
        if role == "assistant":
            role = "model"

        parts = msg.get("parts", [])
        content = msg.get("content")

        if not parts and content:
            parts = [{"text": content}]

        if role and parts:
            sanitized.append({"role": role, "parts": parts})
    return sanitized

@router.post("/chat")
async def chat_with_tully(request: ChatRequest, authorization: str = Header(None, alias="Authorization")):
    """
    Handles conversation with Tully using streaming for progress updates.
    """
    async def event_generator():
        try:
            user_profile = await get_user_profile(request.user_id, authorization)

            # Define tools available to Gemini with user profile context for ranking
            async def search_with_profile(args: dict):
                return await execute_search_events(args, user_profile)

            tool_functions = {
                "search_events":  execute_search_events,
                "search_with_profile": search_with_profile,
                "search_places":  execute_search_places,
            }

            # Limit history to last 15 turns to prevent context exhaustion
            history = sanitize_history(request.conversation_history)
            if len(history) > 15:
                history = history[-15:]

            async for chunk in gemini.generate_chat_response(
                message=request.message,
                history=history,
                user_profile=user_profile,
                tool_functions=tool_functions
            ):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            print(f"Error in chat_with_tully stream: {e}")
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")