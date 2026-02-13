from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

from src.models.feature_flags import FlagType


class FeatureFlagCreate(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    type: FlagType
    default_value: str
    description: Optional[str] = None


class FeatureFlagUpdateDefault(BaseModel):
    default_value: str


class FeatureFlagResponse(BaseModel):
    id: str
    key: str
    type: FlagType
    default_value: str
    description: str | None
    created_by: str | None
    createdAt: datetime


class PagedFeatureFlags(BaseModel):
    items: list[FeatureFlagResponse]
    total: int
    page: int
    size: int
