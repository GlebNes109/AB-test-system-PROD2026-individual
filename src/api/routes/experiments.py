from fastapi import APIRouter, Depends, Query
from starlette import status

from src.api.deps import require_roles, get_feature_flag_service
from src.application.feature_flag_service import FeatureFlagService
from src.models.users import Users
from src.schemas.experiments import ExperimentsCreate

router = APIRouter()


@router.post(
    "",
    summary="Создание эксперимента",
    description="Создание нового эксперимента с версией 1",
    status_code=status.HTTP_201_CREATED,
)
async def create_new_experiment(
    new_expirement: ExperimentsCreate,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER"])),
    service: ExperimentService = Depends(get_experiments_service),
):
    raise NotImplementedError


@router.patch(
    "/{Id}",
    summary="Изменение эксперимента",
    description="Приводит к созданию новой версии эксперимента и увеличению текущей версии на 1",
    status_code=status.HTTP_200_OK,
)
async def update_experiment(
    Id: str,
    update_experiment: ExperimentsUpdate,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER"])),
    service: ExperimentsService = Depends(get_experiments_service),
):
    raise NotImplementedError

@router.get(
    "/{Id}",
    summary="Получение эксперимента",
    description="Получение эксперимента",
    status_code=status.HTTP_200_OK,
)
async def get_experiment(
    Id: str,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"])),
    service: ExperimentsService = Depends(get_experiments_service),
):
    raise NotImplementedError

@router.get(
    "/{Id}",
    summary="Получение всех экспериментов",
    description="Получение всех экспериментов с параметрами и фильтрами",
    status_code=status.HTTP_200_OK,
)
async def get_experiment(
    Id: str,
    page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100), status: str = Query(default=None),
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"])),
    service: ExperimentsService = Depends(get_experiments_service),
):
    raise NotImplementedError

@router.post(
    "/{Id}/submit",
    summary="Отправка эксперимента на ревью",
    description="Отправка эксперимента на ревью приводит к изменению статуса эксперимента. Это делает либо админ, либо создатель эксперимента",
    status_code=status.HTTP_200_OK,
)
async def send_to_review_experiment(
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER"])),
    service: ExperimentService = Depends(get_experiments_service),
):
    raise NotImplementedError # TODO проверка что эксперимент принадлежит тому кто его создал, если роль пользователя EXPERIMENTER
