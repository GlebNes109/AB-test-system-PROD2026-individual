import logging
from datetime import datetime, timezone, timedelta

from ab_test_platform.src.domain.interfaces.repositories.experiment_repository_interface import \
    ExperimentsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.metrics_repository_interface import MetricsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.reports_repository_interface import ReportsRepositoryInterface
from ab_test_platform.src.infra.database.repositories.guardrail_repository import GuardrailRepository
from ab_test_platform.src.models.experiments import ExperimentStatus
from ab_test_platform.src.models.guardrail_triggers import GuardrailTriggers
from ab_test_platform.src.models.metrics import MetricType, GuardrailAction

logger = logging.getLogger(__name__)


class GuardrailService:
    def __init__(
        self,
        experiment_repository: ExperimentsRepositoryInterface,
        reports_repository: ReportsRepositoryInterface,
        metrics_repository: MetricsRepositoryInterface,
        guardrail_repository: GuardrailRepository,
    ):
        self.experiment_repository = experiment_repository
        self.reports_repository = reports_repository
        self.metrics_repository = metrics_repository
        self.guardrail_repository = guardrail_repository

    async def check_all_experiments(self) -> None:
        experiments = await self.experiment_repository.get_running_experiments()

        for experiment in experiments:
            guardrail_metrics = [m for m in experiment.metrics if m.type == MetricType.GUARDRAIL]
            if not guardrail_metrics:
                continue

            # find control variant id
            control_variant_ids = {v.id for v in experiment.variants if v.is_control}

            for gm in guardrail_metrics:
                metric = await self.metrics_repository.get(gm.metric_id)

                now = datetime.now(timezone.utc)
                date_from = now - timedelta(minutes=gm.window_minutes)
                date_to = now

                try:
                    rows = await self.reports_repository.compute_metric_summary(
                        experiment_id=experiment.id,
                        event_type=metric.event_type,
                        aggregation=metric.aggregation.value,
                        payload_field=metric.payload_field,
                        date_from=date_from,
                        date_to=date_to,
                        prerequisite_event_type=metric.prerequisite_event_type,
                    )
                except Exception:
                    logger.exception(
                        "Failed to compute metric %s for experiment %s",
                        gm.metric_key, experiment.id,
                    )
                    continue

                triggered = False
                for row in rows:
                    variant_id, value = row[0], row[1]
                    if variant_id in control_variant_ids:
                        continue
                    if value is not None and value > gm.threshold:
                        trigger = GuardrailTriggers(
                            experiment_id=experiment.id,
                            metric_id=gm.metric_id,
                            threshold=gm.threshold,
                            actual_value=float(value),
                            action_taken=gm.action,
                        )
                        await self.guardrail_repository.create_trigger(trigger)

                        new_status = (
                            ExperimentStatus.PAUSED
                            if gm.action == GuardrailAction.PAUSE
                            else ExperimentStatus.FINISHED
                        )
                        await self.experiment_repository.transition_status(
                            experiment.id, new_status
                        )
                        logger.warning(
                            "Guardrail triggered: experiment=%s metric=%s value=%.4f threshold=%.4f action=%s",
                            experiment.id, gm.metric_key, float(value), gm.threshold, gm.action.value,
                        )
                        triggered = True
                        break

                if triggered:
                    break
