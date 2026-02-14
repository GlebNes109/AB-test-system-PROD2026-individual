from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.requests import Request
from src.infra.database.repositories.user_repository import UserRepository

from src.core.settings import settings
from src.infra.database.session import get_session
from src.models.users import Users
from src.application.user_service import UsersService
from src.application.auth_service import authorize_roles

from src.infra.utils.hash_creator import HashCreator
from src.infra.utils.token_creator import TokenCreator
from src.infra.database.repositories.feature_flag_repository import FeatureFlagRepository
from src.models.feature_flags import FeatureFlags
from src.application.feature_flag_service import FeatureFlagService
from src.infra.utils.dsl_parser.parser import DslParser
from src.infra.database.repositories.experiment_repository import ExperimentRepository
from src.application.experiment_service import ExperimentService


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

def get_user_service(
    token_creator: TokenCreator=Depends(get_token_creator),
    hash_creator: HashCreator = Depends(get_hash_creator),
    repo: UserRepository = Depends(get_user_repository),
    ) -> UsersService:
    return UsersService(repo, token_creator, hash_creator)

def get_token(request: Request):
    headers = request.headers
    a = str(headers.get("Authorization"))
    return a[7:]

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
) -> ExperimentRepository:
    return ExperimentRepository(session=session)


def get_experiment_service(
    repo: ExperimentRepository = Depends(get_experiment_repository),
    ff_repo: FeatureFlagRepository = Depends(get_feature_flag_repository)
) -> ExperimentService:
    return ExperimentService(repo, ff_repo)








