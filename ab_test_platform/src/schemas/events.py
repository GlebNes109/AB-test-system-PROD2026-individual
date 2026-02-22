from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from ab_test_platform.src.models.events import EventsStatus

class PayloadSchemaTypes:
    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"


class EventTypesCreate(BaseModel):
    type: str
    description: str
    requires_event_type: Optional[str] = None
    payload_schema: dict[str, str] = {}  # field_name -> type ("string"|"number"|"bool")


class EventTypesResponse(BaseModel):
    id: str
    type: str
    description: str
    requires_event_id: Optional[str] = None
    payload_schema: dict[str, str] = {}
    created_at: datetime


class EventCreate(BaseModel):
    event_type: str
    decision_id: str
    payload: Optional[dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class EventsBatchRequest(BaseModel):
    events: list[EventCreate]


class EventItemResponse(BaseModel):
    index: int
    status_code: int
    event_id: Optional[str] = None
    event_status: Optional[EventsStatus] = None
    error: Optional[str] = None


class EventsBatchResponse(BaseModel):
    results: list[EventItemResponse]


class PagedEventTypes(BaseModel):
    items: list[EventTypesResponse]
    total: int
    page: int
    size: int