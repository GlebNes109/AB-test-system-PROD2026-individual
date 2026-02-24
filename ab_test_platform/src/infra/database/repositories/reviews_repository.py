from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import SortOrder
from ab_test_platform.src.domain.interfaces.repositories.reviews_repository_interface import (
    ReviewsRepositoryInterface,
)
from ab_test_platform.src.infra.database.repositories.base_repository import BaseRepository
from ab_test_platform.src.models.experiments import Experiments
from ab_test_platform.src.models.reviews import ReviewDecisions, Reviews
from ab_test_platform.src.schemas.reviews import ReviewsRead
from sqlalchemy import asc, desc, func, select


class ReviewsRepository(BaseRepository, ReviewsRepositoryInterface):
    async def count_by_decision(self, experiment_id: str, decision: ReviewDecisions) -> int:
        stmt = select(func.count()).where(
            Reviews.experiment_id == experiment_id,
            Reviews.decision == decision,
        )
        return await self.session.scalar(stmt) or 0

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
        stmt = select(Reviews)

        if experimenter_id:
            stmt = stmt.join(Experiments, Reviews.experiment_id == Experiments.id).where(
                Experiments.created_by == experimenter_id
            )

        if experiment_id:
            stmt = stmt.where(Reviews.experiment_id == experiment_id)

        if reviewer_id:
            stmt = stmt.where(Reviews.reviewer_id == reviewer_id)

        if order_by:
            column = getattr(self.model, order_by, None)
            if column is None:
                raise ValueError(f"Invalid order_by field: {order_by}")

            stmt = stmt.order_by(
                asc(column) if order == SortOrder.ASC else desc(column), asc(self.model.id)
            )
        else:
            stmt = stmt.order_by(asc(self.model.id))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        objs = result.scalars().all()
        return [self.read_schema.model_validate(obj, from_attributes=True) for obj in objs], total
