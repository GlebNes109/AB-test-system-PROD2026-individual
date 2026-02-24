from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import (
    BaseRepositoryInterface,
)
from ab_test_platform.src.models.decisions import Decisions


class DecisionsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def get_decision_by_feature_flag_id(self, feature_flag_id: str) -> Decisions:
        ...

    @abstractmethod
    async def get_decision_by_subject_and_experiment(self, subject_id: str, experiment_id: str) -> Decisions:
        ...

    @abstractmethod
    async def count_active_experiments_by_subject(self, subject_id: str) -> int:
        ...

    @abstractmethod
    async def get_last_decision_by_subject(self, subject_id: str) -> Decisions | None:
        ...