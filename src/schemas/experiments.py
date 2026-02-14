from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, field_validator, model_validator

from src.models.experiments import ExperimentStatus


class VariantCreate(BaseModel):
    name: str
    value: Any  # значение валидируется в сервисе флагов
    weight: int
    is_control: bool = False


class VariantResponse(BaseModel):
    id: str
    name: str
    value: str
    weight: int
    is_control: bool

    model_config = {"from_attributes": True}


class MetricsType(Enum):
    PRIMARY = "PRIMARY"
    GUARDRAIL = "GUARDRAIL"
    SECONDARY = "SECONDARY"


class ExperimentMetrics:
    metric_id: str
    type: MetricsType
    threshold: Optional[str]
    window_minutes: Optional[str]
    action: Optional[str]
    # TODO threshold window_minutes и action задаются обязательно если MetricsType == GUARDRAIL и не задаются в ином случае

class ExperimentCreate(BaseModel):
    feature_flag_id: str
    name: str
    targeting_rule: Optional[str] = None
    audience_percentage: int
    variants: List[VariantCreate]

    @field_validator("audience_percentage")
    @classmethod
    def validate_audience(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("audience_percentage must be between 1 and 100")
        return v

    @field_validator("variants")
    @classmethod
    def validate_variants_not_empty(cls, v: List[VariantCreate]) -> List[VariantCreate]:
        if not v:
            raise ValueError("variants must not be empty")
        return v

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentCreate":
        variants = self.variants
        audience = self.audience_percentage

        control_count = sum(1 for var in variants if var.is_control)
        if control_count != 1:
            raise ValueError("Exactly one variant must be marked as control")

        total_weight = sum(var.weight for var in variants)
        if total_weight != audience:
            raise ValueError(
                f"Sum of variant weights ({total_weight}) must equal audience_percentage ({audience})"
            )
        return self


class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    targeting_rule: Optional[str] = None
    audience_percentage: Optional[int] = None
    variants: Optional[List[VariantCreate]] = None

    @field_validator("audience_percentage")
    @classmethod
    def validate_audience(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 100):
            raise ValueError("audience_percentage must be between 1 and 100")
        return v


class ExperimentResponse(BaseModel):
    id: str
    feature_flag_id: str
    created_by: str
    created_at: datetime
    version: int
    # fields from current version
    name: str
    targeting_rule: Optional[str]
    status: ExperimentStatus
    audience_percentage: int
    modified_by: Optional[str]
    variants: List[VariantResponse]

    model_config = {"from_attributes": True}


class PagedExperiments(BaseModel):
    items: List[ExperimentResponse]
    total: int
    page: int
    size: int
