from fastapi import APIRouter, Depends
from starlette import status

from ab_test_platform.src.api.deps import require_roles, get_approve_groups_service
from ab_test_platform.src.application.approve_groups_service import ApproveGroupsService
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.approver_groups import ApproverGroupCreate, ApproverGroupResponse

router = APIRouter()


@router.get(
    "/{userId}/approvers",
    summary="Получить группу аппруверов для экспериментатора",
    description="Возвращает список аппруверов и минимальный порог одобрений для данного EXPERIMENTER",
    status_code=status.HTTP_200_OK,
    response_model=ApproverGroupResponse,
)
async def get_approvers(
    userId: str,
    current_user: Users = Depends(require_roles(["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"])),
    service: ApproveGroupsService = Depends(get_approve_groups_service),
) -> ApproverGroupResponse:
    return await service.get_approve_group(userId)


@router.put(
    "/{userId}/approvers",
    summary="Назначить группу аппруверов",
    description="Назначить группу аппруверов для EXPERIMENTER. Перезаписывает текущий список.",
    status_code=status.HTTP_200_OK,
    response_model=ApproverGroupResponse,
)
async def put_approvers(
    userId: str,
    data: ApproverGroupCreate,
    current_user: Users = Depends(require_roles(["ADMIN"])),
    service: ApproveGroupsService = Depends(get_approve_groups_service),
) -> ApproverGroupResponse:
    return await service.update_approve_group(data, userId)