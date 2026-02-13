import os
import httpx
from fastapi import APIRouter, HTTPException
from app.models.schemas import SearchRequest, SearchResponse
from app.services import gemini

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")

@router.post("/search", response_model=SearchResponse)
async def search_intent(request: SearchRequest):
    """
    Analyzes a natural language query and extracts structured search parameters.
    Then queries the backend for matching events.
    """
    try:
        # 1. Parse natural language into JSON params
        params = await gemini.parse_user_intent(request.query)

        # Fallback: If the LLM returns no meaningful parameters (all None),
        # assume the user's query is a direct keyword search.
        if all(v is None for v in params.values()):
            params["q"] = request.query

        # 2. Format dates for backend (YYYY-MM-DD -> ISO)
        if params.get("start_date") and len(str(params["start_date"])) == 10:
            params["start_date"] = f"{params['start_date']}T00:00:00Z"
        if params.get("end_date") and len(str(params["end_date"])) == 10:
            params["end_date"] = f"{params['end_date']}T23:59:59Z"

        # 3. Query the Rust Backend
        clean_params = {k: v for k, v in params.items() if v is not None}
        events = []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/api/events/search", params=clean_params)
            if response.status_code == 200:
                events = response.json()
            
            # FALLBACK: If smart search returns nothing, but we have a 'q', try searching JUST 'q'.
            # This fixes cases where LLM infers a category/date that excludes the item the user is looking for by name.
            if not events and params.get("q"):
                fallback_params = {"q": params["q"]}
                response = await client.get(f"{BACKEND_URL}/api/events/search", params=fallback_params)
                if response.status_code == 200:
                    events = response.json()

        return SearchResponse(parsed_params=params, events=events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))