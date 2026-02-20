from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from ab_test_platform.src.domain.exceptions import EntityNotFoundError, EntityAlreadyExistsError
from ab_test_platform.src.domain.interfaces.repositories.events_repository_interface import EventsRepositoryInterface
from ab_test_platform.src.infra.database.repositories.base_repository import BaseRepository
from ab_test_platform.src.models.events import EventTypes, Events, EventsStatus


class EventsRepository(BaseRepository, EventsRepositoryInterface):
    async def create_type(self, obj: EventTypes) -> EventTypes:
        db_obj = obj
        # db_obj.id = str(uuid.uuid4())
        try:
            self.session.add(db_obj)
            await self.session.commit()
            await self.session.refresh(db_obj)
            return EventTypes.model_validate(db_obj, from_attributes=True)
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

    async def has_event_for_decision_with_type(self, decision_id: str, event_type_id: str) -> bool:
        return await self.get_event_by_decision_and_type(decision_id, event_type_id) is not None

    async def create_event(self, event: Events) -> Events:
        self.session.add(event)
        await self.session.flush()
        return event

    async def resolve_pending_events(self, decision_id: str, fulfilled_type_id: str) -> None:
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