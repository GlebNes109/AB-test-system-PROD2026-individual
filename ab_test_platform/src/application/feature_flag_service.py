from ab_test_platform.src.domain.interfaces.repositories.feature_flag_repository_interface import (
    FeatureFlagRepositoryInterface,
)
from ab_test_platform.src.infra.database.repositories.base_repository import SortOrder
from ab_test_platform.src.models.feature_flags import FeatureFlags, validate_value_for_flag_type
from ab_test_platform.src.schemas.feature_flags import (
    FeatureFlagCreate,
    FeatureFlagResponse,
    FeatureFlagUpdateDefault,
    PagedFeatureFlags,
)


class FeatureFlagService:
    def __init__(self, repository: FeatureFlagRepositoryInterface):
        self.repository = repository

    async def create_flag(self, flag_create: FeatureFlagCreate, created_by: str) -> FeatureFlagResponse:
        validated_default = validate_value_for_flag_type(
            flag_create.default_value, flag_create.type, "default_value"
        )
        flag = FeatureFlags(
            key=flag_create.key,
            type=flag_create.type,
            default_value=validated_default,
            description=flag_create.description,
            created_by=created_by,
        )
        flag_read = await self.repository.create(flag)
        return FeatureFlagResponse.model_validate(flag_read, from_attributes=True)

    async def get_flag_by_key(self, key: str) -> FeatureFlagResponse:
        flag_read = await self.repository.get_by_key(key)
        return FeatureFlagResponse.model_validate(flag_read, from_attributes=True)

    async def get_flag_by_id(self, id: str) -> FeatureFlagResponse:
        flag_read = await self.repository.get(id)
        return FeatureFlagResponse.model_validate(flag_read, from_attributes=True)

    async def get_flags(self, page: int, size: int) -> PagedFeatureFlags:
        offset = page * size
        flags, total = await self.repository.get_all(size, offset, "createdAt", order=SortOrder.ASC)
        return PagedFeatureFlags(
            items=[FeatureFlagResponse.model_validate(f, from_attributes=True) for f in flags],
            total=total,
            page=page,
            size=size,
        )

    async def update_default_value(self, key: str, update_data: FeatureFlagUpdateDefault) -> FeatureFlagResponse:
        flag = await self.repository.get_by_key(key)
        validated = validate_value_for_flag_type(
            update_data.default_value, flag.type, "default_value"
        )
        flag_read = await self.repository.update_default_value(key, validated)
        return FeatureFlagResponse.model_validate(flag_read, from_attributes=True)

    async def delete(self, key: str):
        flag = await self.repository.get_by_key(key)
        await self.repository.delete(flag.id)
