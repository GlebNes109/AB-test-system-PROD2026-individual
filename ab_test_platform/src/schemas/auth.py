from ab_test_platform.src.schemas.users import UsersResponse
from pydantic import BaseModel


class AuthResponse(BaseModel):
    accessToken: str
    expiresIn: int
    user: UsersResponse