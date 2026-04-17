import os
import httpx
from fastapi import APIRouter, HTTPException, Header
from app.models.schemas import InteractionRequest
from app.services import ranking

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")

async def get_user_preferences(user_id: str, auth_header: str) -> list:
    """
    Fetches user preferences from the custom backend endpoint.
    """
    print(f"DEBUG: Attempting to fetch preferences for user_id: {user_id}")
    headers = {"Authorization": auth_header}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/users/me/preferences", headers=headers)
            response.raise_for_status()
            preferences = response.json()
            print(f"DEBUG: Successfully loaded {len(preferences)} preferences for user {user_id}.")
            return preferences
        except httpx.HTTPStatusError as e:
            print(f"DEBUG: Backend returned a non-2xx status for preferences: {e.response.status_code} {e.response.text}")
        except Exception as e:
            print(f"DEBUG: Failed to load preferences for user {user_id}. Error: {e}")
    # Return an empty list if the fetch fails for any reason
    return []

@router.post("/interactions")
async def log_interaction_and_update_preferences(request: InteractionRequest, authorization: str = Header(..., alias="Authorization")):
    """
    Logs a user interaction and updates their preferences in the backend.
    This function is designed to be resilient, logging failures without crashing.
    It requires the user's JWT to be passed in the 'Authorization' header.
    """
    print(f"\n--- New Interaction Received ---")
    print(f"DEBUG: Received interaction for user_id: {request.user_id}, type: {request.interaction_type}")
    print(f"DEBUG: Event Categories: {request.event_categories}")

    headers = {"Authorization": authorization}
    event_categories = request.event_categories

    # If event_categories are not provided (e.g., from a simple click tracker),
    # try to fetch them from the backend using the event_id.
    if not event_categories and request.event_id:
        print(f"DEBUG: Event categories missing for event {request.event_id}. Fetching from backend...")
        try:
            async with httpx.AsyncClient() as client:
                event_resp = await client.get(f"{BACKEND_URL}/api/events/{request.event_id}")
                event_resp.raise_for_status()
                event_data = event_resp.json()
                event_categories = event_data.get("categories", [])
                print(f"DEBUG: Fetched categories: {event_categories}")
        except Exception as e:
            print(f"WARN: Could not fetch categories for event {request.event_id}. Preference update will be skipped. Error: {e}")
            # Can still log the interaction, but we can't update preferences.
            event_categories = [] # Ensure it's an empty list

    # Part 1: Log the interaction itself
    # This part will try to log the interaction but won't stop the preference update if it fails.
    try:
        print("DEBUG: Attempting to log interaction to backend...")
        async with httpx.AsyncClient() as client:
            interaction_payload = {
                "event_id": request.event_id,
                "interaction_type": request.interaction_type,
            }
            response = await client.post(
                f"{BACKEND_URL}/api/users/me/interactions",
                json=interaction_payload,
                headers=headers
            )
            if response.status_code >= 400:
                print(f"WARN: Backend failed to log interaction: {response.status_code} {response.text}")
        print("DEBUG: Interaction logging finished.")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during interaction logging: {e}")

    if not event_categories:
        print("INFO: No event categories available. Skipping preference score update.")
        return {"status": "success", "detail": "Interaction logged, preference update skipped due to missing categories."}

    # Part 2: Calculate and update user preferences
    try:
        print("DEBUG: Starting preference update process...")

        # Calculate the new scores based on the new interaction.
        updated_preferences = ranking.score_categories_from_interaction(
            request.user_id,
            event_categories, # Use the potentially fetched categories
            request.interaction_type,
        )
        print(f"DEBUG: Calculated updated preference dictionary (deltas): {updated_preferences}")

        # Send each updated preference (delta) back to the backend, one by one.
        print("DEBUG: Attempting to send updated preferences to backend...")
        async with httpx.AsyncClient() as client:
            for category, score in updated_preferences.items():
                preference_payload = {
                    "category": category,
                    "weight": score
                }
                print(f"DEBUG: ...sending payload: {preference_payload}")
                response = await client.post(
                    f"{BACKEND_URL}/api/users/me/preferences",
                    json=preference_payload,
                    headers=headers)
                response.raise_for_status() # This will raise an error if the status is 4xx or 5xx

        print(f"Interaction Processed Successfully")
        return {"status": "success", "updated_preferences": updated_preferences}

    except httpx.HTTPStatusError as e:
        print(f"ERROR: A backend error occurred while updating preferences: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from backend updating preferences: {e.response.text}")
    except Exception as e:
        print(f"ERROR: A critical error occurred during preference update: {e}")
        raise HTTPException(status_code=500, detail=f"A critical error occurred during preference update: {e}")
