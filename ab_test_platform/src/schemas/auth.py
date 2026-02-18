from pydantic import BaseModel

from ab_test_platform.src.schemas.users import UsersResponse


class AuthResponse(BaseModel):
    accessToken: str
    expiresIn: int
    user: UsersResponse