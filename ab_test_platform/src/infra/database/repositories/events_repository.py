from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from ab_test_platform.src.domain.exceptions import EntityNotFoundError, EntityAlreadyExistsError
from ab_test_platform.src.domain.interfaces.repositories.events_repository_interface import EventsRepositoryInterface
from ab_test_platform.src.infra.database.repositories.base_repository import BaseRepository
from ab_test_platform.src.models.events import EventTypes, Events, EventsRaw, EventsStatus


class EventsRepository(BaseRepository, EventsRepositoryInterface):
    async def create_type(self, obj: EventTypes) -> EventTypes:
        try:
            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return EventTypes.model_validate(obj, from_attributes=True)
        except IntegrityError as e:
            if e.orig.sqlstate == '23505':
                raise EntityAlreadyExistsError from e
            else:
                raise

    async def get_all_types(self, limit: int, offset: int) -> tuple[list[EventTypes], int]:
        count_stmt = select(func.count()).select_from(EventTypes)
        total = await self.session.scalar(count_stmt)

        stmt = select(EventTypes).order_by(EventTypes.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total or 0

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

    async def get_non_rejected_raw_event_by_decision_and_type(self, decision_id: str, event_type_id: str) -> EventsRaw | None:
        stmt = select(EventsRaw).where(
            EventsRaw.decision_id == decision_id,
            EventsRaw.event_type_id == event_type_id,
            EventsRaw.status != EventsStatus.REJECTED,
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_raw_event(self, raw: EventsRaw) -> EventsRaw:
        self.session.add(raw)
        await self.session.flush()
        return raw

    async def create_event(self, event: Events) -> Events:
        self.session.add(event)
        await self.session.flush()
        return event

    async def update_raw_event_status(self, raw_event_id: str, status: EventsStatus) -> None:
        await self.session.execute(
            update(EventsRaw)
            .where(EventsRaw.id == raw_event_id)
            .values(status=status)
        )

    async def commit(self) -> None:
        await self.session.commit()
