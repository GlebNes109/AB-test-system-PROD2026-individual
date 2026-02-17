from sqlalchemy import select

from src.domain.exceptions import EntityNotFoundError
from src.domain.interfaces.repositories.metrics_repository_interface import MetricsRepositoryInterface
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.metrics import Metrics


class MetricsRepository(BaseRepository, MetricsRepositoryInterface):
    async def get_by_key(self, key: str) -> Metrics:
        stmt = select(Metrics).where(Metrics.key == key)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError(f"Metric '{key}' not found")
        return self.read_schema.model_validate(obj, from_attributes=True)