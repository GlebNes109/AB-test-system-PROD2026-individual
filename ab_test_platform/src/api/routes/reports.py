from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ab_test_platform.src.api.deps import require_roles, get_reports_service
from ab_test_platform.src.application.reports_service import ReportsService
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.reports import (
    ExperimentReport,
    ExperimentTimeseriesReport,
    Granularity,
)

router = APIRouter()

_ALL_ROLES = ["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"]


@router.get(
    "/{experiment_id}/reports",
    summary="Получение отчёта по эксперименту",
    response_model=ExperimentReport,
)
async def get_report(
    experiment_id: str,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: ReportsService = Depends(get_reports_service),
) -> ExperimentReport:
    return await service.get_summary_report(experiment_id, date_from, date_to)


@router.get(
    "/{experiment_id}/reports/timeseries",
    summary="Получение динамики эксперимента",
    response_model=ExperimentTimeseriesReport,
)
async def get_timeseries_report(
    experiment_id: str,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    granularity: Granularity = Query(Granularity.DAY),
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: ReportsService = Depends(get_reports_service),
) -> ExperimentTimeseriesReport:
    return await service.get_timeseries_report(experiment_id, date_from, date_to, granularity)
