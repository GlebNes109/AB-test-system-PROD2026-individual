from datetime import datetime
from typing import Any

from ab_test_platform.src.core.db_sql import SQL_REFRESH_MV
from ab_test_platform.src.domain.interfaces.repositories.reports_repository_interface import (
    ReportsRepositoryInterface,
)
from ab_test_platform.src.models.decisions import Decisions
from sqlalchemy import distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession


class ReportsRepository(ReportsRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_metric_summary(
        self,
        experiment_id: str,
        metric_key: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        result = await self.session.execute(
            text(
                "SELECT * FROM fn_metric_summary("
                ":experiment_id, :metric_key, :date_from, :date_to)"
            ),
            {
                "experiment_id": experiment_id,
                "metric_key": metric_key,
                "date_from": date_from,
                "date_to": date_to,
            },
        )
        return result.all()

    async def compute_metric_timeseries(
        self,
        experiment_id: str,
        metric_key: str,
        granularity: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Any]:
        result = await self.session.execute(
            text(
                "SELECT * FROM fn_metric_timeseries("
                ":experiment_id, :metric_key, :date_from, :date_to, :granularity)"
            ),
            {
                "experiment_id": experiment_id,
                "metric_key": metric_key,
                "date_from": date_from,
                "date_to": date_to,
                "granularity": granularity,
            },
        )
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

    async def refresh_mv(self) -> None:
        await self.session.execute(text(SQL_REFRESH_MV))
        await self.session.commit()
