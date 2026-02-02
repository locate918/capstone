from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services import gemini

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_with_tully(request: ChatRequest):
    """
    Handles conversation with Tully.
    """
    try:
        # TODO: Fetch the user profile from the backend using request.user_id
        # For MVP, we mock a basic profile
        mock_user_profile = {
            "id": request.user_id,
            "location_preference": "Downtown Tulsa",
            "family_friendly_only": False
        }

        response = await gemini.generate_chat_response(
            message=request.message,
            history=request.conversation_history,
            user_profile=mock_user_profile
        )
        
        return ChatResponse(**response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))