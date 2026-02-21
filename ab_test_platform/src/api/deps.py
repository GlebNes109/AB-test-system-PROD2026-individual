from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.requests import Request

bearer_scheme = HTTPBearer(auto_error=False)

from ab_test_platform.src.infra.database.repositories.guardrail_repository import GuardrailRepository
from ab_test_platform.src.application.decisions_service import DecisionsService
from ab_test_platform.src.application.events_sevice import EventsService
from ab_test_platform.src.application.reports_service import ReportsService
from ab_test_platform.src.infra.database.repositories.reports_repository import ReportsRepository
from ab_test_platform.src.application.reviews_service import ReviewsService
from ab_test_platform.src.infra.database.repositories.decisions_repository import DecisionsRepository
from ab_test_platform.src.infra.database.repositories.events_repository import EventsRepository
from ab_test_platform.src.infra.database.repositories.reviews_repository import ReviewsRepository
from ab_test_platform.src.infra.database.repositories.user_repository import UserRepository
from ab_test_platform.src.infra.redis.session import get_redis_client
from ab_test_platform.src.infra.redis.repositories.events_cache_repository import EventsCacheRepository

from ab_test_platform.src.core.settings import settings
from ab_test_platform.src.infra.database.session import get_session
from ab_test_platform.src.models.approver_groups import ApproverGroups
from ab_test_platform.src.models.decisions import Decisions
from ab_test_platform.src.models.events import Events
from ab_test_platform.src.models.experiments import Experiments
from ab_test_platform.src.models.reviews import Reviews
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.application.user_service import UsersService
from ab_test_platform.src.application.auth_service import authorize_roles

from ab_test_platform.src.infra.utils.hash_creator import HashCreator
from ab_test_platform.src.infra.utils.token_creator import TokenCreator
from ab_test_platform.src.infra.database.repositories.feature_flag_repository import FeatureFlagRepository
from ab_test_platform.src.models.feature_flags import FeatureFlags
from ab_test_platform.src.application.feature_flag_service import FeatureFlagService
from ab_test_platform.src.infra.utils.dsl_parser.parser import DslParser
from ab_test_platform.src.infra.database.repositories.experiment_repository import ExperimentsRepository
from ab_test_platform.src.application.experiment_service import ExperimentService
from ab_test_platform.src.infra.database.repositories.approve_groups_repository import ApproveGroupsRepository
from ab_test_platform.src.application.approve_groups_service import ApproveGroupsService
from ab_test_platform.src.application.metrics_service import MetricsService
from ab_test_platform.src.infra.database.repositories.metrics_repository import MetricsRepository
from ab_test_platform.src.models.metrics import Metrics
from ab_test_platform.src.schemas.experiments import ExperimentResponse
from ab_test_platform.src.schemas.reviews import ReviewsRead


def get_user_repository(
    session: AsyncSession = Depends(get_session),
) -> UserRepository:
    return UserRepository(
        session=session,
        model=Users,
        read_schema=Users
    )

def get_hash_creator() -> HashCreator:
    return HashCreator()

def get_token_creator(repo: UserRepository = Depends(get_user_repository)) -> TokenCreator:
    return TokenCreator(secret_key=settings.random_secret, algorithm="HS256", repository=repo)

def get_approve_groups_repository(
    session: AsyncSession = Depends(get_session),
) -> ApproveGroupsRepository:
    return ApproveGroupsRepository(session=session,
                                   model=ApproverGroups,
                                   read_schema=ApproverGroups
                                   )

def get_user_service(
    token_creator: TokenCreator=Depends(get_token_creator),
    hash_creator: HashCreator = Depends(get_hash_creator),
    repo: UserRepository = Depends(get_user_repository),
    approve_groups_repo: ApproveGroupsRepository = Depends(get_approve_groups_repository),
    ) -> UsersService:
    return UsersService(repo, token_creator, hash_creator, approve_groups_repo)

def get_approve_groups_service(
    repo: ApproveGroupsRepository = Depends(get_approve_groups_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> ApproveGroupsService:
    return ApproveGroupsService(repo, user_repo)

def get_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    if credentials is None:
        from ab_test_platform.src.domain.exceptions import UnauthorizedError
        raise UnauthorizedError()
    return credentials.credentials

async def get_user_id(request: Request, token: str = Depends(get_token), token_creator: TokenCreator = Depends(get_token_creator)):
    user_id = await token_creator.verify_access_token(token)
    request.state.user_id = user_id
    return user_id

async def get_current_user(
    token: str = Depends(get_token),
    token_creator: TokenCreator = Depends(get_token_creator),
    repo: UserRepository = Depends(get_user_repository),
) -> Users:
    user_id = await token_creator.verify_access_token(token)
    return await repo.get(user_id)

def require_roles(allowed_roles: list[str]):
    async def dependency(current_user: Users = Depends(get_current_user)) -> Users:
        authorize_roles(current_user, allowed_roles)
        return current_user
    return dependency

def get_feature_flag_repository(
    session: AsyncSession = Depends(get_session),
) -> FeatureFlagRepository:
    return FeatureFlagRepository(
        session=session,
        model=FeatureFlags,
        read_schema=FeatureFlags,
    )

def get_feature_flag_service(
    repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
) -> FeatureFlagService:
    return FeatureFlagService(repo)

def get_dsl_parser() -> DslParser:
    return DslParser()


def get_experiment_repository(
    session: AsyncSession = Depends(get_session),
) -> ExperimentsRepository:
    return ExperimentsRepository(session=session,
                                 model=Experiments,
                                 read_schema=ExperimentResponse)

def get_metrics_repository(
    session: AsyncSession = Depends(get_session),
) -> MetricsRepository:
    return MetricsRepository(session=session, model=Metrics, read_schema=Metrics)


def get_experiment_service(
    repo: ExperimentsRepository = Depends(get_experiment_repository),
    ff_repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
    parser: DslParser = Depends(get_dsl_parser),
    metrics_repo: MetricsRepository = Depends(get_metrics_repository),
) -> ExperimentService:
    return ExperimentService(repo, ff_repo, parser, metrics_repo)

def get_reviews_repository(
    session: AsyncSession = Depends(get_session)
) -> ReviewsRepository:
    return ReviewsRepository(
        session=session,
        model=Reviews,
        read_schema=ReviewsRead)



def get_reviews_service(
        repository: ReviewsRepository = Depends(get_reviews_repository),
        user_repo: UserRepository = Depends(get_user_repository),
        experiment_repository: ExperimentsRepository = Depends(get_experiment_repository),
        approve_group_repository: ApproveGroupsRepository = Depends(get_approve_groups_repository)
) -> ReviewsService:
    return ReviewsService(repository=repository, user_repo=user_repo, experiment_repository=experiment_repository, approve_group_repository=approve_group_repository)


async def check_experimenter_access(
    experiment_id: str,
    current_user: Users = Depends(get_current_user),
    service: ExperimentService = Depends(get_experiment_service),
):
    await service.check_experimenter_create_this_experiment(experiment_id, current_user)

async def get_decisions_repository(
    session: AsyncSession = Depends(get_session)
) -> DecisionsRepository:
    return DecisionsRepository(session=session, model=Decisions, read_schema=Decisions)

async def get_decisions_service(
    experiments_repository: ExperimentsRepository = Depends(get_experiment_repository),
    decisions_repository: DecisionsRepository = Depends(get_decisions_repository),
    feature_flag_repository: FeatureFlagRepository = Depends(get_feature_flag_repository),
    parser: DslParser = Depends(get_dsl_parser)
) -> DecisionsService:
    return DecisionsService(
        experiments_repository=experiments_repository,
        decisions_repository=decisions_repository,
        feature_flag_repository=feature_flag_repository,
        parser=parser,
        cooling_period_days=settings.cooling_period_days,
        max_active_experiments=settings.max_active_experiments_per_subject,
    )

def get_events_repository(
    session: AsyncSession = Depends(get_session)
) -> EventsRepository:
    return EventsRepository(
        session=session,
        model=Events,
        read_schema=Events
    )

def get_events_cache_repository() -> EventsCacheRepository:
    return EventsCacheRepository(
        client=get_redis_client(),
        ttl_seconds=settings.redis_events_ttl_seconds,
    )

def get_metrics_service(
    repo: MetricsRepository = Depends(get_metrics_repository),
events_repository: EventsRepository = Depends(get_events_repository)
) -> MetricsService:
    return MetricsService(repo, events_repository)

def get_events_service(
    repository: EventsRepository = Depends(get_events_repository),
    decisions_repository: DecisionsRepository = Depends(get_decisions_repository),
    cache_repository: EventsCacheRepository = Depends(get_events_cache_repository),
) -> EventsService:
    return EventsService(
        repository=repository,
        decisions_repository=decisions_repository,
        cache_repository=cache_repository,
    )


def get_guardrail_repository(
    session: AsyncSession = Depends(get_session),
) -> GuardrailRepository:
    return GuardrailRepository(session=session)


def get_reports_repository(
    session: AsyncSession = Depends(get_session),
) -> ReportsRepository:
    return ReportsRepository(session=session)


def get_reports_service(
    reports_repo: ReportsRepository = Depends(get_reports_repository),
    experiment_repo: ExperimentsRepository = Depends(get_experiment_repository),
    metrics_repo: MetricsRepository = Depends(get_metrics_repository),
) -> ReportsService:
    return ReportsService(
        reports_repository=reports_repo,
        experiment_repository=experiment_repo,
        metrics_repository=metrics_repo,
    )