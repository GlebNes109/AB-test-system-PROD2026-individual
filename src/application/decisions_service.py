import hashlib
from datetime import datetime, timezone

from src.domain.exceptions import EntityNotFoundError
from src.domain.interfaces.repositories.decisions_repository_interface import DecisionsRepositoryInterface
from src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from src.domain.interfaces.repositories.feature_flag_repository_interface import FeatureFlagRepositoryInterface
from src.models.decisions import Decisions
from src.schemas.decisions import Subject, DecisionsResponse
from src.schemas.experiments import VariantResponse


class DecisionsService:
    def __init__(self, experiments_repository: ExperimentsRepositoryInterface, decisions_repository: DecisionsRepositoryInterface, feature_flag_repository: FeatureFlagRepositoryInterface):
        self.experiments_repository = experiments_repository
        self.decisions_repository = decisions_repository
        self.feature_flag_repository = feature_flag_repository

    async def check_target(self, data: dict[any]):
        return True

    @staticmethod
    def _hash_bucket(subject_id: str, experiment_id: str) -> int:
        seed = f"{subject_id}:{experiment_id}"
        digest = hashlib.sha256(seed.encode()).hexdigest()
        return int(digest, 16) % 100

    @staticmethod
    def _pick_variant(variants: list[VariantResponse], bucket: int) -> VariantResponse:
        cumulative = 0
        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant
        return variants[-1]


    async def _make_ab_decision(self, subject_id: str, experiment) -> Decisions:
        bucket = self._hash_bucket(subject_id, experiment.id)
        variant = self._pick_variant(experiment.variants, bucket)

        decision = await self.decisions_repository.create(Decisions(
            subject_id=subject_id,
            variant_id=variant.id,
            experiment_id=experiment.id,
            value=variant.value,
        ))

        return decision

    async def make_decision(self, subject: Subject) -> list[DecisionsResponse]:
        # конфликт экспериментов в одном домене и рассчет приоритета - будет реализовано в будущем

        # если все 3 проверки пройдены - получается решение по эксперименту. Пользователь участвует в эксперименте, он записывается в decisions, и в
        # дальнейшем он всегда видит выбранное значение, вплоть до окончания эксперимента, при условии, что он проходит по таргету (таргет всегда проверяется первым)

        decisions = []
        for flags_key in subject.flags_keys:
            flag = await self.feature_flag_repository.get_by_key(flags_key)
            feature_flag_id = flag.id

            # проверка что такой эксперимент есть.
            experiment = await self.experiments_repository.get_active_experiment_for_flag(feature_flag_id)
            if experiment is None:
                decisions.append(DecisionsResponse(value=flag.default_value, id=None, created_at=datetime.now(timezone.utc)))
                continue

            # проверка по таргету
            if not await self.check_target(subject.subject_attr):
                decisions.append(DecisionsResponse(value=flag.default_value, id=None, created_at=datetime.now(timezone.utc)))
                continue

            # проверка, участвует ли он в эксперименте на этом флаге. Если участвует, берется уже полученное ранее значение, приклеенное к этому пользователю
            try:
                decision = await self.decisions_repository.get_decision_by_subject_and_experiment(
                    subject_id=subject.id,
                    experiment_id=experiment.id,
                )
                decisions.append(DecisionsResponse(value=decision.value, id=decision.id, created_at=decision.createdAt))
                continue
            except EntityNotFoundError:
                pass

            # охлаждение пользователя
            # охлаждение происходит в двух случаях:
            # 1. если число активных экспериментов на этом пользователе выше критического значения
            # 2. если пользователь уже недавно участвовал в эксперименте (с момента создания последнего decisions для этого пользователя прошло мало времени)

            decision = await self._make_ab_decision(subject_id=subject.id, experiment=experiment)

            decisions.append(DecisionsResponse(value=decision.value, id=decision.id, created_at=decision.createdAt))

        return decisions







