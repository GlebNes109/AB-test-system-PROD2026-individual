from datetime import datetime
from typing import Any

from ab_test_platform.src.models.events import EventsStatus
from pydantic import BaseModel


class PayloadSchemaTypes:
    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"


class EventTypesCreate(BaseModel):
    type: str
    description: str
    requires_event_type: str | None = None
    payload_schema: dict[str, str] = {}  # field_name -> type ("string"|"number"|"bool")


class EventTypesResponse(BaseModel):
    id: str
    type: str
    description: str
    requires_event_id: str | None = None
    payload_schema: dict[str, str] = {}
    created_at: datetime


class EventCreate(BaseModel):
    event_type: str
    decision_id: str
    payload: dict[str, Any] | None = None
    occurred_at: datetime | None = None


class EventsBatchRequest(BaseModel):
    events: list[EventCreate]


class EventItemResponse(BaseModel):
    index: int
    status_code: int
    event_id: str | None = None
    event_status: EventsStatus | None = None
    error: str | None = None


class EventsBatchResponse(BaseModel):
    results: list[EventItemResponse]


class PagedEventTypes(BaseModel):
    items: list[EventTypesResponse]
    total: int
    page: int
    size: int