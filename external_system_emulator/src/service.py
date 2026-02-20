import asyncio
import logging
import random
import uuid
from typing import Any

from src.abtests_api_integration import ABTestClient
from src.schemas import ScenarioConfig, ScenarioStatus, VariantConfig, EventsConfig

logger = logging.getLogger(__name__)


class ScenarioStore:
    """Хранилище сценариев в памяти."""

    def __init__(self):
        self._scenarios: dict[str, ScenarioConfig] = {}
        self._statuses: dict[str, ScenarioStatus] = {}

    def create(self, config: ScenarioConfig) -> ScenarioStatus:
        scenario_id = str(uuid.uuid4())
        self._scenarios[scenario_id] = config
        status = ScenarioStatus(
            id=scenario_id,
            scenario_name=config.scenario_name,
            status="pending",
            subjects_total=config.subjects_count,
            subjects_processed=0,
            events_sent=0,
        )
        self._statuses[scenario_id] = status
        return status

    def get_config(self, scenario_id: str) -> ScenarioConfig | None:
        return self._scenarios.get(scenario_id)

    def get_status(self, scenario_id: str) -> ScenarioStatus | None:
        return self._statuses.get(scenario_id)

    def list_all(self) -> list[ScenarioStatus]:
        return list(self._statuses.values())


def _calc_delay(base: int, variation: int) -> float:
    """Рассчитать задержку с вариацией: base ± variation (не меньше 0)."""
    offset = random.uniform(-variation, variation)
    return max(0.0, base + offset)


def _find_variant(variants: list[VariantConfig], value: Any) -> VariantConfig | None:
    """Найти конфиг варианта по значению флага."""
    val_str = str(value)
    for v in variants:
        if v.feature_flag_value == val_str:
            return v
    return None


class ScenarioRunner:
    """Запуск сценария: генерация пользователей, decisions, events."""

    def __init__(self, client: ABTestClient, store: ScenarioStore):
        self.client = client
        self.store = store

    async def run(self, scenario_id: str):
        config = self.store.get_config(scenario_id)
        status = self.store.get_status(scenario_id)
        if config is None or status is None:
            return

        status.status = "running"
        exp = config.experiment

        try:
            tasks: list[asyncio.Task] = []
            for i in range(config.subjects_count):
                if i > 0:
                    delay = _calc_delay(exp.time_delay_seconds, exp.time_variation)
                    await asyncio.sleep(delay)

                subject_id = str(uuid.uuid4())
                task = asyncio.create_task(
                    self._process_subject(scenario_id, subject_id, config)
                )
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)
            status.status = "finished"
            logger.info(
                "Scenario %s finished: %d subjects, %d events sent",
                scenario_id, status.subjects_processed, status.events_sent,
            )
        except Exception as e:
            status.status = "error"
            status.errors.append(str(e))
            logger.exception("Scenario %s failed", scenario_id)

    async def _process_subject(
        self, scenario_id: str, subject_id: str, config: ScenarioConfig
    ):
        status = self.store.get_status(scenario_id)
        exp = config.experiment

        try:
            decisions = await self.client.get_decision(
                subject_id, [exp.feature_flag_key]
            )
            if not decisions:
                logger.warning("No decisions for subject %s", subject_id)
                status.subjects_processed += 1
                return

            decision = decisions[0]
            decision_id = decision.get("id")
            value = decision.get("value")

            if decision_id is None:
                status.subjects_processed += 1
                return

            variant = _find_variant(exp.variants, value)
            if variant is None:
                logger.warning(
                    "No variant config for value=%s, subject=%s", value, subject_id
                )
                status.subjects_processed += 1
                return

            sent_any_event = await self._send_events(
                status, variant.events, decision_id, subject_id
            )

            """if sent_any_event and variant.sub_events:
                await self._send_events(
                    status, variant.sub_events, decision_id, subject_id
                )"""

            status.subjects_processed += 1

        except Exception as e:
            logger.error("Error processing subject %s: %s", subject_id, e)
            status.errors.append(f"subject {subject_id}: {e}")
            status.subjects_processed += 1

    async def _send_events(
        self,
        status: ScenarioStatus,
        events_config: list[EventsConfig],
        decision_id: str,
        subject_id: str,
    ) -> bool:
        """Отправить события по конфигу. Возвращает True, если хотя бы одно событие отправлено."""
        sent_any = False
        for ec in events_config:
            if random.random() > ec.probability:
                continue

            delay = _calc_delay(ec.time_delay_seconds, ec.time_variation)
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                await self.client.send_events([
                    {
                        "event_type": ec.event_type,
                        "decision_id": decision_id,
                        "subject_id": subject_id,
                    }
                ])
                status.events_sent += 1
                sent_any = True
            except Exception as e:
                logger.error("Failed to send event %s: %s", ec.event_type, e)
                status.errors.append(f"event {ec.event_type} for {subject_id}: {e}")

        return sent_any
