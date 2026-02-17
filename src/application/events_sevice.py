from datetime import datetime, timezone

from src.domain.exceptions import EntityNotFoundError
from src.domain.interfaces.repositories.decisions_repository_interface import DecisionsRepositoryInterface
from src.domain.interfaces.repositories.events_repository_interface import EventsRepositoryInterface
from src.models.events import Events, EventTypes, EventsStatus
from src.schemas.events import EventCreate, EventTypesCreate, EventItemResponse, EventsBatchResponse, EventTypesResponse


class EventsService:
    def __init__(
        self,
        repository: EventsRepositoryInterface,
        decisions_repository: DecisionsRepositoryInterface,
    ):
        self.repository = repository
        self.decisions_repository = decisions_repository

    async def create_event_type(self, data: EventTypesCreate) -> EventTypesResponse:
        if data.requires_event_type is not None:
            # Валидация что requires_event_key есть
            await self.repository.get_type_by_key(data.requires_event_type)

        event_type = await self.repository.create_type(EventTypes(**data.model_dump()))
        return EventTypesResponse.model_validate(event_type, from_attributes=True)

    async def _process_single_event(self, event_data: EventCreate) -> EventItemResponse | None:
        # 1. Получить event_type
        event_type = await self.repository.get_type_by_key(event_data.event_type)

        # 2. Валидация что decision существует
        await self.decisions_repository.get(event_data.decision_id)

        # 3. Проверка на дублирование (decision_id + event type)
        existing = await self.repository.get_event_by_decision_and_type(
            event_data.decision_id, event_type.id
        )
        if existing is not None:
            return EventItemResponse(
                index=0,
                status_code=409,
                error=f"Duplicate event: decision_id={event_data.decision_id}, event_type={event_data.event_type}",
            )

        # 4. Определение статуса
        if event_type.requires_event_id is not None:
            # Проверка, было ли уже получено зависимое событие
            required_type = await self.repository.get_type_by_key(event_type.requires_event_id)
            has_required = await self.repository.has_event_for_decision_with_type(
                event_data.decision_id, required_type.id
            )
            status = EventsStatus.RECEIVED if has_required else EventsStatus.PENDING
        else:
            status = EventsStatus.RECEIVED

        # 5. Создание ивента
        now = datetime.now(timezone.utc)
        event = Events(
            event_type_id=event_type.id,
            decision_id=event_data.decision_id,
            subject_id=event_data.subject_id,
            payload=event_data.payload,
            status=status,
            occurred_at=event_data.occurred_at or now,
            received_at=now,
        )
        created = await self.repository.create_event(event)

        # 6. Обновление других ивентов, которые в статусе pending
        await self.repository.resolve_pending_events(event_data.decision_id, event_type.id)

        return EventItemResponse(
            index=0,
            status_code=201,
            event_id=created.id,
            event_status=created.status,
        )

    async def process_batch(self, events: list[EventCreate]) -> EventsBatchResponse:
        results: list[EventItemResponse] = []

        for i, event_data in enumerate(events):
            try:
                item = await self._process_single_event(event_data)
                item.index = i
                results.append(item)
            except EntityNotFoundError as e:
                results.append(EventItemResponse(
                    index=i,
                    status_code=404,
                    error=e.message,
                ))
            except Exception as e:
                results.append(EventItemResponse(
                    index=i,
                    status_code=500,
                    error=str(e),
                ))

        await self.repository.commit()
        return EventsBatchResponse(results=results)