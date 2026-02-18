from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Granularity(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class VariantMetricValue(BaseModel):
    metric_key: str
    metric_name: str
    value: Optional[float] = None


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
    totals: Optional[VariantReport] = None


class TimeseriesPoint(BaseModel):
    timestamp: datetime
    value: Optional[float] = None


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
