from abc import abstractmethod
from typing import Protocol

from src.models.approver_groups import ApproverGroups


class ApproveGroupsRepositoryInterface(Protocol):
    @abstractmethod
    async def create_members(self, approver_ids: list[str], group_id: str):
        ...

    @abstractmethod
    async def get_by_experimenter_id(self, experimenter_id: str) -> ApproverGroups:
        ...

    @abstractmethod
    async def get_members(self, group_id: str) -> list[str]:
        ...