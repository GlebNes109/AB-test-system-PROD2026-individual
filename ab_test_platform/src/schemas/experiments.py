from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, field_validator, model_validator

from ab_test_platform.src.domain.exceptions import UnsupportableContentError
from ab_test_platform.src.models.experiments import ExperimentStatus, ExperimentResult
from ab_test_platform.src.models.metrics import MetricType
from ab_test_platform.src.schemas.metrics import ExperimentMetricBind, ExperimentMetricResponse


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


class ExperimentCreate(BaseModel):
    feature_flag_key: str
    name: str
    targeting_rule: Optional[str] = None
    audience_percentage: int
    variants: List[VariantCreate]
    metrics: List[ExperimentMetricBind]

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
            raise UnsupportableContentError("variants must not be empty")
        return v

    @field_validator("metrics")
    @classmethod
    def validate_metrics_not_empty(cls, v: List[ExperimentMetricBind]) -> List[ExperimentMetricBind]:
        if not v:
            raise UnsupportableContentError("metrics must not be empty")
        return v

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentCreate":
        variants = self.variants
        audience = self.audience_percentage

        control_count = sum(1 for var in variants if var.is_control)
        if control_count != 1:
            raise UnsupportableContentError("Exactly one variant must be marked as control")

        total_weight = sum(var.weight for var in variants)
        if total_weight != audience:
            raise UnsupportableContentError(
                f"Sum of variant weights ({total_weight}) must equal audience_percentage ({audience})"
            )

        primary_count = sum(1 for m in self.metrics if m.type == MetricType.PRIMARY)
        if primary_count < 1:
            raise UnsupportableContentError("At least one PRIMARY metric is required")

        return self


class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    targeting_rule: Optional[str] = None
    audience_percentage: Optional[int] = None
    variants: Optional[List[VariantCreate]] = None
    metrics: Optional[List[ExperimentMetricBind]] = None

    @field_validator("audience_percentage")
    @classmethod
    def validate_audience(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 100):
            raise UnsupportableContentError("audience_percentage must be between 1 and 100")
        return v

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentUpdate":
        # Когда обновляется audience_percentage, но не обновляются варианты - в них становится неправильный weight потому что сумма весов должна давать audience_percentage.
        # Наоборот не работает - можно менять развесовку вариантов без изменения audience_percentage
        if self.audience_percentage is not None and self.variants is None:
            raise UnsupportableContentError(
                "Cannot change audience_percentage without providing variants, variant weights would become inconsistent"
            )

        if self.variants is not None:
            control_count = sum(1 for var in self.variants if var.is_control)
            if control_count != 1:
                raise UnsupportableContentError("Exactly one variant must be marked as control")

        if self.metrics is not None:
            if not self.metrics:
                raise UnsupportableContentError("metrics must not be empty")
            primary_count = sum(1 for m in self.metrics if m.type == MetricType.PRIMARY)
            if primary_count < 1:
                raise UnsupportableContentError("At least one PRIMARY metric is required")

        return self


class ExperimentResponse(BaseModel):
    id: str
    feature_flag_id: str
    feature_flag_key: str
    created_by: str
    created_at: datetime
    started_at: Optional[datetime] = None
    version: int
    # fields from current version
    name: str
    targeting_rule: Optional[str]
    status: ExperimentStatus
    audience_percentage: int
    modified_by: Optional[str]
    variants: List[VariantResponse]
    metrics: List[ExperimentMetricResponse] = []
    result: Optional[ExperimentResult] = None
    result_description: Optional[str] = None

    model_config = {"from_attributes": True}


class PagedExperiments(BaseModel):
    items: List[ExperimentResponse]
    total: int
    page: int
    size: int

class ExperimentFinish(BaseModel):
    result: ExperimentResult
    result_description: str