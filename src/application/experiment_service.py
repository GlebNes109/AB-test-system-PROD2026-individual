from typing import Optional

from src.domain.exceptions import BadRequestError, ConflictError, EntityNotFoundError, AccessDeniedError, UnsupportableContentError

from src.domain.interfaces.dsl_parser import DslParserInterface
from src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from src.domain.interfaces.repositories.feature_flag_repository_interface import FeatureFlagRepositoryInterface
from src.models.experiments import ExperimentStatus, ALLOWED_TRANSITIONS, FROZEN_STATUSES
from src.models.feature_flags import validate_value_for_flag_type
from src.models.users import UserRole
from src.schemas.experiments import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    PagedExperiments,
)


class ExperimentService:
    def __init__(self, repository: ExperimentsRepositoryInterface, feature_flags_repository: FeatureFlagRepositoryInterface, parser: DslParserInterface):
        self.repository = repository
        self.feature_flags_repository = feature_flags_repository
        self.parser = parser

    async def check_experimenter_create_this_experiment(self, experiment_id, user):
        experiment = await self.repository.get(experiment_id)
        if not experiment.created_by == user.id and user.role != UserRole.ADMIN:
            raise AccessDeniedError("This experiment created by another experimenter")

    async def _validate_variants_type(self, feature_flag_id: str, variants):
        # проверка что тип вариантов совпадает с типом в эксперименте
        flag = await self.feature_flags_repository.get(feature_flag_id)
        for var in variants:
            validate_value_for_flag_type(var.value, flag.type, f"variant '{var.name}'")

    async def create_experiment(
        self, data: ExperimentCreate, created_by: str
    ) -> ExperimentResponse:

        if data.targeting_rule is not None and not self.parser.validate(data.targeting_rule):
            raise UnsupportableContentError(f"Unsupportable targeting rule {data.targeting_rule}")

        try:
            flag = await self.feature_flags_repository.get(data.feature_flag_id)
        except EntityNotFoundError:
            raise EntityNotFoundError(f"Feature flag '{data.feature_flag_id}' not found")

        await self._validate_variants_type(data.feature_flag_id, data.variants)

        return await self.repository.create_experiment(data, created_by, flag.default_value)

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

        if data.targeting_rule is not None and not self.parser.validate(data.targeting_rule):
            raise UnsupportableContentError(f"Unsupportable targeting rule {data.targeting_rule}")

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

            effective_audience = data.audience_percentage if data.audience_percentage is not None else experiment.audience_percentage
            total_weight = sum(var.weight for var in data.variants)
            if total_weight != effective_audience:
                raise UnsupportableContentError(
                    f"Sum of variant weights ({total_weight}) must equal audience_percentage ({effective_audience})"
                )

        flag = await self.feature_flags_repository.get(experiment.feature_flag_id)
        return await self.repository.update_experiment(experiment_id, data, modified_by, flag.default_value)

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