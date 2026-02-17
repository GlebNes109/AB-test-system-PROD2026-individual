from abc import abstractmethod
from typing import Protocol

from src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from src.models.metrics import Metrics


class MetricsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def get_by_key(self, key: str) -> Metrics:
        ...