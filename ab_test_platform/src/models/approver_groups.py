import uuid

from sqlmodel import Field, SQLModel


class ApproverGroups(SQLModel, table=True):
    __tablename__ = "approver_groups"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    experimenter_id: str = Field()
    min_approvals: int = Field(default=1)

class ApproverGroupMembers(SQLModel, table=True):
    __tablename__ = "approver_group_members"

    group_id: str = Field(primary_key=True)
    approver_id: str = Field(primary_key=True)


