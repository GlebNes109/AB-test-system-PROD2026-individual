from typing import Optional

from fastapi import APIRouter, Depends, Query
from starlette import status

from ab_test_platform.src.api.deps import require_roles, get_experiment_service, check_experimenter_access
from ab_test_platform.src.application.experiment_service import ExperimentService
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.experiments import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    PagedExperiments,
)

router = APIRouter()

_ALL_ROLES = ["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"]
_EDITORS = ["ADMIN", "EXPERIMENTER"]


@router.post(
    "",
    summary="Создание эксперимента",
    description="Создаёт эксперимент и первую версию конфигурации (version=1, status=draft).",
    status_code=status.HTTP_201_CREATED,
    response_model=ExperimentResponse,
)
async def create_experiment(
    body: ExperimentCreate,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    return await service.create_experiment(body, current_user.id)


@router.get(
    "",
    summary="Список экспериментов",
    description="Возвращает постраничный список экспериментов. Можно фильтровать по статусу.",
    status_code=status.HTTP_200_OK,
    response_model=PagedExperiments,
)
async def list_experiments(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status", description="Фильтр по статусу"),
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: ExperimentService = Depends(get_experiment_service),
) -> PagedExperiments:
    return await service.get_experiments(page, size, status_filter)


@router.get(
    "/{experiment_id}",
    summary="Получение эксперимента",
    description="Возвращает эксперимент с данными текущей версии конфигурации.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def get_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    return await service.get_experiment(experiment_id)


@router.patch(
    "/{experiment_id}",
    summary="Изменение эксперимента",
    description=(
        "Частичное изменение конфигурации эксперимента. "
        "Создаёт новую версию (version+1). "
        "Поля, не переданные в запросе, копируются из текущей версии. "
        "Запрещено для экспериментов со статусом running или paused."
    ),
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def update_experiment(
    experiment_id: str,
    body: ExperimentUpdate,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
    _: None = Depends(check_experimenter_access),
) -> ExperimentResponse:
    return await service.update_experiment(experiment_id, body, current_user.id)


@router.post(
    "/{experiment_id}/submit",
    summary="Отправка на ревью",
    description="Переводит эксперимент из draft в review.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def submit_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
    _: None = Depends(check_experimenter_access)
) -> ExperimentResponse:
    return await service.submit_for_review(experiment_id, current_user.id)


@router.post(
    "/{experiment_id}/start",
    summary="Запуск эксперимента",
    description="Переводит эксперимент из approved в running. Проверяет отсутствие другого активного эксперимента на том же флаге.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,

)
async def start_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
    _: None = Depends(check_experimenter_access)
) -> ExperimentResponse:
    return await service.start_experiment(experiment_id, current_user.id)


@router.post(
    "/{experiment_id}/pause",
    summary="Пауза эксперимента",
    description="Переводит эксперимент из running в paused.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def pause_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
    _: None = Depends(check_experimenter_access)
) -> ExperimentResponse:
    return await service.pause_experiment(experiment_id, current_user.id)


@router.post(
    "/{experiment_id}/resume",
    summary="Возобновление эксперимента",
    description="Переводит эксперимент из paused в running.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def resume_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    return await service.resume_experiment(experiment_id, current_user.id)


@router.post(
    "/{experiment_id}/finish",
    summary="Завершение эксперимента",
    description="Переводит эксперимент из running или paused в finished.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def finish_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
    _: None = Depends(check_experimenter_access)
) -> ExperimentResponse:
    return await service.finish_experiment(experiment_id, current_user.id)


@router.post(
    "/{experiment_id}/archive",
    summary="Архивирование эксперимента",
    description="Переводит эксперимент из finished в archived.",
    status_code=status.HTTP_200_OK,
    response_model=ExperimentResponse,
)
async def archive_experiment(
    experiment_id: str,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: ExperimentService = Depends(get_experiment_service),
    _: None = Depends(check_experimenter_access)
) -> ExperimentResponse:
    return await service.archive_experiment(experiment_id, current_user.id)
