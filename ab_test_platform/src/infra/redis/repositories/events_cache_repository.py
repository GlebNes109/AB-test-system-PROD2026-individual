import json

import redis.asyncio as aioredis
from ab_test_platform.src.domain.interfaces.repositories.events_cache_repository_interface import (
    EventsCacheRepositoryInterface,
)

_PENDING_PREFIX = "pending"
_FULFILLED_PREFIX = "fulfilled"


class EventsCacheRepository(EventsCacheRepositoryInterface):
    def __init__(self, client: aioredis.Redis, ttl_seconds: int):
        self.client = client
        self.ttl = ttl_seconds

    def _pending_key(self, decision_id: str, required_type_id: str) -> str:
        return f"{_PENDING_PREFIX}:{decision_id}:{required_type_id}"

    def _fulfilled_key(self, decision_id: str, event_type_id: str) -> str:
        return f"{_FULFILLED_PREFIX}:{decision_id}:{event_type_id}"

    async def set_pending(self, decision_id: str, required_type_id: str, event_data: dict) -> None:
        key = self._pending_key(decision_id, required_type_id)
        await self.client.set(key, json.dumps(event_data), ex=self.ttl)

    async def pop_pending(self, decision_id: str, fulfilled_type_id: str) -> dict | None:
        key = self._pending_key(decision_id, fulfilled_type_id)
        value = await self.client.getdel(key)
        if value is None:
            return None
        return json.loads(value)

    async def set_fulfilled(self, decision_id: str, event_type_id: str) -> None:
        key = self._fulfilled_key(decision_id, event_type_id)
        await self.client.set(key, "1", ex=self.ttl)

    async def has_fulfilled(self, decision_id: str, event_type_id: str) -> bool:
        key = self._fulfilled_key(decision_id, event_type_id)
        return await self.client.exists(key) > 0
