import uuid
from datetime import datetime, timezone
from enum import Enum, UNIQUE
from typing import Optional, List

from sqlalchemy import Column, DateTime, Text
from sqlmodel import SQLModel, Field, Relationship


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ARCHIVED = "archived"
    REJECTED = "rejected"


ALLOWED_TRANSITIONS: dict[ExperimentStatus, list[ExperimentStatus]] = {
    ExperimentStatus.DRAFT: [ExperimentStatus.REVIEW],
    ExperimentStatus.REVIEW: [ExperimentStatus.APPROVED, ExperimentStatus.DRAFT, ExperimentStatus.REJECTED],
    ExperimentStatus.APPROVED: [ExperimentStatus.RUNNING],
    ExperimentStatus.RUNNING: [ExperimentStatus.PAUSED, ExperimentStatus.FINISHED],
    ExperimentStatus.PAUSED: [ExperimentStatus.RUNNING, ExperimentStatus.FINISHED],
    ExperimentStatus.FINISHED: [ExperimentStatus.ARCHIVED],
    ExperimentStatus.REJECTED: [ExperimentStatus.DRAFT],
    ExperimentStatus.ARCHIVED: [],
}

# Статусы, на которых нельзя менять версию эксперимента
FROZEN_STATUSES = {ExperimentStatus.RUNNING, ExperimentStatus.PAUSED}

class ExperimentResult(Enum):
    ROLLOUT = "ROLLOUT"
    ROLLBACK = "ROLLBACK"
    NO_EFFECT = "NO_EFFECT"


class Experiments(SQLModel, table=True):
    __tablename__ = "experiments"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    feature_flag_id: str = Field(foreign_key="feature_flags.id", nullable=False)
    created_by: str = Field(foreign_key="users.id", nullable=False)
    status: ExperimentStatus = Field(default=ExperimentStatus.DRAFT)
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        )
    )
    result: Optional[ExperimentResult] = None
    result_description: Optional[str] = None
    versions: List["ExperimentVersions"] = Relationship(back_populates="experiment")


class ExperimentVersions(SQLModel, table=True):
    __tablename__ = "experiment_versions"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experiment_id: str = Field(foreign_key="experiments.id", nullable=False)
    name: str
    version_number: int
    targeting_rule: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    audience_percentage: int
    modified_by: Optional[str] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )

    experiment: Optional[Experiments] = Relationship(back_populates="versions")
    variants: List["Variants"] = Relationship(back_populates="experiment_version")


class Variants(SQLModel, table=True):
    __tablename__ = "variants"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experiment_version_id: str = Field(foreign_key="experiment_versions.id", nullable=False)
    name: str
    value: str
    weight: int
    is_control: bool = Field(default=False)

    experiment_version: Optional[ExperimentVersions] = Relationship(back_populates="variants")
