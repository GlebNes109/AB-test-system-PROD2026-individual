from ab_test_platform.src.domain.exceptions import EntityNotFoundError
from ab_test_platform.src.domain.interfaces.repositories.feature_flag_repository_interface import (
    FeatureFlagRepositoryInterface,
)
from ab_test_platform.src.infra.database.repositories.base_repository import BaseRepository
from sqlalchemy import select, update


class FeatureFlagRepository(BaseRepository, FeatureFlagRepositoryInterface):
    async def get_by_key(self, key: str):
        stmt = select(self.model).where(self.model.key == key)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError("Feature flag not found")
        return self.read_schema.model_validate(obj, from_attributes=True)

    async def update_default_value(self, key: str, default_value: str):
        await self.get_by_key(key)
        await self.session.execute(
            update(self.model)
            .where(self.model.key == key)
            .values(default_value=default_value)
        )
        await self.session.commit()
        return await self.get_by_key(key)
