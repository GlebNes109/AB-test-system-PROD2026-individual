from datetime import datetime
from typing import Any

from sqlalchemy import select, func, cast, Float, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.repositories.reports_repository_interface import ReportsRepositoryInterface
from src.models.decisions import Decisions
from src.models.events import Events, EventTypes


class ReportsRepository(ReportsRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _build_agg_expr(self, aggregation: str, payload_field: str | None):
        if aggregation == "COUNT":
            return func.count(Events.id)
        elif aggregation == "COUNT_UNIQUE":
            return func.count(distinct(Events.subject_id))
        elif aggregation == "SUM":
            return func.sum(cast(Events.payload[payload_field].as_string(), Float))
        elif aggregation == "AVG":
            return func.avg(cast(Events.payload[payload_field].as_string(), Float))
        else:
            return func.count(Events.id)

    def _base_query(
        self,
        experiment_id: str,
        event_type: str,
        date_from: datetime,
        date_to: datetime,
    ):
        return (
            select(Decisions.variant_id)
            .select_from(Events)
            .join(EventTypes, Events.event_type_id == EventTypes.id)
            .join(Decisions, Events.decision_id == Decisions.id)
            .where(
                Decisions.experiment_id == experiment_id,
                EventTypes.type == event_type,
                Events.occurred_at >= date_from,
                Events.occurred_at <= date_to,
            )
        )

    async def compute_metric_summary(
        self,
        experiment_id: str,
        event_type: str,
        aggregation: str,
        payload_field: str | None,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        agg = self._build_agg_expr(aggregation, payload_field)
        stmt = (
            self._base_query(experiment_id, event_type, date_from, date_to)
            .add_columns(agg.label("value"))
            .group_by(Decisions.variant_id)
        )
        result = await self.session.execute(stmt)
        return result.all()

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
        agg = self._build_agg_expr(aggregation, payload_field)
        bucket = func.date_trunc(granularity, Events.occurred_at).label("bucket")
        stmt = (
            self._base_query(experiment_id, event_type, date_from, date_to)
            .add_columns(bucket, agg.label("value"))
            .group_by(Decisions.variant_id, bucket)
            .order_by(bucket)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def count_subjects_per_variant(
        self,
        experiment_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        stmt = (
            select(
                Decisions.variant_id,
                func.count(distinct(Decisions.subject_id)).label("count"),
            )
            .where(
                Decisions.experiment_id == experiment_id,
                Decisions.createdAt >= date_from,
                Decisions.createdAt <= date_to,
            )
            .group_by(Decisions.variant_id)
        )
        result = await self.session.execute(stmt)
        return result.all()
