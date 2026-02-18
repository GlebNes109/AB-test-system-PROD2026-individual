from typing import Optional, List

from pydantic import BaseModel, Field


class DslValidateRequest(BaseModel):
    dslExpression: str = Field(min_length=3, max_length=2000)


class DslError(BaseModel):
    code: str
    message: str
    position: Optional[int] = None
    near: Optional[str] = None


class DslValidateResponse(BaseModel):
    isValid: bool
    normalizedExpression: Optional[str] = None
    errors: List[DslError] = Field(default_factory=list)