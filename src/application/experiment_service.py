from typing import Optional

from src.core.exceptions import (
    BadRequestError,
    ConflictError,
    EntityNotFoundError,
    UnsupportableContentError, AccessDeniedError,
)
from src.infra.database.repositories.experiment_repository import ExperimentsRepository
from src.infra.database.repositories.feature_flag_repository import FeatureFlagRepository
from src.models.experiments import ExperimentStatus, ALLOWED_TRANSITIONS, FROZEN_STATUSES
from src.models.feature_flags import validate_value_for_flag_type
from src.schemas.experiments import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    PagedExperiments,
)


class ExperimentService:
    def __init__(self, repository: ExperimentsRepository, feature_flags_repository: FeatureFlagRepository):
        self.repository = repository
        self.feature_flags_repository = feature_flags_repository

    async def check_experimenter_create_this_experiment(self, experiment_id, experimenter_id):
        experiment = await self.repository.get(experiment_id)
        if not experiment.created_by == experimenter_id:
            raise AccessDeniedError("This experiment created by another experimenter")

    async def _validate_variants_type(self, feature_flag_id: str, variants):
        # проверка что тип вариантов совпадает с типом в эксперименте
        flag = await self.feature_flags_repository.get(feature_flag_id)
        for var in variants:
            validate_value_for_flag_type(var.value, flag.type, f"variant '{var.name}'")

    async def create_experiment(
        self, data: ExperimentCreate, created_by: str
    ) -> ExperimentResponse:
        try:
            await self.feature_flags_repository.get(data.feature_flag_id)
        except EntityNotFoundError:
            raise EntityNotFoundError(f"Feature flag '{data.feature_flag_id}' not found")

        await self._validate_variants_type(data.feature_flag_id, data.variants)

        return await self.repository.create_experiment(data, created_by)

    async def get_experiment(self, experiment_id: str) -> ExperimentResponse:
        return await self.repository.get(experiment_id)

    async def get_experiments(
        self,
        page: int,
        size: int,
        status: Optional[str] = None,
    ) -> PagedExperiments:
        status_filter: Optional[ExperimentStatus] = None
        if status is not None:
            try:
                status_filter = ExperimentStatus(status)
            except ValueError:
                raise BadRequestError(
                    f"Invalid status value '{status}'. "
                    f"Allowed: {[s.value for s in ExperimentStatus]}"
                )
        return await self.repository.get_all_experiments(page, size, status_filter)

    async def update_experiment(
        self, experiment_id: str, data: ExperimentUpdate, modified_by: str
    ) -> ExperimentResponse:
        experiment = await self.repository.get(experiment_id)

        if experiment.status in FROZEN_STATUSES:
            raise ConflictError(
                f"Cannot edit experiment in status '{experiment.status.value}'. "
                "Config is frozen while the experiment is running or paused."
            )

        if experiment.status not in (ExperimentStatus.DRAFT, ExperimentStatus.REJECTED):
            raise ConflictError(
                f"Cannot edit experiment in status '{experiment.status.value}'. "
                "Only DRAFT and REJECTED experiments can be edited."
            )

        if data.variants is not None:
            await self._validate_variants_type(experiment.feature_flag_id, data.variants)

        return await self.repository.update_experiment(experiment_id, data, modified_by)

    async def _transition(
        self,
        experiment_id: str,
        target_status: ExperimentStatus,
        actor_id: str,
    ) -> ExperimentResponse:
        experiment = await self.repository.get(experiment_id)
        current_status = experiment.status

        if target_status not in ALLOWED_TRANSITIONS.get(current_status, []):
            raise ConflictError(
                f"Cannot transition from '{current_status.value}' to '{target_status.value}'"
            )
        return await self.repository.transition_status(experiment_id, target_status)

    async def submit_for_review(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """DRAFT -> REVIEW"""
        return await self._transition(experiment_id, ExperimentStatus.REVIEW, actor_id)

    async def start_experiment(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """APPROVED -> RUNNING. Базовая проверка на коллизию экспериментов"""
        experiment = await self.repository.get(experiment_id)

        if await self.repository.has_active_experiment_for_flag(experiment.feature_flag_id):
            raise ConflictError(
                "Another experiment is already RUNNING or PAUSED for this feature flag"
            )

        return await self._transition(experiment_id, ExperimentStatus.RUNNING, actor_id)

    async def pause_experiment(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """RUNNING -> PAUSED"""
        return await self._transition(experiment_id, ExperimentStatus.PAUSED, actor_id)

    async def resume_experiment(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """PAUSED ->  RUNNING"""
        return await self._transition(experiment_id, ExperimentStatus.RUNNING, actor_id)

    async def finish_experiment(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """RUNNING | PAUSED -> FINISHED"""
        return await self._transition(experiment_id, ExperimentStatus.FINISHED, actor_id)

    async def archive_experiment(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """FINISHED -> ARCHIVED"""
        return await self._transition(experiment_id, ExperimentStatus.ARCHIVED, actor_id)