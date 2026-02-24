from ab_test_platform.src.models.guardrail_triggers import GuardrailTriggers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class GuardrailRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_trigger(self, trigger: GuardrailTriggers) -> GuardrailTriggers:
        self.session.add(trigger)
        await self.session.flush()
        return trigger

    async def get_triggers_by_experiment(self, experiment_id: str) -> list[GuardrailTriggers]:
        stmt = (
            select(GuardrailTriggers)
            .where(GuardrailTriggers.experiment_id == experiment_id)
            .order_by(GuardrailTriggers.triggered_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
