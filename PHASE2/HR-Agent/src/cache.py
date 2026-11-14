from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResilientCache:
    """Redis-backed cache. Any Redis failure behaves like a cache miss."""

    def __init__(self, redis_url: str) -> None:
        import redis as redis_lib
        try:
            self.client = redis_lib.Redis.from_url(redis_url, socket_timeout=2, decode_responses=True)
        except Exception:
            logger.warning("Redis connection failed, operating without cache")
            self.client = None

    def health(self) -> bool:
        if self.client is None:
            return False
        try:
            return self.client.ping()
        except Exception:
            return False

    def get(self, key: str) -> Any | None:
        if self.client is None:
            return None
        try:
            raw = self.client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if self.client is None:
            return
        try:
            self.client.setex(key, ttl_seconds, json.dumps(value, default=str))
        except Exception:
            logger.warning("Cache set failed, swallowing error")


class NullCache(ResilientCache):
    """No-op cache for tests."""

    def __init__(self) -> None:
        self.client = None

    def health(self) -> bool:
        return True

    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        pass

