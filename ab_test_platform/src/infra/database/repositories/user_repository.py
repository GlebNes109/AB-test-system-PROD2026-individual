from ab_test_platform.src.domain.exceptions import EntityNotFoundError
from ab_test_platform.src.domain.interfaces.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from ab_test_platform.src.infra.database.repositories.base_repository import BaseRepository
from ab_test_platform.src.models.users import Users
from sqlalchemy import select


class UserRepository(BaseRepository, UserRepositoryInterface):
    async def get_by_email(self, email: str) -> Users:
        stmt = select(self.model).where(self.model.email == email)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError
        return self.read_schema.model_validate(obj, from_attributes=True)