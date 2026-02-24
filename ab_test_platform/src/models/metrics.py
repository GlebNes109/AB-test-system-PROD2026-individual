import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


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
    description: str | None = None

    event_type: str = Field(nullable=False)
    aggregation: AggregationType = Field(nullable=False)
    payload_field: str | None = None

    denominator_event_type: str | None = None
    denominator_aggregation: AggregationType | None = None

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
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
    threshold: float | None = None
    window_minutes: int | None = None
    action: GuardrailAction | None = None