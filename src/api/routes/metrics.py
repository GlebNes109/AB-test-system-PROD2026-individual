from fastapi import APIRouter, Depends, Query
from starlette import status

from src.api.deps import require_roles, get_metrics_service
from src.application.metrics_service import MetricsService
from src.schemas.metrics import MetricCreate, MetricUpdate, MetricResponse, PagedMetrics

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
    "/{metric_id}",
    summary="Получение метрики",
    response_model=MetricResponse,
)
async def get_metric(
    metric_id: str,
    current_user=Depends(require_roles(["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"])),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.get_metric(metric_id)


@router.patch(
    "/{metric_id}",
    summary="Обновление метрики",
    response_model=MetricResponse,
)
async def update_metric(
    metric_id: str,
    body: MetricUpdate,
    current_user=Depends(require_roles(["ADMIN"])),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.update_metric(metric_id, body)


@router.delete(
    "/{metric_id}",
    summary="Удаление метрики",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_metric(
    metric_id: str,
    current_user=Depends(require_roles(["ADMIN"])),
    service: MetricsService = Depends(get_metrics_service),
):
    await service.delete_metric(metric_id)