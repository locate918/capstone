import os
import httpx
from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services import gemini

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")

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
    # Ensure dates are in full ISO 8601 format for the Rust backend
    # Gemini often returns 'YYYY-MM-DD', but Rust's DateTime<Utc> needs time info.
    if args.get("start_date") and len(str(args["start_date"])) == 10:
        args["start_date"] = f"{args['start_date']}T00:00:00Z"
    if args.get("end_date") and len(str(args["end_date"])) == 10:
        args["end_date"] = f"{args['end_date']}T23:59:59Z"

    # Filter out null values to keep the query clean
    params = {k: v for k, v in args.items() if v is not None}
    
    print(f"DEBUG: Connecting to Backend at {BACKEND_URL}/api/events/search with params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/events/search", params=params)
            if response.status_code == 200:
                events = response.json()
                # Limit results to avoid overflowing the LLM context window
                return {"events": events[:10], "count": len(events)}
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

        response = await gemini.generate_chat_response(
            message=request.message,
            history=sanitize_history(request.conversation_history),
            user_profile=user_profile,
            tool_functions=tool_functions
        )
        
        return ChatResponse(**response)
    except Exception as e:
        print(f"Error in chat_with_tully: {e}")  # Print actual error to terminal
        raise HTTPException(status_code=500, detail=str(e))