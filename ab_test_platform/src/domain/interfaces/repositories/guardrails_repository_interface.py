from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.models.guardrail_triggers import GuardrailTriggers


class GuardrailRepositoryInterface(Protocol):
    @abstractmethod
    async def create_trigger(self, trigger: GuardrailTriggers) -> GuardrailTriggers:
        ...

    @abstractmethod
    async def get_triggers_by_experiment(self, experiment_id: str) -> list[GuardrailTriggers]:
        ...