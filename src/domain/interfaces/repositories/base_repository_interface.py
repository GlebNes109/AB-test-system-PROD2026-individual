from enum import Enum
from typing import Any, Generic, TypeVar, Protocol
from abc import abstractmethod

from src.models.models import ModelType, ReadModelType

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class BaseRepositoryInterface(Protocol):
    @abstractmethod
    async def get(self, id: Any) -> ReadModelType:
        ...

    @abstractmethod
    async def get_all(
        self,
        limit: int,
        offset: int,
        order_by: str | None = None,
        order: Any = None,
    ) -> tuple[list[ReadModelType], int]:
        ...

    @abstractmethod
    async def create(self, obj: ModelType) -> ReadModelType:
        ...

    @abstractmethod
    async def update(self, obj: ModelType) -> ReadModelType:
        ...

    @abstractmethod
    async def delete(self, id: Any) -> bool:
        ...


