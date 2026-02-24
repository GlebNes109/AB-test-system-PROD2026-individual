from abc import abstractmethod
from typing import Protocol


class EventsCacheRepositoryInterface(Protocol):
    """
    Интерфейс для Redis-кэша событий.

    Redis 1 (pending): ключ pending:{decision_id}:{required_type_id} — события,
    ожидающие появления зависимости.

    Redis 2 (fulfilled): ключ fulfilled:{decision_id}:{event_type_id} — принятые
    события, которые могут быть чьей-то зависимостью.
    """

    @abstractmethod
    async def set_pending(self, decision_id: str, required_type_id: str, event_data: dict) -> None:
        """Положить событие в Redis 1 (pending)."""
        ...

    @abstractmethod
    async def pop_pending(self, decision_id: str, fulfilled_type_id: str) -> dict | None:
        """Извлечь и удалить событие из Redis 1 по ключу (decision_id, required_type_id)."""
        ...

    @abstractmethod
    async def set_fulfilled(self, decision_id: str, event_type_id: str) -> None:
        """Положить запись в Redis 2 (fulfilled)."""
        ...

    @abstractmethod
    async def has_fulfilled(self, decision_id: str, event_type_id: str) -> bool:
        """Проверить, есть ли запись в Redis 2 (fulfilled)."""
        ...
