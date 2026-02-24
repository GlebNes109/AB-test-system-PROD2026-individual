from abc import abstractmethod
from typing import Any, Protocol

from ab_test_platform.src.models.experiments import ExperimentResult
from ab_test_platform.src.models.learnings import Learnings


class LearningsRepositoryInterface(Protocol):
    @abstractmethod
    async def create(self, learning: Learnings) -> Learnings: ...

    @abstractmethod
    async def get(self, learning_id: str) -> Learnings: ...

    @abstractmethod
    async def get_by_experiment_id(self, experiment_id: str) -> Learnings: ...

    @abstractmethod
    async def update(self, learning_id: str, values: dict) -> Learnings: ...

    @abstractmethod
    async def search(
        self,
        query: str | None,
        feature_flag_key: str | None,
        result: ExperimentResult | None,
        tags: list[str] | None,
        primary_metric_key: str | None,
        platform: str | None,
        created_by: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Any], int]: ...

    @abstractmethod
    async def find_similar(
        self,
        experiment_id: str,
        limit: int,
    ) -> list[Any]: ...
