from ab_test_platform.src.api.deps import get_learnings_service, require_roles
from ab_test_platform.src.application.learnings_service import LearningsService
from ab_test_platform.src.models.users import Users
from ab_test_platform.src.schemas.learnings import (
    LearningCreate,
    LearningResponse,
    LearningUpdate,
    PagedLearnings,
    SimilarLearningResponse,
)
from fastapi import APIRouter, Depends, Query
from starlette import status

router = APIRouter()

_ALL_ROLES = ["ADMIN", "EXPERIMENTER", "APPROVER", "VIEWER"]
_EDITORS = ["ADMIN", "EXPERIMENTER"]


@router.post(
    "",
    summary="Создать learning-запись для эксперимента",
    status_code=status.HTTP_201_CREATED,
    response_model=LearningResponse,
)
async def create_learning(
    body: LearningCreate,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: LearningsService = Depends(get_learnings_service),
):
    return await service.create_learning(body, current_user.id)


@router.get(
    "",
    summary="Поиск и список learnings",
    response_model=PagedLearnings,
)
async def search_learnings(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Полнотекстовый поиск"),
    feature_flag_key: str | None = Query(None),
    result: str | None = Query(None, description="ROLLOUT / ROLLBACK / NO_EFFECT"),
    tags: list[str] | None = Query(None),
    primary_metric_key: str | None = Query(None),
    platform: str | None = Query(None),
    created_by: str | None = Query(None),
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: LearningsService = Depends(get_learnings_service),
):
    return await service.search_learnings(
        page=page,
        size=size,
        query=q,
        feature_flag_key=feature_flag_key,
        result=result,
        tags=tags,
        primary_metric_key=primary_metric_key,
        platform=platform,
        created_by=created_by,
    )


@router.get(
    "/similar/{experiment_id}",
    summary="Найти похожие эксперименты",
    response_model=list[SimilarLearningResponse],
)
async def find_similar(
    experiment_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: LearningsService = Depends(get_learnings_service),
):
    return await service.find_similar(experiment_id, limit)


@router.get(
    "/{learning_id}",
    summary="Получить learning по ID",
    response_model=LearningResponse,
)
async def get_learning(
    learning_id: str,
    current_user: Users = Depends(require_roles(_ALL_ROLES)),
    service: LearningsService = Depends(get_learnings_service),
):
    return await service.get_learning(learning_id)


@router.patch(
    "/{learning_id}",
    summary="Обновить learning",
    response_model=LearningResponse,
)
async def update_learning(
    learning_id: str,
    body: LearningUpdate,
    current_user: Users = Depends(require_roles(_EDITORS)),
    service: LearningsService = Depends(get_learnings_service),
):
    return await service.update_learning(learning_id, body)
