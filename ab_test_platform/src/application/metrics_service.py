from ab_test_platform.src.domain.interfaces.repositories.events_repository_interface import EventsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.metrics_repository_interface import MetricsRepositoryInterface
from ab_test_platform.src.models.metrics import Metrics
from ab_test_platform.src.schemas.metrics import MetricCreate, MetricUpdate, MetricResponse, PagedMetrics


class MetricsService:
    def __init__(self, repository: MetricsRepositoryInterface, events_repository: EventsRepositoryInterface):
        self.repository = repository
        self.events_repository = events_repository

    async def create_metric(self, data: MetricCreate) -> MetricResponse:
        await self.events_repository.get_type_by_key(data.event_type)
        if data.denominator_event_type is not None:
            await self.events_repository.get_type_by_key(data.denominator_event_type)
        if data.prerequisite_event_type is not None:
            await self.events_repository.get_type_by_key(data.prerequisite_event_type)

        metric = await self.repository.create(Metrics(**data.model_dump()))
        return MetricResponse.model_validate(metric, from_attributes=True)

    async def get_metric(self, metric_key: str) -> MetricResponse:
        metric = await self.repository.get_by_key(metric_key)
        return MetricResponse.model_validate(metric, from_attributes=True)

    async def get_metrics(self, page: int, size: int) -> PagedMetrics:
        items, total = await self.repository.get_all(limit=size, offset=page * size)
        return PagedMetrics(
            items=[MetricResponse.model_validate(m, from_attributes=True) for m in items],
            total=total,
            page=page,
            size=size,
        )

    async def update_metric(self, metric_key: str, data: MetricUpdate) -> MetricResponse:
        if data.event_type is not None:
            await self.events_repository.get_type_by_key(data.event_type)
        if data.denominator_event_type is not None:
            await self.events_repository.get_type_by_key(data.denominator_event_type)
        if data.prerequisite_event_type is not None:
            await self.events_repository.get_type_by_key(data.prerequisite_event_type)

        metric = await self.repository.get_by_key(metric_key)
        obj = Metrics(id=metric.id, **data.model_dump(exclude_none=True))
        updated = await self.repository.update(obj)
        return MetricResponse.model_validate(updated, from_attributes=True)

    async def delete_metric(self, metric_key: str) -> bool:
        metric = await self.repository.get_by_key(metric_key)
        return await self.repository.delete(metric.id)