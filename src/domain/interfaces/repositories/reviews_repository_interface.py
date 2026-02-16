from abc import abstractmethod
from typing import Protocol

from src.infra.database.repositories.base_repository import SortOrder
from src.models.reviews import ReviewDecisions
from src.schemas.reviews import ReviewsRead


class ReviewsRepositoryInterface(Protocol):
    @abstractmethod
    async def count_by_decision(self, experiment_id: str, decision: ReviewDecisions) -> int:
        ...

    async def get_all_with_params(
        self,
        limit: int,
        offset: int,
        order_by: str | None = None,
        order: SortOrder = SortOrder.DESC,
        experimenter_id: str | None = None,
        experiment_id: str | None = None,
    ) -> tuple[list[ReviewsRead], int]:
        ...