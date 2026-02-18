from typing import Optional

from pydantic import BaseModel, Field, EmailStr

from ab_test_platform.src.models.users import UserRole


class UsersCreate(BaseModel):
  email: EmailStr = Field(max_length=254)
  password: str = Field(min_length=8, max_length=72)
  role: Optional[UserRole]

class UsersUpdate(BaseModel):
  email: Optional[EmailStr] = Field(default=None, max_length=254)
  password: Optional[str] = Field(default=None, min_length=8, max_length=72)
  role: Optional[UserRole] = Field(default=None)

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