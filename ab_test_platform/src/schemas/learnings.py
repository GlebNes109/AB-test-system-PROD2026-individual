from datetime import datetime

from ab_test_platform.src.models.experiments import ExperimentResult
from pydantic import BaseModel, field_validator


class LearningCreate(BaseModel):
    experiment_id: str
    hypothesis: str
    primary_metric_key: str
    tags: list[str] = []
    platform: str | None = None
    segment: str | None = None
    dashboard_link: str | None = None
    ticket_link: str | None = None
    notes: str

    @field_validator("hypothesis")
    @classmethod
    def hypothesis_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("hypothesis must not be empty")
        return v

    @field_validator("notes")
    @classmethod
    def notes_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("notes must not be empty")
        return v


class LearningUpdate(BaseModel):
    hypothesis: str | None = None
    primary_metric_key: str | None = None
    tags: list[str] | None = None
    platform: str | None = None
    segment: str | None = None
    dashboard_link: str | None = None
    ticket_link: str | None = None
    notes: str | None = None


class LearningResponse(BaseModel):
    id: str
    experiment_id: str
    experiment_name: str | None = None
    feature_flag_key: str | None = None
    hypothesis: str
    primary_metric_key: str
    result: ExperimentResult
    result_description: str
    tags: list[str] = []
    platform: str | None = None
    segment: str | None = None
    dashboard_link: str | None = None
    ticket_link: str | None = None
    notes: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PagedLearnings(BaseModel):
    items: list[LearningResponse]
    total: int
    page: int
    size: int


class SimilarLearningResponse(BaseModel):
    learning: LearningResponse
    similarity_reason: list[str]
