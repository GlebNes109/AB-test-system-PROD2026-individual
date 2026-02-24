from ab_test_platform.src.domain.exceptions import EntityNotFoundError, UnauthorizedError
from ab_test_platform.src.domain.interfaces.hash_creator_interface import HashCreatorInterface
from ab_test_platform.src.domain.interfaces.repositories.approve_groups_repository_interface import (
    ApproveGroupsRepositoryInterface,
)
from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import SortOrder
from ab_test_platform.src.domain.interfaces.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from ab_test_platform.src.domain.interfaces.token_creator_interface import TokenCreatorInterface
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.auth import AuthResponse
from ab_test_platform.src.schemas.users import PagedUsers, UsersResponse, UsersUpdate


class UsersService:
    def __init__(
        self,
        repository: UserRepositoryInterface,
        token_creator: TokenCreatorInterface,
        hash_creator: HashCreatorInterface,
        approve_groups_repository: ApproveGroupsRepositoryInterface,
    ):
        self.repository = repository
        self.approve_groups_repository = approve_groups_repository
        self.token_creator = token_creator
        self.hash_creator = hash_creator

    async def create_user(self, user_create) -> UsersResponse:
        password_hash = await self.hash_creator.create_hash(user_create.password)

        user = Users(email=user_create.email, password_hash=password_hash, role=user_create.role)

        user_read = await self.repository.create(user)

        return UsersResponse.model_validate(user_read, from_attributes=True)

    async def sign_in_user(self, user) -> AuthResponse:
        try:
            user_read = await self.repository.get_by_email(user.email)
        except EntityNotFoundError:
            raise UnauthorizedError("Токен отсутствует или невалиден") from None

        if user_read.password_hash == await self.hash_creator.create_hash(user.password):
            access_token, expires_in = await self.token_creator.create_access_token(user_read.id)
            return AuthResponse(
                accessToken=access_token,
                expiresIn=expires_in,
                user=UsersResponse.model_validate(user_read, from_attributes=True),
            )

        else:
            raise UnauthorizedError("Токен отсутствует или невалиден")

    async def get_users(self, page, size):
        offset = page * size
        limit = size
        users, total = await self.repository.get_all(
            limit, offset, "createdAt", order=SortOrder.ASC
        )
        return PagedUsers(
            items=[UsersResponse.model_validate(user, from_attributes=True) for user in users],
            total=total,
            page=page,
            size=size,
        )

    async def get_user(self, user_id: str) -> UsersResponse:
        user_read = await self.repository.get(user_id)
        return UsersResponse.model_validate(user_read, from_attributes=True)

    async def update_user(self, user_update: UsersUpdate, user_id) -> UsersResponse:
        user_read = await self.repository.update(Users(id=user_id, **user_update.model_dump()))
        return UsersResponse.model_validate(user_read, from_attributes=True)
