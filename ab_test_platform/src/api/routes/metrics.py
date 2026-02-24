from ab_test_platform.src.api.deps import get_metrics_service, require_roles
from ab_test_platform.src.application.metrics_service import MetricsService
from ab_test_platform.src.schemas.metrics import (
    MetricCreate,
    MetricResponse,
    MetricUpdate,
    PagedMetrics,
)
from fastapi import APIRouter, Depends, Query
from starlette import status

router = APIRouter()


@router.post(
    "",
    summary="Создание метрики в каталоге",
    status_code=status.HTTP_201_CREATED,
    response_model=MetricResponse,
)
async def create_metric(
    body: MetricCreate,
    current_user=Depends(require_roles(["ADMIN"])),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.create_metric(body)


@router.get(
    "",
    summary="Список метрик",
    response_model=PagedMetrics,
)
async def get_metrics(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_roles(["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"])),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.get_metrics(page, size)


@router.get(
    "/{metric_key}",
    summary="Получение метрики",
    response_model=MetricResponse,
)
async def get_metric(
    metric_key: str,
    current_user=Depends(require_roles(["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"])),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.get_metric(metric_key)


@router.patch(
    "/{metric_key}",
    summary="Обновление метрики",
    response_model=MetricResponse,
)
async def update_metric(
    metric_key: str,
    body: MetricUpdate,
    current_user=Depends(require_roles(["ADMIN"])),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.update_metric(metric_key, body)


@router.delete(
    "/{metric_key}",
    summary="Удаление метрики",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_metric(
    metric_key: str,
    current_user=Depends(require_roles(["ADMIN"])),
    service: MetricsService = Depends(get_metrics_service),
):
    await service.delete_metric(metric_key)
