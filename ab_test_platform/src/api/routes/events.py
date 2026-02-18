from fastapi import APIRouter, Depends
from starlette import status

from ab_test_platform.src.api.deps import require_roles, get_events_service
from ab_test_platform.src.application.events_sevice import EventsService
from ab_test_platform.src.schemas.events import EventTypesCreate, EventTypesResponse, EventsBatchRequest, EventsBatchResponse

router = APIRouter()


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