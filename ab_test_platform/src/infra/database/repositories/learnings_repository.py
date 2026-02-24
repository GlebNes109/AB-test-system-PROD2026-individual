from datetime import UTC, datetime
from typing import Any

from ab_test_platform.src.domain.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from ab_test_platform.src.domain.interfaces.repositories.learnings_repository_interface import (
    LearningsRepositoryInterface,
)
from ab_test_platform.src.models.experiments import (
    ExperimentResult,
    Experiments,
    ExperimentVersions,
)
from ab_test_platform.src.models.feature_flags import FeatureFlags
from ab_test_platform.src.models.learnings import Learnings
from sqlalchemy import case, func, literal, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _fts_vector():
    return func.to_tsvector(
        text("'russian'"),
        func.coalesce(Learnings.hypothesis, "")
        + " "
        + func.coalesce(Learnings.notes, "")
        + " "
        + func.coalesce(Learnings.result_description, ""),
    )


class LearningsRepository(LearningsRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, learning: Learnings) -> Learnings:
        try:
            self.session.add(learning)
            await self.session.commit()
            await self.session.refresh(learning)
            return learning
        except IntegrityError as e:
            await self.session.rollback()
            if e.orig and hasattr(e.orig, "sqlstate") and e.orig.sqlstate == "23505":
                raise EntityAlreadyExistsError("Learning for this experiment already exists") from e
            raise

    async def get(self, learning_id: str) -> Learnings:
        result = await self.session.execute(select(Learnings).where(Learnings.id == learning_id))
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError("Learning not found")
        return obj

    async def get_by_experiment_id(self, experiment_id: str) -> Learnings:
        result = await self.session.execute(
            select(Learnings).where(Learnings.experiment_id == experiment_id)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError("Learning not found for this experiment")
        return obj

    async def update(self, learning_id: str, values: dict) -> Learnings:
        values["updated_at"] = datetime.now(UTC)
        await self.session.execute(
            update(Learnings).where(Learnings.id == learning_id).values(**values)
        )
        await self.session.commit()
        return await self.get(learning_id)

    async def _enrich_rows(self, rows: list[Any]) -> list[dict]:
        enriched = []
        for row in rows:
            learning = row[0] if isinstance(row, tuple) else row
            data = {
                "id": learning.id,
                "experiment_id": learning.experiment_id,
                "hypothesis": learning.hypothesis,
                "primary_metric_key": learning.primary_metric_key,
                "result": learning.result,
                "result_description": learning.result_description,
                "tags": learning.tags or [],
                "platform": learning.platform,
                "segment": learning.segment,
                "dashboard_link": learning.dashboard_link,
                "ticket_link": learning.ticket_link,
                "notes": learning.notes,
                "created_by": learning.created_by,
                "created_at": learning.created_at,
                "updated_at": learning.updated_at,
            }

            exp_res = await self.session.execute(
                select(Experiments).where(Experiments.id == learning.experiment_id)
            )
            experiment = exp_res.scalar_one_or_none()
            if experiment:
                ver_res = await self.session.execute(
                    select(ExperimentVersions)
                    .where(
                        ExperimentVersions.experiment_id == experiment.id,
                        ExperimentVersions.version_number == experiment.version,
                    )
                    .limit(1)
                )
                version = ver_res.scalar_one_or_none()
                data["experiment_name"] = version.name if version else None

                flag_res = await self.session.execute(
                    select(FeatureFlags).where(FeatureFlags.id == experiment.feature_flag_id)
                )
                flag = flag_res.scalar_one_or_none()
                data["feature_flag_key"] = flag.key if flag else None
            else:
                data["experiment_name"] = None
                data["feature_flag_key"] = None

            enriched.append(data)
        return enriched

    def _current_version_sub(self):
        return (
            select(ExperimentVersions.name)
            .join(Experiments, Experiments.id == ExperimentVersions.experiment_id)
            .where(
                ExperimentVersions.experiment_id == Learnings.experiment_id,
                ExperimentVersions.version_number == Experiments.version,
            )
            .correlate(Learnings)
            .scalar_subquery()
        )

    def _fts_vector_with_name(self):
        exp_name = self._current_version_sub()
        return func.to_tsvector(
            text("'russian'"),
            func.coalesce(Learnings.hypothesis, "")
            + " "
            + func.coalesce(Learnings.notes, "")
            + " "
            + func.coalesce(Learnings.result_description, "")
            + " "
            + func.coalesce(exp_name, ""),
        )

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
    ) -> tuple[list[dict], int]:
        stmt = select(Learnings)
        count_stmt = select(func.count()).select_from(Learnings)

        if query:
            ts_query = func.plainto_tsquery(text("'russian'"), query)
            fts_vec = self._fts_vector_with_name()
            fts_cond = fts_vec.op("@@")(ts_query)
            stmt = stmt.where(fts_cond)
            count_stmt = count_stmt.where(fts_cond)

        if feature_flag_key:
            flag_sub = (
                select(Experiments.id)
                .join(FeatureFlags, FeatureFlags.id == Experiments.feature_flag_id)
                .where(FeatureFlags.key == feature_flag_key)
            )
            stmt = stmt.where(Learnings.experiment_id.in_(flag_sub))
            count_stmt = count_stmt.where(Learnings.experiment_id.in_(flag_sub))

        if result:
            stmt = stmt.where(Learnings.result == result)
            count_stmt = count_stmt.where(Learnings.result == result)

        if tags:
            stmt = stmt.where(Learnings.tags.op("@>")(tags))
            count_stmt = count_stmt.where(Learnings.tags.op("@>")(tags))

        if primary_metric_key:
            stmt = stmt.where(Learnings.primary_metric_key == primary_metric_key)
            count_stmt = count_stmt.where(Learnings.primary_metric_key == primary_metric_key)

        if platform:
            stmt = stmt.where(Learnings.platform == platform)
            count_stmt = count_stmt.where(Learnings.platform == platform)

        if created_by:
            stmt = stmt.where(Learnings.created_by == created_by)
            count_stmt = count_stmt.where(Learnings.created_by == created_by)

        if query:
            ts_query = func.plainto_tsquery(text("'russian'"), query)
            fts_vec = self._fts_vector_with_name()
            stmt = stmt.order_by(
                func.ts_rank(fts_vec, ts_query).desc(),
                Learnings.created_at.desc(),
            )
        else:
            stmt = stmt.order_by(Learnings.created_at.desc())

        stmt = stmt.limit(limit).offset(offset)

        total = await self.session.scalar(count_stmt) or 0
        rows_result = await self.session.execute(stmt)
        rows = rows_result.scalars().all()
        enriched = await self._enrich_rows(rows)
        return enriched, total

    async def find_similar(
        self,
        experiment_id: str,
        limit: int,
    ) -> list[dict]:
        exp_res = await self.session.execute(
            select(Experiments).where(Experiments.id == experiment_id)
        )
        experiment = exp_res.scalar_one_or_none()
        if experiment is None:
            raise EntityNotFoundError("Experiment not found")

        learning_res = await self.session.execute(
            select(Learnings).where(Learnings.experiment_id == experiment_id)
        )
        source_learning = learning_res.scalar_one_or_none()

        same_flag_sub = select(Experiments.id).where(
            Experiments.feature_flag_id == experiment.feature_flag_id,
            Experiments.id != experiment_id,
        )

        stmt = (
            select(Learnings)
            .where(Learnings.experiment_id != experiment_id)
            .order_by(Learnings.created_at.desc())
        )

        if source_learning:
            tags_overlap = Learnings.tags.op("&&")(source_learning.tags or [])
            same_metric = Learnings.primary_metric_key == source_learning.primary_metric_key
            same_flag = Learnings.experiment_id.in_(same_flag_sub)

            score = (
                case((same_flag, literal(3)), else_=literal(0))
                + case((same_metric, literal(2)), else_=literal(0))
                + case((tags_overlap, literal(1)), else_=literal(0))
            )
            stmt = stmt.where(same_flag | same_metric | tags_overlap).order_by(
                score.desc(), Learnings.created_at.desc()
            )
        else:
            stmt = stmt.where(Learnings.experiment_id.in_(same_flag_sub))

        stmt = stmt.limit(limit)
        rows_result = await self.session.execute(stmt)
        rows = rows_result.scalars().all()
        enriched = await self._enrich_rows(rows)

        results = []
        for data in enriched:
            reasons = []
            if source_learning:
                en_exp = await self.session.execute(
                    select(Experiments).where(Experiments.id == data["experiment_id"])
                )
                en_experiment = en_exp.scalar_one_or_none()
                if en_experiment and en_experiment.feature_flag_id == experiment.feature_flag_id:
                    reasons.append("same_feature_flag")
                if data["primary_metric_key"] == source_learning.primary_metric_key:
                    reasons.append("same_primary_metric")
                common_tags = set(data.get("tags") or []) & set(source_learning.tags or [])
                if common_tags:
                    reasons.append(f"common_tags: {', '.join(sorted(common_tags))}")
            else:
                reasons.append("same_feature_flag")

            results.append({"learning": data, "similarity_reason": reasons})

        return results
