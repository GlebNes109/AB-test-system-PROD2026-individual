
from ab_test_platform.src.models.users import UserRole
from pydantic import BaseModel, EmailStr, Field


class UsersCreate(BaseModel):
  email: EmailStr = Field(max_length=254)
  password: str = Field(min_length=8, max_length=72)
  role: UserRole | None

class UsersUpdate(BaseModel):
  email: EmailStr | None = Field(default=None, max_length=254)
  password: str | None = Field(default=None, min_length=8, max_length=72)
  role: UserRole | None = Field(default=None)

class UsersLogin(BaseModel):
  email: EmailStr = Field(max_length=254)
  password: str = Field(min_length=8, max_length=72)

class UsersResponse(BaseModel):
  id: str
  email: str
  role: UserRole

class PagedUsers(BaseModel):
  items: list[UsersResponse]
  total: int
  page: int
  size: int