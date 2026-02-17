from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound

from src.domain.exceptions import EntityNotFoundError
from src.domain.interfaces.repositories.events_repository_interface import EventsRepositoryInterface
from src.infra.database.repositories.base_repository import BaseRepository
from src.models.events import EventTypes, Events, EventsStatus


class EventsRepository(BaseRepository, EventsRepositoryInterface):
    async def create_type(self, obj: EventTypes) -> EventTypes:
        return await self.create(obj)

    async def get_type_by_key(self, type_key: str) -> EventTypes:
        stmt = select(EventTypes).where(EventTypes.type == type_key)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise EntityNotFoundError(f"Event type '{type_key}' not found")
        return obj

    async def get_event_by_decision_and_type(self, decision_id: str, event_type_id: str) -> Events | None:
        stmt = select(Events).where(
            Events.decision_id == decision_id,
            Events.event_type_id == event_type_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_event_for_decision_with_type(self, decision_id: str, event_type_id: str) -> bool:
        return await self.get_event_by_decision_and_type(decision_id, event_type_id) is not None

    async def create_event(self, event: Events) -> Events:
        self.session.add(event)
        await self.session.flush()
        return event

    async def resolve_pending_events(self, decision_id: str, fulfilled_type_id: str) -> None:
        """When a new event arrives, promote PENDING events that were waiting for this type."""
        # Find event types that require the fulfilled type
        type_stmt = select(EventTypes.id).where(EventTypes.requires_event_id == fulfilled_type_id)
        type_result = await self.session.execute(type_stmt)
        dependent_type_ids = [row[0] for row in type_result.all()]

        if not dependent_type_ids:
            return

        await self.session.execute(
            update(Events)
            .where(
                Events.decision_id == decision_id,
                Events.event_type_id.in_(dependent_type_ids),
                Events.status == EventsStatus.PENDING,
            )
            .values(status=EventsStatus.RECEIVED)
        )

    async def commit(self) -> None:
        await self.session.commit()