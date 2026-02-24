import uuid
from datetime import UTC, datetime

from ab_test_platform.src.models.experiments import ExperimentResult
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


class Learnings(SQLModel, table=True):
    __tablename__ = "learnings"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experiment_id: str = Field(
        foreign_key="experiments.id",
        nullable=False,
        unique=True,
    )
    hypothesis: str = Field(sa_column=Column(Text, nullable=False))
    primary_metric_key: str = Field(nullable=False)
    result: ExperimentResult = Field(nullable=False)
    result_description: str = Field(sa_column=Column(Text, nullable=False))

    tags: list[str] = Field(
        default=[],
        sa_column=Column(ARRAY(String), nullable=False, server_default="{}"),
    )
    platform: str | None = Field(default=None, max_length=50)
    segment: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    dashboard_link: str | None = Field(default=None, max_length=500)
    ticket_link: str | None = Field(default=None, max_length=500)

    notes: str = Field(sa_column=Column(Text, nullable=False))

    created_by: str = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
        )
    )
