
from ab_test_platform.src.domain.exceptions import UnsupportableContentError
from pydantic import BaseModel, field_validator


class ApproverGroupCreate(BaseModel):
    approver_ids: list[str]
    min_approvals: int = 1

    @field_validator("min_approvals")
    @classmethod
    def validate_min_approvals(cls, v: int) -> int:
        if v < 1:
            raise UnsupportableContentError("min_approvals must be at least 1")
        return v


class ApproverGroupResponse(BaseModel):
    experimenter_id: str
    approver_ids: list[str]
    min_approvals: int