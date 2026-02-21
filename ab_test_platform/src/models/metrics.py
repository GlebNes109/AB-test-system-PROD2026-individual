import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field


class AggregationType(str, Enum):
    COUNT = "COUNT"
    COUNT_UNIQUE = "COUNT_UNIQUE"
    SUM = "SUM"
    AVG = "AVG"


class Metrics(SQLModel, table=True):
    __tablename__ = "metrics"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    key: str = Field(unique=True, nullable=False)
    name: str = Field(nullable=False)
    description: Optional[str] = None

    event_type: str = Field(nullable=False)
    aggregation: AggregationType = Field(nullable=False)
    payload_field: Optional[str] = None

    denominator_event_type: Optional[str] = None
    denominator_aggregation: Optional[AggregationType] = None

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )


class MetricType(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    GUARDRAIL = "GUARDRAIL"


class GuardrailAction(str, Enum):
    PAUSE = "PAUSE"
    ROLLBACK = "ROLLBACK"


class ExperimentMetrics(SQLModel, table=True):
    __tablename__ = "experiment_metrics"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experiment_id: str = Field(foreign_key="experiments.id", nullable=False)
    metric_id: str = Field(foreign_key="metrics.id", nullable=False)
    type: MetricType = Field(nullable=False)

    # guardrail-specific fields
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    action: Optional[GuardrailAction] = None