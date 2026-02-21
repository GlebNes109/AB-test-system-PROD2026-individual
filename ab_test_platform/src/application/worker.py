import asyncio
import logging

from ab_test_platform.src.application.guardrail_service import GuardrailService
from ab_test_platform.src.infra.database.repositories.experiment_repository import ExperimentsRepository
from ab_test_platform.src.infra.database.repositories.guardrail_repository import GuardrailRepository
from ab_test_platform.src.infra.database.repositories.metrics_repository import MetricsRepository
from ab_test_platform.src.infra.database.repositories.reports_repository import ReportsRepository
from ab_test_platform.src.infra.database.session import async_session_maker
from ab_test_platform.src.models.experiments import Experiments
from ab_test_platform.src.models.metrics import Metrics
from ab_test_platform.src.schemas.experiments import ExperimentResponse

logger = logging.getLogger(__name__)


async def guardrail_loop(interval_seconds: int = 60) -> None:
    while True:
        try:
            async with async_session_maker() as session:
                service = GuardrailService(
                    experiment_repository=ExperimentsRepository(session, Experiments, ExperimentResponse),
                    reports_repository=ReportsRepository(session),
                    metrics_repository=MetricsRepository(session, Metrics, Metrics),
                    guardrail_repository=GuardrailRepository(session),
                )
                await service.check_all_experiments()
        except Exception:
            logger.exception("Guardrail check failed")
        await asyncio.sleep(interval_seconds)


async def mv_refresh_loop(interval_seconds: int = 60) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with async_session_maker() as session:
                repo = ReportsRepository(session)
                await repo.refresh_mv()
        except Exception:
            logger.exception("MV refresh failed")
