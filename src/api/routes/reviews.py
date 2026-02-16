from fastapi import Depends, Query, APIRouter
from starlette import status

from src.api.deps import require_roles, get_reviews_service
from src.application.reviews_service import ReviewsService
from src.models.users import Users
from src.schemas.reviews import ReviewsCreate

router = APIRouter()


@router.post(
    "/experiments/{ExperimentId}/review",
    summary="Провести ревью",
    description="Проведение ревью",
    status_code=status.HTTP_200_OK,
)
async def review_experiment(
    ExperimentId: str,
    review: ReviewsCreate,
    current_user: Users = Depends(require_roles(["ADMIN", "APPROVER"])),
    service: ReviewsService = Depends(get_reviews_service),
):
    return await service.create_review(review, ExperimentId, current_user.id)


@router.post(
    "/reviews/my",
    summary="Получить все свои ревью",
    description="Получить все свои результаты ревью",
    status_code=status.HTTP_200_OK,
)
async def review_experiment(
        ExperimentId: str,
        review: ReviewsCreate,
        current_user: Users = Depends(require_roles(["ADMIN", "APPROVER"])),
        service: ReviewsService = Depends(get_reviews_service),
):
    return await service.create_review(review, ExperimentId, current_user)

    # page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),




