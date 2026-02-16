from src.core.exceptions import EntityNotFoundError, UnauthorizedError, UserInactiveError
from src.infra.database.repositories.approve_groups_repository import ApproveGroupsRepository
from src.infra.database.repositories.base_repository import SortOrder
from src.infra.database.repositories.user_repository import UserRepository
from src.models.approver_groups import ApproverGroups
from src.schemas.auth import AuthResponse
from src.models.users import Users, UserRole

from src.schemas.users import UsersResponse, UsersUpdate, PagedUsers
from src.infra.utils.hash_creator import HashCreator
from src.infra.utils.token_creator import TokenCreator


class UsersService:
    def __init__(self, repository: UserRepository, token_creator: TokenCreator, hash_creator: HashCreator, approve_groups_repository: ApproveGroupsRepository):
        self.repository = repository
        self.approve_groups_repository = approve_groups_repository
        self.token_creator = token_creator
        self.hash_creator = hash_creator

    async def create_user(self, user_create) -> UsersResponse:
        password_hash = await self.hash_creator.create_hash(user_create.password)

        user = Users(email=user_create.email,
                     password_hash=password_hash,
                     role=user_create.role)

        user_read = await self.repository.create(user)

        if user_create.role == UserRole.EXPERIMENTER:
            # fallback для экспериментатора - создание пустой аппрувер группы с дефолтным порогом аппрувов (min_approvals=1)
            await self.approve_groups_repository.create(ApproverGroups(experimenter_id=user_read.id))

        return UsersResponse.model_validate(user_read, from_attributes=True)

    async def sign_in_user(self, user) -> AuthResponse:
        try:
            user_read = await self.repository.get_by_email(user.email)
        except EntityNotFoundError:
            raise UnauthorizedError("Токен отсутствует или невалиден")

        if user_read.password_hash == await self.hash_creator.create_hash(user.password):
            access_token, expires_in = await self.token_creator.create_access_token(user_read.id)
            return AuthResponse(
            accessToken=access_token,
            expiresIn=expires_in,
            user=UsersResponse.model_validate(user_read, from_attributes=True)
            )


        else:
            raise UnauthorizedError("Токен отсутствует или невалиден")

    async def get_users(self, page, size):
        offset = page * size
        limit = size
        users, total = await self.repository.get_all(limit, offset, "createdAt", order=SortOrder.ASC)
        return PagedUsers(
            items=[UsersResponse.model_validate(user, from_attributes=True) for user in users],
            total=total,
            page=page,
            size=size)

    async def get_user(self, user_id: str) -> UsersResponse:
        user_read = await self.repository.get(user_id)
        return UsersResponse.model_validate(user_read, from_attributes=True)

    async def update_user(self, user_update: UsersUpdate, user_id) -> UsersResponse:
        user_read = await self.repository.update(Users(id=user_id, **user_update.model_dump()))
        return UsersResponse.model_validate(user_read, from_attributes=True)
