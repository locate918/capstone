import os
import httpx
from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services import gemini

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")

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
    # Filter out null values to keep the query clean
    params = {k: v for k, v in args.items() if v is not None}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/events/search", params=params)
            if response.status_code == 200:
                events = response.json()
                # Limit results to avoid overflowing the LLM context window
                return {"events": events[:10], "count": len(events)}
            return {"error": f"Backend returned status {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

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
            history=request.conversation_history,
            user_profile=user_profile,
            tool_functions=tool_functions
        )
        
        return ChatResponse(**response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))