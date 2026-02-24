
from ab_test_platform.src.domain.exceptions import (
    AccessDeniedError,
    BadRequestError,
    ConflictError,
    EntityNotFoundError,
    UnsupportableContentError,
)
from ab_test_platform.src.domain.interfaces.dsl_parser import DslParserInterface
from ab_test_platform.src.domain.interfaces.repositories.experiment_repository_interface import (
    ExperimentsRepositoryInterface,
)
from ab_test_platform.src.domain.interfaces.repositories.feature_flag_repository_interface import (
    FeatureFlagRepositoryInterface,
)
from ab_test_platform.src.domain.interfaces.repositories.metrics_repository_interface import (
    MetricsRepositoryInterface,
)
from ab_test_platform.src.models.experiments import (
    ALLOWED_TRANSITIONS,
    FROZEN_STATUSES,
    ExperimentStatus,
)
from ab_test_platform.src.models.feature_flags import validate_value_for_flag_type
from ab_test_platform.src.models.users import UserRole
from ab_test_platform.src.schemas.experiments import (
    ExperimentCreate,
    ExperimentFinish,
    ExperimentResponse,
    ExperimentUpdate,
    PagedExperiments,
)
from ab_test_platform.src.schemas.metrics import ExperimentMetricBind


class ExperimentService:
    def __init__(
        self,
        repository: ExperimentsRepositoryInterface,
        feature_flags_repository: FeatureFlagRepositoryInterface,
        parser: DslParserInterface,
        metrics_repository: MetricsRepositoryInterface,
    ):
        self.repository = repository
        self.feature_flags_repository = feature_flags_repository
        self.parser = parser
        self.metrics_repository = metrics_repository

    async def check_experimenter_create_this_experiment(self, experiment_id, user):
        experiment = await self.repository.get(experiment_id)
        if not experiment.created_by == user.id and user.role != UserRole.ADMIN:
            raise AccessDeniedError("This experiment created by another experimenter")

    async def _validate_variants_type(self, feature_flag_id: str, variants):
        # проверка что тип вариантов совпадает с типом в эксперименте
        flag = await self.feature_flags_repository.get(feature_flag_id)
        for var in variants:
            validate_value_for_flag_type(var.value, flag.type, f"variant '{var.name}'")

    async def _resolve_metric_keys(self, metrics: list[ExperimentMetricBind]) -> dict[str, str]:
        metric_id_map = {}
        for m in metrics:
            metric = await self.metrics_repository.get_by_key(m.metric_key)
            metric_id_map[m.metric_key] = metric.id
        return metric_id_map

    async def create_experiment(
        self, data: ExperimentCreate, created_by: str
    ) -> ExperimentResponse:
        for metric in data.metrics:
            await self.metrics_repository.get_by_key(metric.metric_key)

        if data.targeting_rule is not None and not self.parser.validate(data.targeting_rule):
            raise UnsupportableContentError(f"Unsupportable targeting rule {data.targeting_rule}")

        try:
            flag = await self.feature_flags_repository.get_by_key(data.feature_flag_key)
        except EntityNotFoundError:
            raise EntityNotFoundError(f"Feature flag '{data.feature_flag_key}' not found")

        await self._validate_variants_type(flag.id, data.variants)

        metric_id_map = await self._resolve_metric_keys(data.metrics)

        return await self.repository.create_experiment(data, created_by, flag, metric_id_map)

    async def get_experiment(self, experiment_id: str) -> ExperimentResponse:
        return await self.repository.get(experiment_id)

    async def get_experiments(
        self,
        page: int,
        size: int,
        status: str | None = None,
    ) -> PagedExperiments:
        status_filter: ExperimentStatus | None = None
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
        if data.metrics is not None:
            for metric in data.metrics:
                await self.metrics_repository.get_by_key(metric.metric_key)

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

        metric_id_map = None
        if data.metrics is not None:
            metric_id_map = await self._resolve_metric_keys(data.metrics)

        flag = await self.feature_flags_repository.get(experiment.feature_flag_id)
        return await self.repository.update_experiment(experiment_id, data, modified_by, flag.default_value, metric_id_map)

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

        if await self.repository.has_active_experiment_for_flag(experiment.feature_flag_id, exclude_experiment_id=experiment_id):
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

    async def finish_experiment(self, experiment_id: str, actor_id: str, experiment_results: ExperimentFinish) -> ExperimentResponse:
        """RUNNING | PAUSED -> FINISHED"""
        experiment = await self.repository.get(experiment_id)
        current_status = experiment.status

        if ExperimentStatus.FINISHED not in ALLOWED_TRANSITIONS.get(current_status, []):
            raise ConflictError(
                f"Cannot transition from '{current_status.value}' to 'finished'"
            )
        return await self.repository.transition_status(
            experiment_id,
            ExperimentStatus.FINISHED,
            result=experiment_results.result,
            result_description=experiment_results.result_description,
        )

    async def archive_experiment(self, experiment_id: str, actor_id: str) -> ExperimentResponse:
        """FINISHED -> ARCHIVED"""
        return await self._transition(experiment_id, ExperimentStatus.ARCHIVED, actor_id)