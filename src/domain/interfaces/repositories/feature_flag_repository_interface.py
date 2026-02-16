from abc import abstractmethod
from typing import Protocol



class FeatureFlagRepositoryInterface(Protocol):
    @abstractmethod
    async def get_by_key(self, key: str):
        ...

    @abstractmethod
    async def update_default_value(self, key: str, default_value: str):
        ...