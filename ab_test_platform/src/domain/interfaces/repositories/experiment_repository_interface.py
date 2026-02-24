from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import (
    BaseRepositoryInterface,
)
from ab_test_platform.src.models.experiments import ExperimentResult, ExperimentStatus
from ab_test_platform.src.schemas.experiments import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentUpdate,
    PagedExperiments,
)


class ExperimentsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def create_experiment(self, data: ExperimentCreate, created_by: str, flag, metric_id_map: dict[str, str] = None) -> ExperimentResponse:
        ...

    @abstractmethod
    async def get(self, experiment_id: str) -> ExperimentResponse:
        ...

    @abstractmethod
    async def get_all_experiments(
        self,
        page: int,
        size: int,
        status: ExperimentStatus | None = None,
    ) -> PagedExperiments:
        ...

    @abstractmethod
    async def update_experiment(
        self, experiment_id: str, data: ExperimentUpdate, modified_by: str, flag_default_value: str | None = None, metric_id_map: dict[str, str] | None = None
    ) -> ExperimentResponse:
        ...

    @abstractmethod
    async def transition_status(
        self,
        experiment_id: str,
        new_status: ExperimentStatus,
        result: ExperimentResult | None = None,
        result_description: str | None = None,
    ) -> ExperimentResponse:
        ...

    @abstractmethod
    async def has_active_experiment_for_flag(self, feature_flag_id: str, exclude_experiment_id: str | None = None) -> bool:
        ...

    @abstractmethod
    async def get_active_experiment_for_flag(self, feature_flag_id: str) -> ExperimentResponse | None:
        ...

    @abstractmethod
    async def get_running_experiments(self) -> list[ExperimentResponse]:
        ...