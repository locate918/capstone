from fastapi import APIRouter, HTTPException
from app.models.schemas import SearchRequest, SearchResponse
from app.services import gemini

router = APIRouter()

@router.post("/search", response_model=SearchResponse)
async def search_intent(request: SearchRequest):
    """
    Analyzes a natural language query and extracts structured search parameters.
    """
    try:
        params = await gemini.parse_user_intent(request.query)
        return SearchResponse(parsed_params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))