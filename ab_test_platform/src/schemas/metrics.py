from datetime import datetime

from ab_test_platform.src.domain.exceptions import UnsupportableContentError
from ab_test_platform.src.models.metrics import AggregationType, GuardrailAction, MetricType
from pydantic import BaseModel, model_validator


class MetricCreate(BaseModel):
    key: str
    name: str
    description: str | None = None
    event_type: str
    aggregation: AggregationType
    payload_field: str | None = None
    denominator_event_type: str | None = None
    denominator_aggregation: AggregationType | None = None

    @model_validator(mode="after")
    def validate_aggregation_fields(self) -> "MetricCreate":
        if (
            self.aggregation in (AggregationType.SUM, AggregationType.AVG)
            and not self.payload_field
        ):
            raise UnsupportableContentError(
                f"payload_field is required for {self.aggregation.value} aggregation"
            )
        if self.denominator_event_type is not None and self.denominator_aggregation is None:
            raise UnsupportableContentError(
                "denominator_aggregation is required when denominator_event_type is set"
            )
        return self


class MetricUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    event_type: str | None = None
    aggregation: AggregationType | None = None
    payload_field: str | None = None
    denominator_event_type: str | None = None
    denominator_aggregation: AggregationType | None = None


class MetricResponse(BaseModel):
    id: str
    key: str
    name: str
    description: str | None
    event_type: str
    aggregation: AggregationType
    payload_field: str | None
    denominator_event_type: str | None
    denominator_aggregation: AggregationType | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PagedMetrics(BaseModel):
    items: list[MetricResponse]
    total: int
    page: int
    size: int


class ExperimentMetricBind(BaseModel):
    metric_key: str
    type: MetricType
    threshold: float | None = None
    window_minutes: int | None = None
    action: GuardrailAction | None = None

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
                raise UnsupportableContentError(f"Guardrail metrics require: {', '.join(missing)}")
        else:
            if any(
                [
                    self.threshold is not None,
                    self.window_minutes is not None,
                    self.action is not None,
                ]
            ):
                raise UnsupportableContentError(
                    "threshold, window_minutes, action can only be set for GUARDRAIL metrics"
                )
        return self


class ExperimentMetricResponse(BaseModel):
    metric_id: str
    metric_key: str
    metric_name: str
    type: MetricType
    threshold: float | None = None
    window_minutes: int | None = None
    action: GuardrailAction | None = None

    model_config = {"from_attributes": True}
