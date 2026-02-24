import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class UserRole(Enum):
  ADMIN = "ADMIN"
  EXPERIMENTER = "EXPERIMENTER"
  APPROVER = "APPROVER"
  VIEWER = "VIEWER"


class Users(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True
    )

    email: str = Field(unique=True, index=True)
    password_hash: str
    role: UserRole = Field(default=UserRole.VIEWER)

    createdAt: datetime = Field(
      sa_column=Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
      )
    )