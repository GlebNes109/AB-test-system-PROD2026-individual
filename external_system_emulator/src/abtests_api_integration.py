import httpx
from typing import Any


class ABTestClient:
    """HTTP-клиент для взаимодействия с AB-test платформой."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def get_decision(
        self, subject_id: str, flag_keys: list[str]
    ) -> list[dict[str, Any]]:
        """POST /api/v1/decision — получить решение для пользователя."""
        resp = await self._client.post(
            "/api/v1/decision",
            json={
                "id": subject_id,
                "subject_attr": {},
                "flags_keys": flag_keys,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def send_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """POST /api/v1/events/batch — отправить пакет событий."""
        resp = await self._client.post(
            "/api/v1/events/batch",
            json={"events": events},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
