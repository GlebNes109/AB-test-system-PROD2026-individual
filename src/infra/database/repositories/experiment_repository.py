import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, insert, delete, func, literal
from sqlalchemy.orm import selectinload

from src.domain.exceptions import EntityNotFoundError
from src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.experiments import (
    Experiments,
    ExperimentVersions,
    Variants,
    ExperimentStatus,
)
from src.models.feature_flags import FeatureFlags
from src.models.metrics import ExperimentMetrics as ExperimentMetricsModel, Metrics
from src.schemas.experiments import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    VariantResponse,
    PagedExperiments,
)
from src.schemas.metrics import ExperimentMetricBind, ExperimentMetricResponse


class ExperimentsRepository(BaseRepository, ExperimentsRepositoryInterface):
    async def _get_experiment_row(self, experiment_id: str) -> Experiments:
        stmt = select(Experiments).where(Experiments.id == experiment_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise EntityNotFoundError(f"Experiment {experiment_id} not found")
        return row

    async def _get_current_version(self, experiment_id: str, version_number: int) -> ExperimentVersions:
        stmt = (
            select(ExperimentVersions)
            .where(
                ExperimentVersions.experiment_id == experiment_id,
                ExperimentVersions.version_number == version_number,
            )
            .options(selectinload(ExperimentVersions.variants))
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise EntityNotFoundError(f"ExperimentVersion not found for experiment {experiment_id} v{version_number}")
        return row

    async def _get_experiment_metrics(self, experiment_id: str) -> list[ExperimentMetricResponse]:
        stmt = (
            select(ExperimentMetricsModel, Metrics)
            .join(Metrics, ExperimentMetricsModel.metric_id == Metrics.id)
            .where(ExperimentMetricsModel.experiment_id == experiment_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            ExperimentMetricResponse(
                metric_id=em.metric_id,
                metric_key=m.key,
                metric_name=m.name,
                type=em.type,
                threshold=em.threshold,
                window_minutes=em.window_minutes,
                action=em.action,
            )
            for em, m in rows
        ]

    async def _save_metrics(self, experiment_id: str, metrics: list[ExperimentMetricBind], metric_id_map: dict[str, str]) -> None:
        for m in metrics:
            self.session.add(ExperimentMetricsModel(
                id=str(uuid.uuid4()),
                experiment_id=experiment_id,
                metric_id=metric_id_map[m.metric_key],
                type=m.type,
                threshold=m.threshold,
                window_minutes=m.window_minutes,
                action=m.action,
            ))

    async def _replace_metrics(self, experiment_id: str, metrics: list[ExperimentMetricBind], metric_id_map: dict[str, str]) -> None:
        await self.session.execute(
            delete(ExperimentMetricsModel).where(ExperimentMetricsModel.experiment_id == experiment_id)
        )
        await self._save_metrics(experiment_id, metrics, metric_id_map)

    async def _get_flag_key(self, feature_flag_id: str) -> str:
        stmt = select(FeatureFlags.key).where(FeatureFlags.id == feature_flag_id)
        result = await self.session.scalar(stmt)
        return result or ""

    async def _get_flag_keys_batch(self, feature_flag_ids: list[str]) -> dict[str, str]:
        if not feature_flag_ids:
            return {}
        stmt = select(FeatureFlags.id, FeatureFlags.key).where(FeatureFlags.id.in_(feature_flag_ids))
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    def _build_response(self, experiment: Experiments, version: ExperimentVersions, feature_flag_key: str, metrics: list[ExperimentMetricResponse] = None) -> ExperimentResponse:
        return ExperimentResponse(
            id=experiment.id,
            feature_flag_id=experiment.feature_flag_id,
            feature_flag_key=feature_flag_key,
            created_by=experiment.created_by,
            created_at=experiment.created_at,
            started_at=experiment.started_at,
            version=experiment.version,
            name=version.name,
            targeting_rule=version.targeting_rule,
            status=experiment.status,
            audience_percentage=version.audience_percentage,
            modified_by=version.modified_by,
            variants=[
                VariantResponse(
                    id=v.id,
                    name=v.name,
                    value=v.value,
                    weight=v.weight,
                    is_control=v.is_control,
                )
                for v in version.variants
            ],
            metrics=metrics or [],
        )

    async def create_experiment(self, data: ExperimentCreate, created_by: str, flag, metric_id_map: dict[str, str] = None) -> ExperimentResponse:
        experiment_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        flag_default_value = flag.default_value

        experiment = Experiments(
            id=experiment_id,
            feature_flag_id=flag.id,
            created_by=created_by,
            status=ExperimentStatus.DRAFT,
            version=1,
        )
        self.session.add(experiment)
        await self.session.flush()

        version = ExperimentVersions(
            id=version_id,
            experiment_id=experiment_id,
            name=data.name,
            version_number=1,
            targeting_rule=data.targeting_rule,
            audience_percentage=data.audience_percentage,
            modified_by=created_by,
        )
        self.session.add(version)
        await self.session.flush()

        for var in data.variants:
            self.session.add(Variants(
                id=str(uuid.uuid4()),
                experiment_version_id=version_id,
                name=var.name,
                value=str(var.value),
                weight=var.weight,
                is_control=var.is_control,
            ))

        # Дефолтный вариант создается вместе с другими. Пользователи вне тестовой группы получают значение флага по умолчанию
        self.session.add(Variants(
            id=str(uuid.uuid4()),
            experiment_version_id=version_id,
            name="default",
            value=str(flag_default_value),
            weight=100 - data.audience_percentage,
            is_control=False,
        ))

        if metric_id_map:
            await self._save_metrics(experiment_id, data.metrics, metric_id_map)

        await self.session.commit()
        await self.session.refresh(experiment)
        current_version = await self._get_current_version(experiment_id, 1)
        metrics = await self._get_experiment_metrics(experiment_id)
        return self._build_response(experiment, current_version, flag.key, metrics)

    async def get(self, experiment_id: str) -> ExperimentResponse:
        experiment = await self._get_experiment_row(experiment_id)
        current_version = await self._get_current_version(experiment_id, experiment.version)
        metrics = await self._get_experiment_metrics(experiment_id)
        flag_key = await self._get_flag_key(experiment.feature_flag_id)
        return self._build_response(experiment, current_version, flag_key, metrics)

    async def get_all_experiments(
        self,
        page: int,
        size: int,
        status: Optional[ExperimentStatus] = None,
    ) -> PagedExperiments:
        offset = page * size

        # Sub-query: получение version_id для каждого эксперимента
        subq = (
            select(ExperimentVersions.id)
            .where(
                ExperimentVersions.experiment_id == Experiments.id,
                ExperimentVersions.version_number == Experiments.version,
            )
            .correlate(Experiments)
            .scalar_subquery()
        )

        stmt = (
            select(Experiments, ExperimentVersions)
            .join(ExperimentVersions, ExperimentVersions.id == subq)
        )
        if status is not None:
            stmt = stmt.where(Experiments.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt)

        stmt = stmt.offset(offset).limit(size)
        rows = (await self.session.execute(stmt)).all()

        # Batch-load вариантов для всех версий чтобы не было lazy-load загрузки в асинхронном контексте
        version_ids = [version.id for _, version in rows]
        variants_by_version: dict[str, list[Variants]] = {vid: [] for vid in version_ids}
        if version_ids:
            variants_stmt = select(Variants).where(Variants.experiment_version_id.in_(version_ids))
            all_variants = (await self.session.execute(variants_stmt)).scalars().all()
            for v in all_variants:
                variants_by_version[v.experiment_version_id].append(v)

        # Batch-load метрик для всех экспериментов
        experiment_ids = [exp.id for exp, _ in rows]
        metrics_by_experiment: dict[str, list[ExperimentMetricResponse]] = {eid: [] for eid in experiment_ids}
        if experiment_ids:
            metrics_stmt = (
                select(ExperimentMetricsModel, Metrics)
                .join(Metrics, ExperimentMetricsModel.metric_id == Metrics.id)
                .where(ExperimentMetricsModel.experiment_id.in_(experiment_ids))
            )
            all_metrics = (await self.session.execute(metrics_stmt)).all()
            for em, m in all_metrics:
                metrics_by_experiment[em.experiment_id].append(
                    ExperimentMetricResponse(
                        metric_id=em.metric_id,
                        metric_key=m.key,
                        metric_name=m.name,
                        type=em.type,
                        threshold=em.threshold,
                        window_minutes=em.window_minutes,
                        action=em.action,
                    )
                )

        # Batch-load flag keys
        flag_ids = list({exp.feature_flag_id for exp, _ in rows})
        flag_key_map = await self._get_flag_keys_batch(flag_ids)

        items = []
        for experiment, version in rows:
            resp = ExperimentResponse(
                id=experiment.id,
                feature_flag_id=experiment.feature_flag_id,
                feature_flag_key=flag_key_map.get(experiment.feature_flag_id, ""),
                created_by=experiment.created_by,
                created_at=experiment.created_at,
                started_at=experiment.started_at,
                version=experiment.version,
                name=version.name,
                targeting_rule=version.targeting_rule,
                status=experiment.status,
                audience_percentage=version.audience_percentage,
                modified_by=version.modified_by,
                variants=[
                    VariantResponse(
                        id=v.id, name=v.name, value=v.value,
                        weight=v.weight, is_control=v.is_control,
                    )
                    for v in variants_by_version.get(version.id, [])
                ],
                metrics=metrics_by_experiment.get(experiment.id, []),
            )
            items.append(resp)

        return PagedExperiments(items=items, total=total or 0, page=page, size=size)

    async def update_experiment(
        self, experiment_id: str, data: ExperimentUpdate, modified_by: str, flag_default_value: str | None = None, metric_id_map: dict[str, str] | None = None
    ) -> ExperimentResponse:
        experiment = await self._get_experiment_row(experiment_id)
        prev_version = await self._get_current_version(experiment_id, experiment.version)

        new_version_number = experiment.version + 1
        new_version_id = str(uuid.uuid4())
        new_audience = data.audience_percentage if data.audience_percentage is not None else prev_version.audience_percentage

        new_version = ExperimentVersions(
            id=new_version_id,
            experiment_id=experiment_id,
            name=data.name if data.name is not None else prev_version.name,
            version_number=new_version_number,
            targeting_rule=data.targeting_rule if data.targeting_rule is not None else prev_version.targeting_rule,
            audience_percentage=new_audience,
            modified_by=modified_by,
        )
        self.session.add(new_version)
        await self.session.flush()

        if data.variants is not None:
            for var in data.variants:
                self.session.add(Variants(
                    id=str(uuid.uuid4()),
                    experiment_version_id=new_version_id,
                    name=var.name,
                    value=str(var.value),
                    weight=var.weight,
                    is_control=var.is_control,
                ))
            # Пересчет дефолтного варианта под новый audience и variants
            if flag_default_value is not None:
                self.session.add(Variants(
                    id=str(uuid.uuid4()),
                    experiment_version_id=new_version_id,
                    name="default",
                    value=str(flag_default_value),
                    weight=100 - new_audience,
                    is_control=False,
                ))
        else:
            # Копирование вариантов из предыдущей версии одним SQL-запросом
            await self.session.execute(
                insert(Variants).from_select(
                    ["id", "experiment_version_id", "name", "value", "weight", "is_control"],
                    select(
                        func.gen_random_uuid(),
                        literal(new_version_id),
                        Variants.name,
                        Variants.value,
                        Variants.weight,
                        Variants.is_control,
                    ).where(Variants.experiment_version_id == prev_version.id),
                )
            )

        # Метрики не версионируются , при обновлении заменяются целиком
        if data.metrics is not None and metric_id_map is not None:
            await self._replace_metrics(experiment_id, data.metrics, metric_id_map)

        await self.session.execute(
            update(Experiments)
            .where(Experiments.id == experiment_id)
            .values(version=new_version_number)
        )
        await self.session.commit()

        updated = await self._get_experiment_row(experiment_id)
        current_version = await self._get_current_version(experiment_id, updated.version)
        metrics = await self._get_experiment_metrics(experiment_id)
        flag_key = await self._get_flag_key(updated.feature_flag_id)
        return self._build_response(updated, current_version, flag_key, metrics)

    async def transition_status(
        self, experiment_id: str, new_status: ExperimentStatus
    ) -> ExperimentResponse:
        experiment = await self._get_experiment_row(experiment_id)

        values: dict = {"status": new_status}
        if new_status == ExperimentStatus.RUNNING and experiment.started_at is None:
            values["started_at"] = datetime.now(timezone.utc)

        await self.session.execute(
            update(Experiments)
            .where(Experiments.id == experiment_id)
            .values(**values)
        )
        await self.session.commit()

        await self.session.refresh(experiment)
        current_version = await self._get_current_version(experiment_id, experiment.version)
        metrics = await self._get_experiment_metrics(experiment_id)
        flag_key = await self._get_flag_key(experiment.feature_flag_id)
        return self._build_response(experiment, current_version, flag_key, metrics)

    async def has_active_experiment_for_flag(self, feature_flag_id: str) -> bool:
        stmt = select(func.count()).select_from(
            select(Experiments)
            .where(
                Experiments.feature_flag_id == feature_flag_id,
                Experiments.status.in_([ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]),
            )
            .subquery()
        )
        count = await self.session.scalar(stmt)
        return (count or 0) > 0

    async def get_active_experiment_for_flag(self, feature_flag_id: str) -> ExperimentResponse | None:
        stmt = select(Experiments).where(Experiments.feature_flag_id == feature_flag_id, Experiments.status == ExperimentStatus.RUNNING)
        experiment = (await self.session.execute(stmt)).scalar_one_or_none()
        if experiment is None:
            return None
        current_version = await self._get_current_version(experiment.id, experiment.version)
        metrics = await self._get_experiment_metrics(experiment.id)
        flag_key = await self._get_flag_key(experiment.feature_flag_id)
        return self._build_response(experiment, current_version, flag_key, metrics)