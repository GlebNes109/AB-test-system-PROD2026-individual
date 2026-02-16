from abc import abstractmethod
from typing import Protocol

from src.models.users import Users


class UserRepositoryInterface(Protocol):
    @abstractmethod
    async def get_by_email(self, email: str) -> Users:
        ...