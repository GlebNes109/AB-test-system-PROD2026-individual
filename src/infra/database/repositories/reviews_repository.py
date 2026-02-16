import uuid
from enum import Enum
from sqlalchemy import select, update, delete, func, asc, desc

from src.domain.interfaces.repositories.base_repository_interface import SortOrder
from src.domain.interfaces.repositories.reviews_repository_interface import ReviewsRepositoryInterface
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.experiments import Experiments
from src.models.models import ReadModelType, ModelType
from src.models.reviews import Reviews, ReviewDecisions
from src.schemas.reviews import ReviewsRead



class ReviewsRepository(BaseRepository, ReviewsRepositoryInterface):
    async def count_by_decision(self, experiment_id: str, decision: ReviewDecisions) -> int:
        stmt = select(func.count()).where(
            Reviews.experiment_id == experiment_id,
            Reviews.decision == decision,
        )
        return await self.session.scalar(stmt) or 0

    async def get_all_with_params(self, limit: int, offset: int, order_by: str | None = None, order: SortOrder = SortOrder.DESC, experimenter_id: str | None = None, experiment_id: str | None = None) -> tuple[list[ReviewsRead], int]:
        stmt = select(Reviews).limit(limit).offset(offset)
        if experimenter_id:
            stmt = stmt.where(Experiments.created_by == experimenter_id).join(Reviews.experiment_id == Experiments.id)

        if experiment_id:
            stmt = stmt.where(Experiments.id == experiment_id)

        if order_by:
            column = getattr(self.model, order_by, None)
            if column is None:
                raise ValueError(f"Invalid order_by field: {order_by}")

            stmt = stmt.order_by(
                asc(column) if order == SortOrder.ASC else desc(column),
                asc(self.model.id)
            )
        else:
            stmt = stmt.order_by(asc(self.model.id))

        result = await self.session.execute(stmt)
        objs = result.scalars().all()
        count_stmt = select(func.count()).select_from(self.model)
        total = await self.session.scalar(count_stmt)
        return [self.read_schema.model_validate(obj, from_attributes=True) for obj in objs], total