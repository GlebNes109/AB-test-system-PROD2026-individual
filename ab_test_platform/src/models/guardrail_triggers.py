import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field

from ab_test_platform.src.models.metrics import GuardrailAction


class GuardrailTriggers(SQLModel, table=True):
    __tablename__ = "guardrail_triggers"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experiment_id: str = Field(foreign_key="experiments.id", nullable=False)
    metric_id: str = Field(foreign_key="metrics.id", nullable=False)
    threshold: float = Field(nullable=False)
    actual_value: float = Field(nullable=False)
    action_taken: GuardrailAction = Field(nullable=False)
    triggered_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
