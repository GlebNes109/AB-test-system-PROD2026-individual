import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Text
from sqlmodel import SQLModel, Field


class FlagType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"


def validate_value_for_flag_type(value: object, flag_type: FlagType, field_name: str = "value") -> str:
    """Проверка, что фактический тип дефолтного значения или варианта совпадает с указанным типом"""
    str_val = str(value)

    if flag_type == FlagType.BOOL:
        if str_val.lower() not in ("true", "false"):
            raise ValueError(
                f"{field_name}: expected bool ('true'/'false'), got '{value}'"
            )

    elif flag_type == FlagType.NUMBER:
        try:
            float(str_val)
        except (ValueError, TypeError):
            raise ValueError(
                f"{field_name}: expected a number, got '{value}'"
            )

    return str_val


class FeatureFlags(SQLModel, table=True):
    __tablename__ = "feature_flags"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True
    )
    key: str = Field(unique=True, index=True)
    type: FlagType
    default_value: str
    description: str | None = Field(default=None)
    created_by: str | None = Field(default=None)

    createdAt: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )
