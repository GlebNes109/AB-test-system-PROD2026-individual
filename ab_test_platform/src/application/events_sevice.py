from datetime import datetime, timezone

from ab_test_platform.src.domain.exceptions import EntityNotFoundError
from ab_test_platform.src.domain.interfaces.repositories.decisions_repository_interface import DecisionsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.events_cache_repository_interface import EventsCacheRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.events_repository_interface import EventsRepositoryInterface
from ab_test_platform.src.models.events import Events, EventsRaw, EventTypes, EventsStatus, RejectedReason
from ab_test_platform.src.schemas.events import EventCreate, EventTypesCreate, EventItemResponse, EventsBatchResponse, EventTypesResponse, PagedEventTypes


class EventsService:
    def __init__(
        self,
        repository: EventsRepositoryInterface,
        decisions_repository: DecisionsRepositoryInterface,
        cache_repository: EventsCacheRepositoryInterface,
    ):
        self.repository = repository
        self.decisions_repository = decisions_repository
        self.cache_repository = cache_repository

    async def create_event_type(self, data: EventTypesCreate) -> EventTypesResponse:
        requires_event_type = None
        if data.requires_event_type is not None:
            requires_event_type = await self.repository.get_type_by_key(data.requires_event_type)

        event_type = await self.repository.create_type(EventTypes(**data.model_dump(), requires_event_id=requires_event_type.id if requires_event_type is not None else None))
        return EventTypesResponse.model_validate(event_type, from_attributes=True)

    async def get_event_types(self, page: int, size: int) -> PagedEventTypes:
        items, total = await self.repository.get_all_types(limit=size, offset=page * size)
        return PagedEventTypes(
            items=[EventTypesResponse.model_validate(et, from_attributes=True) for et in items],
            total=total,
            page=page,
            size=size,
        )

    @staticmethod
    def _validate_payload(payload: dict | None, payload_schema: dict | None) -> str | None:
        """Проверяет payload по схеме. Возвращает строку с ошибкой или None."""
        if not payload_schema:
            return None
        if not payload:
            return f"Payload is required: expected fields {list(payload_schema.keys())}"
        type_map = {
            "string": str,
            "number": (int, float),
            "bool": bool,
        }
        errors = []
        for field, expected_type in payload_schema.items():
            if field not in payload:
                errors.append(f"missing required field '{field}'")
                continue
            py_type = type_map.get(expected_type)
            if py_type and not isinstance(payload[field], py_type):
                errors.append(f"field '{field}' must be {expected_type}, got {type(payload[field]).__name__}")
        return "; ".join(errors) if errors else None

    async def _process_single_event(self, event_data: EventCreate, index: int) -> EventItemResponse:
        now = datetime.now(timezone.utc)
        occurred_at = event_data.occurred_at or now

        # 1. Валидация типа события
        try:
            event_type = await self.repository.get_type_by_key(event_data.event_type)
        except EntityNotFoundError:
            raw = EventsRaw(
                event_type_id="unknown",
                decision_id=event_data.decision_id,
                subject_id=None,
                payload=event_data.payload,
                status=EventsStatus.REJECTED,
                rejected_reason=RejectedReason.INVALID_EVENT_TYPE,
                occurred_at=occurred_at,
                received_at=now,
            )
            await self.repository.create_raw_event(raw)
            return EventItemResponse(
                index=index,
                status_code=404,
                error=f"Event type '{event_data.event_type}' not found",
            )

        # Валидация payload по схеме типа события
        payload_error = self._validate_payload(event_data.payload, event_type.payload_schema)
        if payload_error:
            raw = EventsRaw(
                event_type_id=event_type.id,
                decision_id=event_data.decision_id,
                subject_id=None,
                payload=event_data.payload,
                status=EventsStatus.REJECTED,
                rejected_reason=RejectedReason.INVALID_PAYLOAD,
                occurred_at=occurred_at,
                received_at=now,
            )
            await self.repository.create_raw_event(raw)
            return EventItemResponse(
                index=index,
                status_code=422,
                error=f"Payload validation failed: {payload_error}",
            )

        # 2. Валидация decision_id — берём subject_id отсюда
        try:
            decision = await self.decisions_repository.get(event_data.decision_id)
        except EntityNotFoundError:
            raw = EventsRaw(
                event_type_id=event_type.id,
                decision_id=event_data.decision_id,
                subject_id=None,
                payload=event_data.payload,
                status=EventsStatus.REJECTED,
                rejected_reason=RejectedReason.INVALID_DECISION_ID,
                occurred_at=occurred_at,
                received_at=now,
            )
            await self.repository.create_raw_event(raw)
            return EventItemResponse(
                index=index,
                status_code=404,
                error=f"Decision '{event_data.decision_id}' not found",
            )

        subject_id = decision.subject_id

        # 3. Проверка на дублирование в events_raw (RECEIVED или PENDING) —
        #    покрывает как принятые, так и ожидающие экспозиции события
        existing_raw = await self.repository.get_non_rejected_raw_event_by_decision_and_type(
            event_data.decision_id, event_type.id
        )
        if existing_raw is not None:
            raw = EventsRaw(
                event_type_id=event_type.id,
                decision_id=event_data.decision_id,
                subject_id=subject_id,
                payload=event_data.payload,
                status=EventsStatus.REJECTED,
                rejected_reason=RejectedReason.DUPLICATE,
                occurred_at=occurred_at,
                received_at=now,
            )
            await self.repository.create_raw_event(raw)
            return EventItemResponse(
                index=index,
                status_code=409,
                error=f"Duplicate event: decision_id={event_data.decision_id}, event_type={event_data.event_type}",
            )

        # 4. Обработка в зависимости от наличия зависимости у типа события
        if event_type.requires_event_id is None:
            return await self._process_independent_event(event_data, event_type, subject_id, index, now, occurred_at)
        else:
            return await self._process_dependent_event(event_data, event_type, subject_id, index, now, occurred_at)

    async def _process_independent_event(
        self,
        event_data: EventCreate,
        event_type: EventTypes,
        subject_id: str,
        index: int,
        now: datetime,
        occurred_at: datetime,
    ) -> EventItemResponse:
        """Событие без зависимости (requires_event_type пустое)."""

        # Записать в events_raw как принятое
        raw = EventsRaw(
            event_type_id=event_type.id,
            decision_id=event_data.decision_id,
            subject_id=subject_id,
            payload=event_data.payload,
            status=EventsStatus.RECEIVED,
            occurred_at=occurred_at,
            received_at=now,
        )
        await self.repository.create_raw_event(raw)

        # Записать в events (принятые)
        event = Events(
            event_type_id=event_type.id,
            decision_id=event_data.decision_id,
            subject_id=subject_id,
            payload=event_data.payload,
            occurred_at=occurred_at,
            received_at=now,
        )
        created_event = await self.repository.create_event(event)

        # Добавить в Redis 2 (fulfilled) — это событие может быть чьей-то зависимостью
        await self.cache_repository.set_fulfilled(event_data.decision_id, event_type.id)

        # Проверить Redis 1 (pending): есть ли события, которые ждали именно этого типа
        pending_data = await self.cache_repository.pop_pending(
            event_data.decision_id, event_type.id
        )
        if pending_data is not None:
            # Дождавшееся событие — записать в events (принятые)
            resolved_event = Events(
                event_type_id=pending_data["event_type_id"],
                decision_id=pending_data["decision_id"],
                subject_id=pending_data["subject_id"],
                payload=pending_data.get("payload"),
                occurred_at=datetime.fromisoformat(pending_data["occurred_at"]),
                received_at=datetime.fromisoformat(pending_data["received_at"]),
            )
            await self.repository.create_event(resolved_event)
            # Обновить статус в events_raw: PENDING → RECEIVED
            await self.repository.update_raw_event_status(
                pending_data["raw_id"], EventsStatus.RECEIVED
            )

        return EventItemResponse(
            index=index,
            status_code=201,
            event_id=created_event.id,
            event_status=EventsStatus.RECEIVED,
        )

    async def _process_dependent_event(
        self,
        event_data: EventCreate,
        event_type: EventTypes,
        subject_id: str,
        index: int,
        now: datetime,
        occurred_at: datetime,
    ) -> EventItemResponse:
        """Событие с зависимостью (requires_event_type не пустое)."""

        # Проверить Redis 2: пришла ли уже зависимость
        has_dependency = await self.cache_repository.has_fulfilled(
            event_data.decision_id, event_type.requires_event_id
        )

        if has_dependency:
            # Зависимость уже есть — принять сразу
            raw = EventsRaw(
                event_type_id=event_type.id,
                decision_id=event_data.decision_id,
                subject_id=subject_id,
                payload=event_data.payload,
                status=EventsStatus.RECEIVED,
                occurred_at=occurred_at,
                received_at=now,
            )
            await self.repository.create_raw_event(raw)

            event = Events(
                event_type_id=event_type.id,
                decision_id=event_data.decision_id,
                subject_id=subject_id,
                payload=event_data.payload,
                occurred_at=occurred_at,
                received_at=now,
            )
            created_event = await self.repository.create_event(event)

            return EventItemResponse(
                index=index,
                status_code=201,
                event_id=created_event.id,
                event_status=EventsStatus.RECEIVED,
            )
        else:
            # Зависимость ещё не пришла, положить в pending
            raw = EventsRaw(
                event_type_id=event_type.id,
                decision_id=event_data.decision_id,
                subject_id=subject_id,
                payload=event_data.payload,
                status=EventsStatus.PENDING,
                occurred_at=occurred_at,
                received_at=now,
            )
            created_raw = await self.repository.create_raw_event(raw)

            # Сохранить в Redis 1 (pending): ключ = required_type.id (UUID зависимости)
            await self.cache_repository.set_pending(
                event_data.decision_id,
                event_type.requires_event_id,
                {
                    "raw_id": created_raw.id,
                    "event_type_id": event_type.id,
                    "decision_id": event_data.decision_id,
                    "subject_id": subject_id,
                    "payload": event_data.payload,
                    "occurred_at": occurred_at.isoformat(),
                    "received_at": now.isoformat(),
                },
            )

            return EventItemResponse(
                index=index,
                status_code=202,
                event_id=created_raw.id,
                event_status=EventsStatus.PENDING,
            )

    async def process_batch(self, events: list[EventCreate]) -> EventsBatchResponse:
        results: list[EventItemResponse] = []

        for i, event_data in enumerate(events):
            try:
                item = await self._process_single_event(event_data, i)
                if item.status is None and item.error is not None:
                    item.event_status = EventsStatus.REJECTED
                results.append(item)
            except Exception as e:
                results.append(EventItemResponse(
                    index=i,
                    status_code=500,
                    error=str(e),
                ))

        await self.repository.commit()
        return EventsBatchResponse(results=results)
