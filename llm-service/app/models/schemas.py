from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# Search Schemas

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    parsed_params: Dict[str, Any]
    # For now just returns the parsed intent.

# Chat Schemas

class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_history: Optional[List[Dict[str, Any]]] = []
    # Example history item: {"role": "user", "parts": ["Hello"]}

class ChatResponse(BaseModel):
    text: Optional[str]
    tool_call: Optional[Dict[str, Any]]

# Normalization Schemas

class NormalizeRequest(BaseModel):
    raw_content: str
    source_url: str
    content_type: str = "html"  # "html" or "json"

class NormalizedEvent(BaseModel):
    title: str
    venue: str
    start_time: datetime
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None

class NormalizeResponse(BaseModel):
    events: List[NormalizedEvent]