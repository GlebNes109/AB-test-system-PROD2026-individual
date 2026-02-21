import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Column, JSON, DateTime
from sqlmodel import SQLModel, Field


class EventsStatus(Enum):
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    REJECTED = "REJECTED"

class RejectedReason(Enum):
    DUPLICATE = "DUPLICATE"
    INVALID_EVENT_TYPE = "INVALID_EVENT_TYPE"
    INVALID_DECISION_ID = "INVALID_DECISION_ID"

class EventsRaw(SQLModel, table=True):
    __tablename__ = "events_raw"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    event_type_id: str
    decision_id: str
    subject_id: str
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True)
    )
    status: EventsStatus

    occurred_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    ) # если в апи не передано иное - считается что событие произошло в момент получения

    received_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
    rejected_reason: Optional[RejectedReason] = None


class Events(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    event_type_id: str
    decision_id: str
    subject_id: str
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True)
    )
    # status: EventsStatus - статус не нужен, в этой таблице только принятые.

    occurred_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    ) # если в апи не передано иное - считается что событие произошло в момент получения

    received_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )

class EventTypes(SQLModel, table=True):
    __tablename__ = "event_types"
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    type: str = Field(unique=True)
    description: str
    requires_event_id: Optional[str] = None
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
