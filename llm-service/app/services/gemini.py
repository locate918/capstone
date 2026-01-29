"""
Locate918 LLM Service - Gemini Integration
==========================================
Owner: Ben (AI Engineer)

Core integration with Google's Gemini API.

Setup:
1. Get API key at https://makersuite.google.com/app/apikey
2. pip install google-generativeai
3. Add GEMINI_API_KEY to .env

Functions to implement:
- parse_user_intent(message) → SearchParams
- generate_chat_response(message, events, user_profile) → str
- normalize_events(raw_events) → List[NormalizedEvent]

See backend/src/services/llm.rs for the Rust client that calls these.
"""

import os
import json
from typing import List, Dict, Any
import google.generativeai as genai
from app.models.schemas import NormalizedEvent
from app.tools.definitions import gemini_tools
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=API_KEY)

# Model Instantiation
# Instantiate the JSON-mode model for parsing and normalization.
# We use Gemini 2.0 Flash for its speed and improved instruction following.
json_model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    generation_config={"response_mime_type": "application/json"}
)


async def parse_user_intent(message: str) -> Dict[str, Any]:
    """
    Uses Gemini 2.0 Flash to extract search parameters from natural language.
    Returns a JSON object compatible with the backend search API.
    """
    prompt = f"""
    Extract search parameters from this query: "{message}"
    
    Output a valid JSON object with any of the following keys based on the query: 
    q, category, start_date, end_date, price_max, location, family_friendly, outdoor.
    Use null for missing fields.
    For dates, convert "this weekend" or "tomorrow" to approximate ISO dates based on current context.
    """
    
    response = await json_model.generate_content_async(prompt)
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"q": message}


async def generate_chat_response(message: str, history: List[Dict], user_profile: Dict) -> Dict[str, Any]:
    """
    Uses Gemini 2.0 Flash for conversation. Handles tool calling.
    Returns a dictionary containing the text response and any tool calls to be executed.
    """
    
    # Construct system prompt with user context
    system_instruction = f"""
    You are Tully, a friendly and knowledgeable event guide for Tulsa, OK (area code 918).
    User Profile: {json.dumps(user_profile)}
    
    If the user asks for events, use the `search_events` tool.
    If the user asks about weather or directions, answer generally or suggest checking a map.
    Be concise, enthusiastic, and helpful.
    """

    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        tools=gemini_tools,
        system_instruction=system_instruction
    )

    # The history object must be a list of dicts in the format:
    # [{'role': 'user', 'parts': ['...']}, {'role': 'model', 'parts': ['...']}]
    # The SDK can consume this directly.
    chat = model.start_chat(history=history)
    
    response = await chat.send_message_async(message)
    
    # Check for function calls
    if response.parts and response.parts[0].function_call:
        fc = response.parts[0].function_call
        return {
            "text": None,
            "tool_call": {
                "name": fc.name,
                "args": dict(fc.args)
            }
        }
    
    return {"text": response.text, "tool_call": None}


async def normalize_events(raw_content: str, source_url: str, content_type: str = "html") -> List[Dict]:
    """
    Uses Gemini 2.0 Flash to extract structured event data from raw HTML or JSON.
    """
    if content_type.lower() == "json":
        instruction = "Map the following raw JSON data into the standardized event format below. Handle nested structures and different field names intelligently."
    else:
        instruction = "Extract distinct events from the following HTML content. Ignore navigation, footers, and unrelated text."

    prompt = f"""
    {instruction}
    Source URL: {source_url}
    
    Output Format: A JSON list of objects with these exact keys:
    - title (string)
    - venue (string)
    - start_time (ISO 8601 string)
    - price_min (number or null)
    - price_max (number or null)
    - description (string, brief summary)
    - image_url (string or null)
    
    Input Data:
    {raw_content[:150000]}
    """

    response = await json_model.generate_content_async(prompt)
    try:
        raw_data = json.loads(response.text)
        valid_events = []
        
        if isinstance(raw_data, list):
            for item in raw_data:
                try:
                    # Validate against the Pydantic schema. This drops invalid items
                    valid_events.append(NormalizedEvent(**item).model_dump())
                except Exception:
                    continue
                    
        return valid_events
    except json.JSONDecodeError:
        # If the model output is not valid JSON, return an empty list.
        return []