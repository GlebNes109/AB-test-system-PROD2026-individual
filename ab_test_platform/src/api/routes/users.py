from fastapi import APIRouter, Depends
from fastapi.params import Query
from starlette import status

from ab_test_platform.src.api.deps import get_user_service, require_roles

from ab_test_platform.src.schemas.users import UsersCreate, UsersUpdate
from ab_test_platform.src.application.user_service import UsersService
from ab_test_platform.src.models.users import Users

router = APIRouter()

@router.post("", summary="Создание пользователя", description="Создание пользователя", status_code=status.HTTP_201_CREATED)
async def create_user(user: UsersCreate, current_user: Users = Depends(require_roles(["ADMIN"])), service: UsersService = Depends(get_user_service)):
    return await service.create_user(user)

@router.get("/{UserId}", summary="Получение пользователя", description="Создание пользователя")
async def get_user(UserId: str, service: UsersService = Depends(get_user_service)):
    return await service.get_user(UserId)

@router.patch("/{UserId}", summary="Изменение пользователя", description="Создание пользователя")
async def update_user(UserId: str, user: UsersUpdate, current_user: Users = Depends(require_roles(["ADMIN"])), service: UsersService = Depends(get_user_service)):
    return await service.update_user(user, UserId)

@router.get("", summary="Список пользователей", description="Доступно всем")
async def get_users(page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100), service: UsersService = Depends(get_user_service)):
    return await service.get_users(page, size)




