import os
import httpx
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services import gemini

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")
CENTRAL = ZoneInfo("America/Chicago")

async def get_user_profile(user_id: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/users/{user_id}/profile")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
    # Fallback default profile
    return {
        "id": user_id,
        "location_preference": "Tulsa",
        "family_friendly_only": False
    }

async def execute_search_events(args: dict):
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

                # Simplify event data to save tokens and avoid 429 errors
                simplified_events = []
                for e in events[:8]:  # Limit to 8 events
                    # Convert UTC start_time to Central Time for display
                    # so Gemini doesn't have to do timezone math
                    raw_time = e.get("start_time")
                    display_time = raw_time
                    if raw_time:
                        try:
                            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                            local_dt = dt.astimezone(CENTRAL)
                            display_time = local_dt.strftime("%A, %B %d, %Y at %I:%M %p CST")
                        except Exception:
                            pass

                    simplified_events.append({
                        "title": e.get("title"),
                        "start_time": display_time,
                        "venue": e.get("venue"),
                        "venue_website": e.get("venue_website"),
                        "price": f"{e.get('price_min')} - {e.get('price_max')}",
                        "description": (e.get("description") or "")[:200] + "...",
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

@router.post("/chat", response_model=ChatResponse)
async def chat_with_tully(request: ChatRequest):
    """
    Handles conversation with Tully.
    """
    try:
        user_profile = await get_user_profile(request.user_id)

        # Define tools available to Gemini
        tool_functions = {
            "search_events": execute_search_events
        }

        # Limit history to last 15 turns to prevent context exhaustion
        history = sanitize_history(request.conversation_history)
        if len(history) > 15:
            history = history[-15:]

        response = await gemini.generate_chat_response(
            message=request.message,
            history=history,
            user_profile=user_profile,
            tool_functions=tool_functions
        )

        return ChatResponse(**response)
    except Exception as e:
        print(f"Error in chat_with_tully: {e}")  # Print actual error to terminal
        raise HTTPException(status_code=500, detail=str(e))