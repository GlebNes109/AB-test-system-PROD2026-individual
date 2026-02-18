from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, model_validator

from ab_test_platform.src.domain.exceptions import UnsupportableContentError
from ab_test_platform.src.models.metrics import AggregationType, MetricType, GuardrailAction


class MetricCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    event_type: str
    aggregation: AggregationType
    payload_field: Optional[str] = None
    denominator_event_type: Optional[str] = None
    denominator_aggregation: Optional[AggregationType] = None
    requires_exposure: bool = False

    @model_validator(mode="after")
    def validate_aggregation_fields(self) -> "MetricCreate":
        if self.aggregation in (AggregationType.SUM, AggregationType.AVG) and not self.payload_field:
            raise UnsupportableContentError(
                f"payload_field is required for {self.aggregation.value} aggregation"
            )
        if self.denominator_event_type is not None and self.denominator_aggregation is None:
            raise UnsupportableContentError(
                "denominator_aggregation is required when denominator_event_type is set"
            )
        return self


class MetricUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    aggregation: Optional[AggregationType] = None
    payload_field: Optional[str] = None
    denominator_event_type: Optional[str] = None
    denominator_aggregation: Optional[AggregationType] = None
    requires_exposure: Optional[bool] = None


class MetricResponse(BaseModel):
    id: str
    key: str
    name: str
    description: Optional[str]
    event_type: str
    aggregation: AggregationType
    payload_field: Optional[str]
    denominator_event_type: Optional[str]
    denominator_aggregation: Optional[AggregationType]
    requires_exposure: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PagedMetrics(BaseModel):
    items: List[MetricResponse]
    total: int
    page: int
    size: int


class ExperimentMetricBind(BaseModel):
    metric_key: str
    type: MetricType
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    action: Optional[GuardrailAction] = None

    @model_validator(mode="after")
    def validate_guardrail(self) -> "ExperimentMetricBind":
        if self.type == MetricType.GUARDRAIL:
            missing = []
            if self.threshold is None:
                missing.append("threshold")
            if self.window_minutes is None:
                missing.append("window_minutes")
            if self.action is None:
                missing.append("action")
            if missing:
                raise UnsupportableContentError(
                    f"Guardrail metrics require: {', '.join(missing)}"
                )
        else:
            if any([self.threshold is not None, self.window_minutes is not None, self.action is not None]):
                raise UnsupportableContentError(
                    "threshold, window_minutes, action can only be set for GUARDRAIL metrics"
                )
        return self


class ExperimentMetricResponse(BaseModel):
    metric_id: str
    metric_key: str
    metric_name: str
    type: MetricType
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    action: Optional[GuardrailAction] = None

    model_config = {"from_attributes": True}