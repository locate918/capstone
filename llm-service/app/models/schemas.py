from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class Event(BaseModel):
    """
    Represents an event as stored in the database.
    """
    # Mandatory fields
    id: UUID
    title: str
    description: str
    venue: str
    venue_address: str
    source_url: str
    source_name: str
    start_time: datetime
    created_at: datetime
    updated_at: datetime

    # Optional fields
    location: Optional[str] = None
    end_time: Optional[datetime] = None
    categories: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    outdoor: Optional[bool] = None
    family_friendly: Optional[bool] = None
    image_url: Optional[str] = None


class NormalizedEvent(BaseModel):
    """
    Represents an event extracted and normalized by the LLM from raw sources.
    Used by app.services.gemini.normalize_events
    """
    title: str
    venue: str
    venue_address: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    description: str
    categories: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    outdoor: Optional[bool] = None
    family_friendly: Optional[bool] = None
    image_url: Optional[str] = None


class NormalizeRequest(BaseModel):
    raw_content: str
    source_url: str
    content_type: str = "html"

class NormalizeResponse(BaseModel):
    events: List[NormalizedEvent]

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    parsed_params: Dict[str, Any]

class ChatRequest(BaseModel):
    # Allow frontend to send 'userId' and 'conversationHistory' (camelCase)
    user_id: str = Field(..., alias="userId")
    message: str
    conversation_history: Optional[List[Dict[str, Any]]] = Field(default=[], alias="conversationHistory")
    conversation_id: Optional[str] = Field(default=None, alias="conversationId")

    model_config = ConfigDict(populate_by_name=True)

class ChatResponse(BaseModel):
    text: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None