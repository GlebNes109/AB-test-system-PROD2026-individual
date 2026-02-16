from abc import abstractmethod
from typing import Protocol

from src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from src.models.approver_groups import ApproverGroups


class ApproveGroupsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def create_members(self, approver_ids: list[str], group_id: str):
        ...

    @abstractmethod
    async def get_by_experimenter_id(self, experimenter_id: str) -> ApproverGroups:
        ...

    @abstractmethod
    async def get_members(self, group_id: str) -> list[str]:
        ...

    @abstractmethod
    async def get_or_create(self, experimenter_id: str, default_min_approvals: int) -> ApproverGroups:
        ...