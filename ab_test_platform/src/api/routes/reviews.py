from fastapi import Depends, Query, APIRouter
from starlette import status

from ab_test_platform.src.api.deps import require_roles, get_reviews_service
from ab_test_platform.src.application.reviews_service import ReviewsService
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.reviews import ReviewsCreate, PagedReviews

router = APIRouter()


@router.post(
    "/experiments/{experiment_id}/review",
    summary="Провести ревью",
    description="Проведение ревью",
    status_code=status.HTTP_200_OK,
)
async def create_review(
    experiment_id: str,
    review: ReviewsCreate,
    current_user: Users = Depends(require_roles(["ADMIN", "APPROVER"])),
    service: ReviewsService = Depends(get_reviews_service),
):
    return await service.create_review(review, experiment_id, current_user.id)


@router.get(
    "/reviews/my",
    summary="Получить все свои ревью",
    description="Возвращает постраничный список ревью, оставленных текущим пользователем.",
    status_code=status.HTTP_200_OK,
    response_model=PagedReviews,
)
async def get_my_reviews(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_user: Users = Depends(require_roles(["ADMIN", "APPROVER"])),
    service: ReviewsService = Depends(get_reviews_service),
):
    return await service.get_reviews(page, size, reviewer_id=current_user.id)

