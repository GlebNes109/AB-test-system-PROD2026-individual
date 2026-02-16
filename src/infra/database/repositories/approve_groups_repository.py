from sqlalchemy import delete

from src.domain.interfaces.repositories.approve_groups_repository_interface import ApproveGroupsRepositoryInterface
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.approver_groups import ApproverGroups, ApproverGroupMembers


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
        from sqlalchemy import select as sa_select
        from src.domain.exceptions import EntityNotFoundError
        stmt = sa_select(ApproverGroups).where(ApproverGroups.experimenter_id == experimenter_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError(f"Approver group for experimenter {experimenter_id} not found")
        return obj

    async def get_members(self, group_id: str) -> list[str]:
        from sqlalchemy import select as sa_select
        stmt = sa_select(ApproverGroupMembers.approver_id).where(ApproverGroupMembers.group_id == group_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())