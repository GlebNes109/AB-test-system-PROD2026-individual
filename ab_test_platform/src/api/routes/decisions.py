from ab_test_platform.src.api.deps import get_decisions_service
from ab_test_platform.src.application.decisions_service import DecisionsService
from ab_test_platform.src.schemas.decisions import DecisionsResponse, Subject
from fastapi import APIRouter, Depends
from starlette import status

router = APIRouter()


@router.post(
    "/decision",
    summary="Отображение флагов",
    description="Список флагов для отображения",
    status_code=status.HTTP_200_OK,
    response_model=list[DecisionsResponse],
)
async def make_ab_decision(
    data: Subject,
    service: DecisionsService = Depends(get_decisions_service),
) -> list[DecisionsResponse]:
    return await service.make_decision(data)
