from abc import abstractmethod
from typing import Protocol


class TokenCreatorInterface(Protocol):
    @abstractmethod
    async def create_access_token(self, user_id: str) -> tuple[str, int]:
        ...

    @abstractmethod
    async def verify_access_token(self, token: str) -> str:
        ...