from sqlalchemy import delete, select

from ab_test_platform.src.domain.exceptions import EntityNotFoundError
from ab_test_platform.src.domain.interfaces.repositories.approve_groups_repository_interface import ApproveGroupsRepositoryInterface
from ab_test_platform.src.infra.database.repositories.base_repository import BaseRepository
from ab_test_platform.src.models.approver_groups import ApproverGroups, ApproverGroupMembers


class ApproveGroupsRepository(BaseRepository, ApproveGroupsRepositoryInterface):
    async def create_members(self, approver_ids: list[str], group_id: str):
        # удаление старых участников с заменой на новых
        await self.session.execute(
            delete(ApproverGroupMembers).where(ApproverGroupMembers.group_id == group_id)
        )
        for approver_id in approver_ids:
            self.session.add(ApproverGroupMembers(group_id=group_id, approver_id=approver_id))
        await self.session.commit()

    async def get_by_experimenter_id(self, experimenter_id: str) -> ApproverGroups:
        stmt = select(ApproverGroups).where(ApproverGroups.experimenter_id == experimenter_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError(f"Approver group for experimenter {experimenter_id} not found")
        return obj

    async def get_or_create(self, experimenter_id: str, default_min_approvals: int) -> ApproverGroups:
        stmt = select(ApproverGroups).where(ApproverGroups.experimenter_id == experimenter_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return await self.create(ApproverGroups(
                experimenter_id=experimenter_id,
                min_approvals=default_min_approvals,
            ))
        return obj

    async def get_members(self, group_id: str) -> list[str]:
        stmt = select(ApproverGroupMembers.approver_id).where(ApproverGroupMembers.group_id == group_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())