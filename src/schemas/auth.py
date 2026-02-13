from pydantic import BaseModel

from src.models.users import Users
from src.schemas.users import UsersResponse


class AuthResponse(BaseModel):
    accessToken: str
    expiresIn: int
    user: UsersResponse