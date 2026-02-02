from fastapi import APIRouter, HTTPException
from app.models.schemas import NormalizeRequest, NormalizeResponse
from app.services import gemini

router = APIRouter()

@router.post("/normalize", response_model=NormalizeResponse)
async def normalize_event_data(request: NormalizeRequest):
    """
    Takes raw content (HTML or JSON) and extracts structured event data using Gemini.
    Used by scrapers to clean data before sending to the backend.
    """
    try:
        events = await gemini.normalize_events(request.raw_content, request.source_url, request.content_type)
        return NormalizeResponse(events=events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))