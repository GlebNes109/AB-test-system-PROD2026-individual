from datetime import UTC, datetime

from ab_test_platform.src.domain.exceptions import (
    BadRequestError,
    ConflictError,
    EntityNotFoundError,
)
from ab_test_platform.src.domain.interfaces.repositories.experiment_repository_interface import (
    ExperimentsRepositoryInterface,
)
from ab_test_platform.src.domain.interfaces.repositories.learnings_repository_interface import (
    LearningsRepositoryInterface,
)
from ab_test_platform.src.domain.interfaces.repositories.metrics_repository_interface import (
    MetricsRepositoryInterface,
)
from ab_test_platform.src.models.experiments import ExperimentResult, ExperimentStatus
from ab_test_platform.src.models.learnings import Learnings
from ab_test_platform.src.schemas.learnings import (
    LearningCreate,
    LearningResponse,
    LearningUpdate,
    PagedLearnings,
    SimilarLearningResponse,
)

LEARNABLE_STATUSES = {ExperimentStatus.FINISHED, ExperimentStatus.ARCHIVED}


class LearningsService:
    def __init__(
        self,
        repository: LearningsRepositoryInterface,
        experiment_repository: ExperimentsRepositoryInterface,
        metrics_repository: MetricsRepositoryInterface,
    ):
        self.repository = repository
        self.experiment_repository = experiment_repository
        self.metrics_repository = metrics_repository

    async def create_learning(self, data: LearningCreate, created_by: str) -> LearningResponse:
        experiment = await self.experiment_repository.get(data.experiment_id)

        if experiment.status not in LEARNABLE_STATUSES:
            raise ConflictError(
                f"Cannot create learning for experiment in status '{experiment.status.value}'. "
                "Only FINISHED or ARCHIVED experiments are allowed."
            )

        if experiment.result is None:
            raise ConflictError(
                "Experiment has no result. Finish the experiment with a result first."
            )

        await self.metrics_repository.get_by_key(data.primary_metric_key)

        now = datetime.now(UTC)
        learning = Learnings(
            experiment_id=data.experiment_id,
            hypothesis=data.hypothesis,
            primary_metric_key=data.primary_metric_key,
            result=experiment.result,
            result_description=experiment.result_description or "",
            tags=data.tags,
            platform=data.platform,
            segment=data.segment,
            dashboard_link=data.dashboard_link,
            ticket_link=data.ticket_link,
            notes=data.notes,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

        created = await self.repository.create(learning)
        return LearningResponse.model_validate(created, from_attributes=True)

    async def get_learning(self, learning_id: str) -> LearningResponse:
        learning = await self.repository.get(learning_id)
        return await self._enrich_single(learning)

    async def _enrich_single(self, learning: Learnings) -> LearningResponse:
        try:
            experiment = await self.experiment_repository.get(learning.experiment_id)
            return LearningResponse(
                id=learning.id,
                experiment_id=learning.experiment_id,
                experiment_name=experiment.name,
                feature_flag_key=experiment.feature_flag_key,
                hypothesis=learning.hypothesis,
                primary_metric_key=learning.primary_metric_key,
                result=learning.result,
                result_description=learning.result_description,
                tags=learning.tags or [],
                platform=learning.platform,
                segment=learning.segment,
                dashboard_link=learning.dashboard_link,
                ticket_link=learning.ticket_link,
                notes=learning.notes,
                created_by=learning.created_by,
                created_at=learning.created_at,
                updated_at=learning.updated_at,
            )
        except EntityNotFoundError:
            return LearningResponse.model_validate(learning, from_attributes=True)

    async def update_learning(self, learning_id: str, data: LearningUpdate) -> LearningResponse:
        learning = await self.repository.get(learning_id)

        values = data.model_dump(exclude_none=True)
        if not values:
            return await self._enrich_single(learning)

        if "primary_metric_key" in values:
            await self.metrics_repository.get_by_key(values["primary_metric_key"])

        updated = await self.repository.update(learning_id, values)
        return await self._enrich_single(updated)

    async def search_learnings(
        self,
        page: int,
        size: int,
        query: str | None = None,
        feature_flag_key: str | None = None,
        result: str | None = None,
        tags: list[str] | None = None,
        primary_metric_key: str | None = None,
        platform: str | None = None,
        created_by: str | None = None,
    ) -> PagedLearnings:
        result_filter: ExperimentResult | None = None
        if result is not None:
            try:
                result_filter = ExperimentResult(result)
            except ValueError:
                raise BadRequestError(
                    f"Invalid result value '{result}'. "
                    f"Allowed: {[r.value for r in ExperimentResult]}"
                ) from None

        items, total = await self.repository.search(
            query=query,
            feature_flag_key=feature_flag_key,
            result=result_filter,
            tags=tags,
            primary_metric_key=primary_metric_key,
            platform=platform,
            created_by=created_by,
            limit=size,
            offset=page * size,
        )

        return PagedLearnings(
            items=[LearningResponse(**item) for item in items],
            total=total,
            page=page,
            size=size,
        )

    async def find_similar(
        self,
        experiment_id: str,
        limit: int = 10,
    ) -> list[SimilarLearningResponse]:
        await self.experiment_repository.get(experiment_id)
        results = await self.repository.find_similar(experiment_id, limit)
        return [
            SimilarLearningResponse(
                learning=LearningResponse(**r["learning"]),
                similarity_reason=r["similarity_reason"],
            )
            for r in results
        ]
