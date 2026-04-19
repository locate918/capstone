import os
import time

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
        start_time = time.time()
        
        # 1. Handle "Normal" Keyword Search if smart search is disabled
        if not request.use_smart_search:
            print(f"DEBUG: Smart search disabled. Using normal keyword search for: '{request.query}'")
            params = {"q": request.query}
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/api/events/search", params=params)
                events = response.json() if response.status_code == 200 else []
            
            return SearchResponse(parsed_params=params, events=events)

        # 2. Parse natural language into JSON params (Smart Search)
        params = await gemini.parse_user_intent(request.query)
        print(f"DEBUG: AI parsed parameters ({time.time() - start_time:.2f}s): {params}")

        # Fallback: If the LLM returns no meaningful parameters (all None),
        # assume the user's query is a direct keyword search.
        if all(v is None for v in params.values()):
            params["q"] = request.query

        # PRE-PROCESSING: Remove common noise from 'q'
        if params.get("q"):
            noise_words = {"under", "for", "at", "in", "around", "event", "events", "near"}
            q_parts = [w for w in params["q"].split() if w.lower() not in noise_words]
            params["q"] = " ".join(q_parts) if q_parts else None

        # 2. Format dates for backend (YYYY-MM-DD -> ISO)
        if params.get("start_date") and len(str(params["start_date"])) == 10:
            params["start_date"] = f"{params['start_date']}T00:00:00Z"
        if params.get("end_date") and len(str(params["end_date"])) == 10:
            params["end_date"] = f"{params['end_date']}T23:59:59Z"

        # 3. Query the Rust Backend
        clean_params = {k: v for k, v in params.items() if v is not None}
        events = []

        async with httpx.AsyncClient() as client:
            backend_start = time.time()
            response = await client.get(f"{BACKEND_URL}/api/events/search", params=clean_params)
            print(f"DEBUG: Initial search took {time.time() - backend_start:.2f}s")
            if response.status_code == 200:
                events = response.json()

            # RELAXATION PROTOCOL: If smart search returns nothing, try relaxing filters
            if not events:
                relaxed_params = clean_params.copy()
                relaxed = False

                # Step 1: If we have both q and category, and they overlap, try removing q
                if "q" in relaxed_params and "category" in relaxed_params:
                    q_lower = relaxed_params["q"].lower()
                    cat_lower = relaxed_params["category"].lower()
                    # Also consider if q is just a substring of category or vice versa
                    if cat_lower in q_lower or q_lower in cat_lower or q_lower == "music":
                        del relaxed_params["q"]
                        relaxed = True

                # Step 2: If still no events or we didn't relax in Step 1, try removing category
                if not relaxed and "category" in relaxed_params:
                    del relaxed_params["category"]
                    relaxed = True

                if relaxed:
                    print(f"DEBUG: No results for initial search. Relaxing parameters to: {relaxed_params}")
                    relax_start = time.time()
                    response = await client.get(f"{BACKEND_URL}/api/events/search", params=relaxed_params)
                    print(f"DEBUG: Relaxed search took {time.time() - relax_start:.2f}s")
                    if response.status_code == 200:
                        events = response.json()

            # FALLBACK: If still nothing, but we have an original 'q', try searching JUST with 'q'.
            if not events and params.get("q"):
                fallback_params = {"q": params["q"]}
                print(f"DEBUG: Still no results. Falling back to simple keyword search: {fallback_params}")
                fallback_start = time.time()
                response = await client.get(f"{BACKEND_URL}/api/events/search", params=fallback_params)
                print(f"DEBUG: Fallback search took {time.time() - fallback_start:.2f}s")
                if response.status_code == 200:
                    events = response.json()

        print(f"DEBUG: Total search workflow took {time.time() - start_time:.2f}s")

        # if request.user_id:
        #   profile = await get_user_profile(request.user_id, authorization)
        #   events = ranking.rank_events(events, profile)

        return SearchResponse(parsed_params=params, events=events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
