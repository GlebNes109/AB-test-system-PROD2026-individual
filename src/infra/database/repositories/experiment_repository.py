import uuid
from typing import Optional

from sqlalchemy import select, update, insert, func, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import EntityNotFoundError
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.experiments import (
    Experiments,
    ExperimentVersions,
    Variants,
    ExperimentStatus,
)
from src.schemas.experiments import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    VariantResponse,
    PagedExperiments,
)


class ExperimentsRepository(BaseRepository):
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

    def _build_response(self, experiment: Experiments, version: ExperimentVersions) -> ExperimentResponse:
        return ExperimentResponse(
            id=experiment.id,
            feature_flag_id=experiment.feature_flag_id,
            created_by=experiment.created_by,
            created_at=experiment.created_at,
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
        )

    async def create_experiment(self, data: ExperimentCreate, created_by: str) -> ExperimentResponse:
        experiment_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        experiment = Experiments(
            id=experiment_id,
            feature_flag_id=data.feature_flag_id,
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

        await self.session.commit()
        await self.session.refresh(experiment)
        current_version = await self._get_current_version(experiment_id, 1)
        return self._build_response(experiment, current_version)

    async def get(self, experiment_id: str) -> ExperimentResponse:
        experiment = await self._get_experiment_row(experiment_id)
        current_version = await self._get_current_version(experiment_id, experiment.version)
        return self._build_response(experiment, current_version)

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

        items = []
        for experiment, version in rows:
            resp = ExperimentResponse(
                id=experiment.id,
                feature_flag_id=experiment.feature_flag_id,
                created_by=experiment.created_by,
                created_at=experiment.created_at,
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
            )
            items.append(resp)

        return PagedExperiments(items=items, total=total or 0, page=page, size=size)

    async def update_experiment(
        self, experiment_id: str, data: ExperimentUpdate, modified_by: str
    ) -> ExperimentResponse:
        experiment = await self._get_experiment_row(experiment_id)
        prev_version = await self._get_current_version(experiment_id, experiment.version)

        new_version_number = experiment.version + 1
        new_version_id = str(uuid.uuid4())

        new_version = ExperimentVersions(
            id=new_version_id,
            experiment_id=experiment_id,
            name=data.name if data.name is not None else prev_version.name,
            version_number=new_version_number,
            targeting_rule=data.targeting_rule if data.targeting_rule is not None else prev_version.targeting_rule,
            audience_percentage=data.audience_percentage if data.audience_percentage is not None else prev_version.audience_percentage,
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

        await self.session.execute(
            update(Experiments)
            .where(Experiments.id == experiment_id)
            .values(version=new_version_number)
        )
        await self.session.commit()

        updated = await self._get_experiment_row(experiment_id)
        current_version = await self._get_current_version(experiment_id, updated.version)
        return self._build_response(updated, current_version)

    async def transition_status(
        self, experiment_id: str, new_status: ExperimentStatus
    ) -> ExperimentResponse:
        experiment = await self._get_experiment_row(experiment_id)

        await self.session.execute(
            update(Experiments)
            .where(Experiments.id == experiment_id)
            .values(status=new_status)
        )
        await self.session.commit()

        await self.session.refresh(experiment)
        current_version = await self._get_current_version(experiment_id, experiment.version)
        return self._build_response(experiment, current_version)

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