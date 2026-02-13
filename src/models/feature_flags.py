import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Text
from sqlmodel import SQLModel, Field


class FlagType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"


class FeatureFlags(SQLModel, table=True):
    __tablename__ = "feature_flags"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True
    )
    key: str = Field(unique=True, index=True)
    type: FlagType
    default_value: str
    description: str | None = Field(default=None)
    created_by: str | None = Field(default=None)

    createdAt: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
