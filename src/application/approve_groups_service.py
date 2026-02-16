from src.domain.exceptions import UnsupportableContentError, EntityNotFoundError
from src.domain.interfaces.repositories.approve_groups_repository_interface import ApproveGroupsRepositoryInterface
from src.domain.interfaces.repositories.user_repository_interface import UserRepositoryInterface
from src.models.users import UserRole
from src.schemas.approver_groups import ApproverGroupCreate, ApproverGroupResponse


class ApproveGroupsService:
    def __init__(self, repository: ApproveGroupsRepositoryInterface, user_repo: UserRepositoryInterface):
        self.repository = repository
        self.user_repo = user_repo

    async def update_approve_group(self, data: ApproverGroupCreate, experimenter_id: str) -> ApproverGroupResponse:
        user = await self.user_repo.get(experimenter_id)
        if user.role != UserRole.EXPERIMENTER:
            raise UnsupportableContentError("This user is not EXPERIMENTER")

        for approver_id in data.approver_ids:
            try:
                approver = await self.user_repo.get(approver_id)
            except EntityNotFoundError:
                raise EntityNotFoundError(f"Approver with id {approver_id} not found")
            if approver.role not in (UserRole.APPROVER, UserRole.ADMIN):
                raise UnsupportableContentError(f"User {approver_id} is not APPROVER or ADMIN")

        if data.min_approvals > len(data.approver_ids):
            raise UnsupportableContentError(
                f"min_approvals ({data.min_approvals}) cannot exceed number of approvers ({len(data.approver_ids)})"
            )

        group = await self.repository.get_by_experimenter_id(experimenter_id)
        group.min_approvals = data.min_approvals
        await self.repository.update(group)
        await self.repository.create_members(data.approver_ids, group.id)

        return ApproverGroupResponse(
            experimenter_id=experimenter_id,
            approver_ids=data.approver_ids,
            min_approvals=data.min_approvals,
        )

    async def get_approve_group(self, experimenter_id: str) -> ApproverGroupResponse:
        user = await self.user_repo.get(experimenter_id)
        if user.role != UserRole.EXPERIMENTER:
            raise UnsupportableContentError("This user is not EXPERIMENTER")

        group = await self.repository.get_by_experimenter_id(experimenter_id)
        members = await self.repository.get_members(group.id)

        return ApproverGroupResponse(
            experimenter_id=experimenter_id,
            approver_ids=members,
            min_approvals=group.min_approvals,
        )