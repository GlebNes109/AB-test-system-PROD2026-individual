import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import Column, DateTime

from sqlmodel import SQLModel, Field

class ReviewDecisions(Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REQUEST_IMPROVEMENTS = "REQUEST_IMPROVEMENTS"


class Reviews(SQLModel, table=True):
    __tablename__ = "experiments_reviews"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experiment_id: str
    reviewer_id: str
    decision: ReviewDecisions
    comment: str
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
