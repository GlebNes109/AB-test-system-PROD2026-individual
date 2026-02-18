from datetime import datetime

from pydantic import BaseModel

from ab_test_platform.src.models.reviews import ReviewDecisions


class ReviewsCreate(BaseModel):
    decision: ReviewDecisions
    comment: str


class ReviewsRead(BaseModel):
    experiment_id: str
    reviewer_id: str
    decision: ReviewDecisions
    comment: str
    created_at: datetime

class PagedReviews(BaseModel):
    items: list[ReviewsRead]
    total: int
    page: int
    size: int