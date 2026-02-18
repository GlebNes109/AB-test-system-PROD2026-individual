from abc import abstractmethod
from datetime import datetime
from typing import Any, Protocol


class ReportsRepositoryInterface(Protocol):
    @abstractmethod
    async def compute_metric_summary(
        self,
        experiment_id: str,
        event_type: str,
        aggregation: str,
        payload_field: str | None,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        ...

    @abstractmethod
    async def compute_metric_timeseries(
        self,
        experiment_id: str,
        event_type: str,
        aggregation: str,
        payload_field: str | None,
        granularity: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        ...

    @abstractmethod
    async def count_subjects_per_variant(
        self,
        experiment_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        ...
