from abc import abstractmethod
from typing import Protocol


class HashCreatorInterface(Protocol):
    @abstractmethod
    async def create_hash(self, password):
        ...