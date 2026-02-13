from typing import Optional

from pydantic import BaseModel, Field, EmailStr

from src.models.users import UserRole


class UsersCreate(BaseModel):
  email: EmailStr = Field(max_length=254)
  password: str = Field(min_length=8, max_length=72)
  role: Optional[UserRole]

class UsersUpdate(BaseModel):
  email: Optional[EmailStr] = Field(max_length=254)
  password: Optional[str] = Field(min_length=8, max_length=72)
  role: Optional[UserRole]

class UsersLogin(BaseModel):
  email: EmailStr = Field(max_length=254)
  password: str = Field(min_length=8, max_length=72)

class UsersResponse(BaseModel):
  id: str
  email: str

class PagedUsers(BaseModel):
  items: list[UsersResponse]
  total: int
  page: int
  size: int