from pydantic import BaseModel, Field


class DslValidateRequest(BaseModel):
    dslExpression: str = Field(min_length=3, max_length=2000)


class DslError(BaseModel):
    code: str
    message: str
    position: int | None = None
    near: str | None = None


class DslValidateResponse(BaseModel):
    isValid: bool
    normalizedExpression: str | None = None
    errors: list[DslError] = Field(default_factory=list)
