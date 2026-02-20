from fastapi import APIRouter, Depends
from fastapi.params import Query
from starlette import status
from starlette.responses import JSONResponse, Response

from ab_test_platform.src.api.deps import require_roles, get_feature_flag_service
from ab_test_platform.src.application.feature_flag_service import FeatureFlagService
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.feature_flags import FeatureFlagCreate, FeatureFlagUpdateDefault

router = APIRouter()


@router.post(
    "",
    summary="Создание флага",
    description="Создание нового feature flag с ключом, типом и значением по умолчанию",
    status_code=status.HTTP_201_CREATED,
)
async def create_feature_flag(
    feature_flag: FeatureFlagCreate,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER"])),
    service: FeatureFlagService = Depends(get_feature_flag_service),
):
    return await service.create_flag(feature_flag, created_by=current_user.id)


@router.get(
    "",
    summary="Список флагов",
    description="Получение списка feature flags с пагинацией",
    status_code=status.HTTP_200_OK,
)
async def get_feature_flags(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    service: FeatureFlagService = Depends(get_feature_flag_service),
):
    return await service.get_flags(page, size)


@router.get(
    "/{key}",
    summary="Получение флага по ключу",
    description="Получение feature flag по уникальному ключу",
    status_code=status.HTTP_200_OK,
)
async def get_feature_flag_by_key(
    key: str,
    service: FeatureFlagService = Depends(get_feature_flag_service),
):
    return await service.get_flag_by_key(key)


@router.patch(
    "/{key}",
    summary="Обновление значения по умолчанию",
    description="Обновление только default_value у существующего feature flag",
    status_code=status.HTTP_200_OK,
)
async def update_feature_flag_default(
    key: str,
    update_data: FeatureFlagUpdateDefault,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER"])),
    service: FeatureFlagService = Depends(get_feature_flag_service),
):
    return await service.update_default_value(key, update_data)

@router.delete(
    "/{key}",
    summary="удаление по ключу",
    description="Удаление флага по ключу",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_feature_flag_default(
    key: str,
    update_data: FeatureFlagUpdateDefault,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER"])),
    service: FeatureFlagService = Depends(get_feature_flag_service),
):
    await service.delete(key)
    return Response(status_code=204)
