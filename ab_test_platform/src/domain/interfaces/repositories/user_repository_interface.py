from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import (
    BaseRepositoryInterface,
)
from ab_test_platform.src.models.users import Users


class UserRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def get_by_email(self, email: str) -> Users: ...
