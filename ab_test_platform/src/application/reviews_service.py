from ab_test_platform.src.domain.exceptions import AccessDeniedError, ConflictError
from ab_test_platform.src.domain.interfaces.repositories.approve_groups_repository_interface import ApproveGroupsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.reviews_repository_interface import ReviewsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.user_repository_interface import UserRepositoryInterface
from ab_test_platform.src.models.experiments import ExperimentStatus
from ab_test_platform.src.models.reviews import Reviews, ReviewDecisions
from ab_test_platform.src.models.users import UserRole
from ab_test_platform.src.schemas.reviews import ReviewsCreate, PagedReviews


class ReviewsService:
    def __init__(self, repository: ReviewsRepositoryInterface, user_repo: UserRepositoryInterface, experiment_repository: ExperimentsRepositoryInterface, approve_group_repository: ApproveGroupsRepositoryInterface):
        self.repository = repository
        self.user_repo = user_repo
        self.experiment_repository = experiment_repository
        self.approve_group_repository = approve_group_repository

    async def create_review(self, data: ReviewsCreate, experiment_id, reviewer_id):
        # проверка, что reviewer_id находится в группе ревью этого эксперимента
        experiment = await self.experiment_repository.get(experiment_id)
        experiment_creator_id = experiment.created_by
        experimenter = await self.user_repo.get(experiment_creator_id)
        default_min = 0 if experimenter.role == UserRole.ADMIN else 1
        approve_group = await self.approve_group_repository.get_or_create(experiment_creator_id, default_min)
        members = await self.approve_group_repository.get_members(group_id=approve_group.id)

        # пустая группа апруверов означает, что аппрув может делать кто угодно
        if members and reviewer_id not in members:
            raise AccessDeniedError("this user is not in experimenter approvers group")

        review = await self.repository.create(Reviews(experiment_id=experiment_id,
                                             reviewer_id=reviewer_id,
                                             **data.model_dump()))

        if experiment.status != ExperimentStatus.REVIEW:
            raise ConflictError(f"this experiment is not on review now. Actual status - {experiment.status}")

        if data.decision == ReviewDecisions.ACCEPT:
            approved_count = await self.repository.count_by_decision(experiment_id, ReviewDecisions.ACCEPT)
            if approved_count >= approve_group.min_approvals:
                await self.experiment_repository.transition_status(experiment_id, ExperimentStatus.APPROVED)

        if data.decision == ReviewDecisions.REJECT:
            await self.experiment_repository.transition_status(experiment_id, ExperimentStatus.REJECTED)

        if data.decision == ReviewDecisions.REQUEST_IMPROVEMENTS:
            await self.experiment_repository.transition_status(experiment_id, ExperimentStatus.DRAFT)

        return review

    async def get_reviews(self, page, size, experimenter_id: str | None = None, reviewer_id: str | None = None):
        offset = page * size
        limit = size
        read_reviews, total = await self.repository.get_all_with_params(
            limit=limit, offset=offset,
            experimenter_id=experimenter_id,
            reviewer_id=reviewer_id,
        )
        return PagedReviews(
            items=read_reviews,
            total=total,
            page=page,
            size=size,
        )