from sqlalchemy.exc import NoResultFound
from sqlalchemy import select, func, or_, desc

from src.domain.exceptions import EntityNotFoundError
from src.domain.interfaces.repositories.decisions_repository_interface import DecisionsRepositoryInterface
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.decisions import Decisions
from src.models.experiments import Experiments, ExperimentStatus


class DecisionsRepository(BaseRepository, DecisionsRepositoryInterface):
    async def get_decision_by_feature_flag_id(self, feature_flag_id: str) -> Decisions:
        stmt = (
            select(Decisions)
            .join(Experiments, Decisions.experiment_id == Experiments.id)
            .where(Experiments.feature_flag_id == feature_flag_id)
        )
        result = await self.session.execute(stmt)
        try:
            obj = result.scalar_one()
            return self.read_schema.model_validate(obj, from_attributes=True)
        except NoResultFound:
            raise EntityNotFoundError

    async def get_decision_by_subject_and_experiment(self, subject_id: str, experiment_id: str) -> Decisions:
        stmt = select(Decisions).where(
            Decisions.subject_id == subject_id,
            Decisions.experiment_id == experiment_id,
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError
        return self.read_schema.model_validate(obj, from_attributes=True)

    async def count_active_experiments_by_subject(self, subject_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Decisions)
            .join(
                Experiments,
                Decisions.experiment_id == Experiments.id
            )
            .where(
                Decisions.subject_id == subject_id,
                or_(
                    Experiments.status == ExperimentStatus.RUNNING, # TODO вынести блокирующие статусы в домен/application слой
                    Experiments.status == ExperimentStatus.PAUSED,
                )
            )
        )

        return await self.session.scalar(stmt)

    async def get_last_decision_by_subject(self, subject_id: str) -> Decisions | None:
        stmt = (
            select(Decisions)
            .where(Decisions.subject_id == subject_id)
            .order_by(desc(Decisions.createdAt))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        return self.read_schema.model_validate(obj, from_attributes=True)
