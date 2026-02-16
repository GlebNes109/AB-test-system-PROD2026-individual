from abc import abstractmethod
from typing import Protocol

from src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from src.models.users import Users


class UserRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def get_by_email(self, email: str) -> Users:
        ...