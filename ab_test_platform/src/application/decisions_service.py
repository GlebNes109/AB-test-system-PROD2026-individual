import hashlib
from datetime import datetime, timezone, timedelta

from ab_test_platform.src.domain.exceptions import EntityNotFoundError
from ab_test_platform.src.domain.interfaces.dsl_parser import DslParserInterface
from ab_test_platform.src.domain.interfaces.repositories.decisions_repository_interface import DecisionsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.feature_flag_repository_interface import FeatureFlagRepositoryInterface
from ab_test_platform.src.models.decisions import Decisions
from ab_test_platform.src.schemas.decisions import Subject, DecisionsResponse
from ab_test_platform.src.schemas.experiments import VariantResponse


class DecisionsService:
    def __init__(
        self,
        experiments_repository: ExperimentsRepositoryInterface,
        decisions_repository: DecisionsRepositoryInterface,
        feature_flag_repository: FeatureFlagRepositoryInterface,
        parser: DslParserInterface,
        cooling_period_days: int = 1,
        max_active_experiments: int = 10,
    ):
        self.experiments_repository = experiments_repository
        self.decisions_repository = decisions_repository
        self.feature_flag_repository = feature_flag_repository
        self.parser = parser
        self.cooling_period = timedelta(days=cooling_period_days)
        self.max_active_experiments = max_active_experiments

    async def check_target(self, data: dict[any]):
        return True

    @staticmethod
    def _hash_bucket(subject_id: str, experiment_id: str) -> int:
        seed = f"{subject_id}:{experiment_id}"
        digest = hashlib.sha256(seed.encode()).hexdigest()
        return int(digest, 16) % 100

    @staticmethod
    def _pick_variant(variants: list[VariantResponse], bucket: int) -> VariantResponse | None:
        cumulative = 0
        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant
        return None


    async def _make_ab_decision(self, subject_id: str, experiment) -> Decisions | None:
        bucket = self._hash_bucket(subject_id, experiment.id)
        variant = self._pick_variant(experiment.variants, bucket)
        if variant is None:
            return None

        decision = await self.decisions_repository.create(Decisions(
            subject_id=subject_id,
            variant_id=variant.id,
            experiment_id=experiment.id,
            value=variant.value,
        ))

        return decision

    def _return_default_without_experiment(self, feature_flag):
        return DecisionsResponse(value=feature_flag.default_value, id=None, created_at=datetime.now(timezone.utc))

    async def make_decision(self, subject: Subject) -> list[DecisionsResponse]:
        # конфликт экспериментов в одном домене и рассчет приоритета - будет реализовано в будущем

        # если все 3 проверки пройдены - получается решение по эксперименту. Пользователь участвует в эксперименте, он записывается в decisions, и в
        # дальнейшем он всегда видит выбранное значение, вплоть до окончания эксперимента, при условии, что он проходит по таргету (таргет всегда проверяется первым)

        decisions = []
        for flags_key in subject.flags_keys:
            feature_flag = await self.feature_flag_repository.get_by_key(flags_key)
            feature_flag_id = feature_flag.id

            # проверка что такой эксперимент есть.
            experiment = await self.experiments_repository.get_active_experiment_for_flag(feature_flag_id)
            if experiment is None:
                decisions.append(self._return_default_without_experiment(feature_flag))
                continue

            # проверка по таргету
            if not self.parser.check_rule_matches(subject.subject_attr, experiment.targeting_rule):
                decisions.append(self._return_default_without_experiment(feature_flag))
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

            if await self.decisions_repository.count_active_experiments_by_subject(subject.id) >= self.max_active_experiments:
                decisions.append(self._return_default_without_experiment(feature_flag))
                continue

            last_decision = await self.decisions_repository.get_last_decision_by_subject(subject.id)
            if last_decision is not None:
                time_since_last = datetime.now(timezone.utc) - last_decision.createdAt
                if time_since_last < self.cooling_period:
                    decisions.append(self._return_default_without_experiment(feature_flag))
                    continue


            decision = await self._make_ab_decision(subject_id=subject.id, experiment=experiment)
            # если пользователь не попал в эксперимент по результатам проверки
            if decision is None:
                decisions.append(self._return_default_without_experiment(feature_flag))
                continue

            decisions.append(DecisionsResponse(value=decision.value, id=decision.id, created_at=decision.createdAt))

        return decisions







