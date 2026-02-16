from abc import abstractmethod
from typing import Optional, Protocol

from src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from src.models.experiments import ExperimentStatus
from src.schemas.experiments import ExperimentCreate, ExperimentUpdate, ExperimentResponse, PagedExperiments


class ExperimentsRepositoryInterface(Protocol):
    @abstractmethod
    async def create_experiment(self, data: ExperimentCreate, created_by: str) -> ExperimentResponse:
        ...

    @abstractmethod
    async def get(self, experiment_id: str) -> ExperimentResponse:
        ...

    @abstractmethod
    async def get_all_experiments(
        self,
        page: int,
        size: int,
        status: Optional[ExperimentStatus] = None,
    ) -> PagedExperiments:
        ...

    @abstractmethod
    async def update_experiment(
        self, experiment_id: str, data: ExperimentUpdate, modified_by: str
    ) -> ExperimentResponse:
        ...

    @abstractmethod
    async def transition_status(
        self, experiment_id: str, new_status: ExperimentStatus
    ) -> ExperimentResponse:
        ...

    @abstractmethod
    async def has_active_experiment_for_flag(self, feature_flag_id: str) -> bool:
        ...