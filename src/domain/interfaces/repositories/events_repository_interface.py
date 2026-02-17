from abc import abstractmethod
from typing import Protocol

from src.domain.interfaces.repositories.base_repository_interface import BaseRepositoryInterface
from src.models.events import EventTypes, Events


class EventsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def create_type(self, obj: EventTypes) -> EventTypes:
        ...

    @abstractmethod
    async def get_type_by_key(self, type_key: str) -> EventTypes:
        ...

    @abstractmethod
    async def get_event_by_decision_and_type(self, decision_id: str, event_type_id: str) -> Events | None:
        ...

    @abstractmethod
    async def has_event_for_decision_with_type(self, decision_id: str, event_type_id: str) -> bool:
        ...

    @abstractmethod
    async def create_event(self, event: Events) -> Events:
        ...

    @abstractmethod
    async def resolve_pending_events(self, decision_id: str, fulfilled_type_id: str) -> None:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...