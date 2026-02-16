from fastapi import APIRouter, Depends
from starlette import status

from src.api.deps import get_decisions_service
from src.application.decisions_service import DecisionsService
from src.schemas.decisions import DecisionsResponse, Subject

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