from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from ab_test_platform.src.infra.database.repositories.base_repository import SortOrder
from ab_test_platform.src.models.reviews import ReviewDecisions
from ab_test_platform.src.schemas.reviews import ReviewsRead


class ReviewsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def count_by_decision(self, experiment_id: str, decision: ReviewDecisions) -> int:
        ...

    @abstractmethod
    async def get_all_with_params(
        self,
        limit: int,
        offset: int,
        order_by: str | None = None,
        order: SortOrder = SortOrder.DESC,
        experimenter_id: str | None = None,
        experiment_id: str | None = None,
        reviewer_id: str | None = None,
    ) -> tuple[list[ReviewsRead], int]:
        ...