import uuid
from datetime import UTC, datetime
from enum import Enum

from ab_test_platform.src.domain.exceptions import UnsupportableContentError
from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class FlagType(Enum):
    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"


def validate_value_for_flag_type(
    value: object, flag_type: FlagType, field_name: str = "value"
) -> str:
    str_val = str(value)

    if flag_type == FlagType.BOOL:
        if str_val.lower() not in ("true", "false"):
            raise UnsupportableContentError(
                f"{field_name}: expected bool ('true'/'false'), got '{value}'"
            )

    elif flag_type == FlagType.NUMBER:
        try:
            float(str_val)
        except (ValueError, TypeError):
            raise UnsupportableContentError(
                f"{field_name}: expected a number, got '{value}'"
            ) from None

    return str_val


class FeatureFlags(SQLModel, table=True):
    __tablename__ = "feature_flags"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    key: str = Field(unique=True, index=True)
    type: FlagType
    default_value: str
    description: str | None = Field(default=None)
    created_by: str | None = Field(default=None)

    createdAt: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
        )
    )
