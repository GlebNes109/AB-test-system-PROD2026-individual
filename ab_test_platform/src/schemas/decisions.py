from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Subject(BaseModel):
    id: str
    subject_attr: dict[str, Any]
    flags_keys: list[str]


class DecisionsResponse(BaseModel):
    id: str | None = None
    created_at: datetime
    value: Any
