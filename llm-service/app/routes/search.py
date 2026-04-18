import os

import httpx
from fastapi import APIRouter, HTTPException, Header

from app.models.schemas import SearchRequest, SearchResponse
from app.services import gemini

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")


async def get_user_profile(user_id: str, auth_header: str):
    """
    Fetches user profile from backend.
    """
    if not auth_header:
        print(f"DEBUG: No auth header for user {user_id}, using fallback profile.")
        # Fallback default profile
        return {
            "user": {
                "id": user_id,
                "location_preference": "Tulsa",
                "family_friendly_only": False,
                "has_completed_onboarding": False,
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
                print(
                    f"DEBUG: Loaded profile for user {user_id} ({profile_data.get('user', {}).get('email', 'unknown')})")
                return profile_data
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
            "has_completed_onboarding": False,
            "email": "guest@locate918.com"
        },
        "preferences": [],
        "recent_interactions": []
    }


@router.post("/search", response_model=SearchResponse)
async def search_intent(request: SearchRequest, authorization: str = Header(None, alias="Authorization")):
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

            # FALLBACK: If smart search returns nothing, but we have a 'q', try searching just with 'q'.
            if not events and params.get("q"):
                fallback_params = {"q": params["q"]}
                response = await client.get(f"{BACKEND_URL}/api/events/search", params=fallback_params)
                if response.status_code == 200:
                    events = response.json()

        # if request.user_id:
        #   profile = await get_user_profile(request.user_id, authorization)
        #   events = ranking.rank_events(events, profile)

        return SearchResponse(parsed_params=params, events=events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
