from abc import abstractmethod
from typing import Protocol

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import (
    BaseRepositoryInterface,
)
from ab_test_platform.src.models.events import Events, EventsRaw, EventsStatus, EventTypes


class EventsRepositoryInterface(BaseRepositoryInterface, Protocol):
    @abstractmethod
    async def create_type(self, obj: EventTypes) -> EventTypes: ...

    @abstractmethod
    async def get_type_by_key(self, type_key: str) -> EventTypes: ...

    @abstractmethod
    async def get_all_types(self, limit: int, offset: int) -> tuple[list[EventTypes], int]: ...

    @abstractmethod
    async def get_event_by_decision_and_type(
        self, decision_id: str, event_type_id: str
    ) -> Events | None:  # поиск дубликатов в events
        ...

    @abstractmethod
    async def get_non_rejected_raw_event_by_decision_and_type(
        self, decision_id: str, event_type_id: str
    ) -> EventsRaw | None:  # поиск дубликатов в events_raw
        ...

    @abstractmethod
    async def create_raw_event(self, raw: EventsRaw) -> EventsRaw: ...

    @abstractmethod
    async def create_event(self, event: Events) -> Events: ...

    @abstractmethod
    async def update_raw_event_status(self, raw_event_id: str, status: EventsStatus) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...
