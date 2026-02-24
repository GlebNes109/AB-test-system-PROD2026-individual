import redis.asyncio as aioredis
from ab_test_platform.src.core.settings import settings

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
    return _redis_client
