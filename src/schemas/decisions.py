import json
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class Subject(BaseModel):
    id: str
    subject_attr: dict[str, Any]
    flags_keys: list[str]


class DecisionsResponse(BaseModel):
    id: Optional[str] = None
    created_at: datetime
    value: Any