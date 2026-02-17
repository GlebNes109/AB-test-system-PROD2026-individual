from src.domain.interfaces.repositories.metrics_repository_interface import MetricsRepositoryInterface
from src.models.metrics import Metrics
from src.schemas.metrics import MetricCreate, MetricUpdate, MetricResponse, PagedMetrics


class MetricsService:
    def __init__(self, repository: MetricsRepositoryInterface):
        self.repository = repository

    async def create_metric(self, data: MetricCreate) -> MetricResponse:
        metric = await self.repository.create(Metrics(**data.model_dump()))
        return MetricResponse.model_validate(metric, from_attributes=True)

    async def get_metric(self, metric_id: str) -> MetricResponse:
        metric = await self.repository.get(metric_id)
        return MetricResponse.model_validate(metric, from_attributes=True)

    async def get_metrics(self, page: int, size: int) -> PagedMetrics:
        items, total = await self.repository.get_all(limit=size, offset=page * size)
        return PagedMetrics(
            items=[MetricResponse.model_validate(m, from_attributes=True) for m in items],
            total=total,
            page=page,
            size=size,
        )

    async def update_metric(self, metric_id: str, data: MetricUpdate) -> MetricResponse:
        await self.repository.get(metric_id)
        obj = Metrics(id=metric_id, **data.model_dump(exclude_none=True))
        updated = await self.repository.update(obj)
        return MetricResponse.model_validate(updated, from_attributes=True)

    async def delete_metric(self, metric_id: str) -> bool:
        return await self.repository.delete(metric_id)