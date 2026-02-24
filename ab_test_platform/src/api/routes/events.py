from ab_test_platform.src.api.deps import get_events_service, require_roles
from ab_test_platform.src.application.events_sevice import EventsService
from ab_test_platform.src.schemas.events import (
    EventsBatchRequest,
    EventsBatchResponse,
    EventTypesCreate,
    EventTypesResponse,
    PagedEventTypes,
)
from fastapi import APIRouter, Depends, Query
from starlette import status

router = APIRouter()

_ALL_ROLES = ["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"]


@router.post(
    "/types",
    summary="Создание типа события в каталоге",
    description="Создает тип события, доступно админу",
    status_code=status.HTTP_201_CREATED,
    response_model=EventTypesResponse,
)
async def create_event_type(
    body: EventTypesCreate,
    current_user=Depends(require_roles(["ADMIN"])),
    service: EventsService = Depends(get_events_service),
):
    return await service.create_event_type(body)


@router.get(
    "/types",
    summary="Список типов событий",
    description="Возвращает постраничный список типов событий из каталога.",
    status_code=status.HTTP_200_OK,
    response_model=PagedEventTypes,
)
async def get_event_types(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_roles(_ALL_ROLES)),
    service: EventsService = Depends(get_events_service),
):
    return await service.get_event_types(page, size)


@router.post(
    "/batch",
    summary="Массовый прием событий",
    description="Принимает список событий и возвращает мульти-статус по каждому",
    status_code=status.HTTP_207_MULTI_STATUS,
    response_model=EventsBatchResponse,
)
async def receive_events_batch(
    body: EventsBatchRequest,
    service: EventsService = Depends(get_events_service),
):
    return await service.process_batch(body.events)
