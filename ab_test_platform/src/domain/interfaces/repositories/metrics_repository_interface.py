from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from ab_test_platform.src.models.metrics import Metrics


class MetricsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def get_by_key(self, key: str) -> Metrics:
        ...