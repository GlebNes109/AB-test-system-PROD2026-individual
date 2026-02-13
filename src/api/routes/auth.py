from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from starlette import status

from src.api.deps import get_user_service
from src.schemas.users import UsersLogin, UsersCreate
from src.application.user_service import UsersService

router = APIRouter()


@router.post("/login", summary="Вход по логину/паролю", description="Вход по кредам и получение токена")
async def sign_in_user(user: UsersLogin, service: UsersService = Depends(get_user_service)):
    return await service.sign_in_user(user)

"""@router.post("/register", summary="Регистрация", description="Первоначальная регистрация на платформе", status_code=status.HTTP_201_CREATED)
async def register_user(new_user: UsersCreate, service: UsersService = Depends(get_user_service)):
    return await service.register(new_user)"""
