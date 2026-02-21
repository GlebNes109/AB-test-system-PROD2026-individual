from abc import abstractmethod
from datetime import datetime
from typing import Any, Protocol


class ReportsRepositoryInterface(Protocol):
    @abstractmethod
    async def compute_metric_summary(
        self,
        experiment_id: str,
        metric_key: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        """
        Вызывает fn_metric_summary. Возвращает строки с полями:
        variant_id, variant_name, is_control, value, value_num, value_denom
        """
        ...

    @abstractmethod
    async def compute_metric_timeseries(
        self,
        experiment_id: str,
        metric_key: str,
        granularity: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        """
        Вызывает fn_metric_timeseries. Возвращает строки с полями:
        variant_id, variant_name, is_control, bucket_start, bucket_end, value
        """
        ...

    @abstractmethod
    async def count_subjects_per_variant(
        self,
        experiment_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        ...

    @abstractmethod
    async def refresh_mv(self) -> None:
        """REFRESH MATERIALIZED VIEW mv_events_enriched."""
        ...
