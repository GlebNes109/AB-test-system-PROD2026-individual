from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Granularity(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class VariantMetricValue(BaseModel):
    metric_key: str
    metric_name: str
    value: float | None = 0


class VariantReport(BaseModel):
    variant_id: str
    variant_name: str
    variant_value: str
    is_control: bool
    subject_count: int
    metrics: list[VariantMetricValue]


class ExperimentReport(BaseModel):
    experiment_id: str
    experiment_name: str
    date_from: datetime
    date_to: datetime
    total_subjects: int
    variants: list[VariantReport]
    total_metrics: list[VariantMetricValue]


class TimeseriesPoint(BaseModel):
    bucket_start: datetime
    bucket_end: datetime
    value: float | None = None


class VariantTimeseries(BaseModel):
    variant_id: str
    variant_name: str
    is_control: bool
    points: list[TimeseriesPoint]


class MetricTimeseries(BaseModel):
    metric_key: str
    metric_name: str
    variants: list[VariantTimeseries]


class ExperimentTimeseriesReport(BaseModel):
    experiment_id: str
    experiment_name: str
    date_from: datetime
    date_to: datetime
    granularity: Granularity
    metrics: list[MetricTimeseries]
