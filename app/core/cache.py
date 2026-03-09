# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Redis Cache Manager for Cognigate.

Provides async Redis caching for:
- Policy evaluation results
- Trust scores
- Velocity state

Gracefully degrades to no-op if Redis is unavailable.
"""

import json
import logging
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Try to import redis, gracefully handle if not installed
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed - caching disabled")


class CacheManager:
    """
    Async Redis cache manager with graceful degradation.

    If Redis is unavailable or disabled, all operations become no-ops.
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._connected: bool = False
        self._settings = get_settings()

    async def connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            bool: True if connected, False otherwise
        """
        if not REDIS_AVAILABLE:
            logger.info("cache_disabled reason='redis package not installed'")
            return False

        if not self._settings.redis_enabled:
            logger.info("cache_disabled reason='redis_enabled=False'")
            return False

        try:
            self._client = redis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info(
                "cache_connected",
                extra={"redis_url": self._settings.redis_url}
            )
            return True
        except Exception as e:
            logger.warning(
                "cache_connection_failed",
                extra={"error": str(e)}
            )
            self._client = None
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"cache_disconnect_error: {e}")
            finally:
                self._client = None
                self._connected = False

    async def get_policy_result(
        self,
        plan_id: str,
        entity_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Get cached policy evaluation result.

        Args:
            plan_id: The plan identifier (may include rigor mode suffix)
            entity_id: Optional entity identifier for namespacing

        Returns:
            Cached result dict or None if not found/expired
        """
        if not self._connected or not self._client:
            return None

        try:
            key = self._make_key("policy", plan_id, entity_id)
            data = await self._client.get(key)
            if data:
                logger.debug(f"cache_hit key={key}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"cache_get_error: {e}")
            return None

    async def set_policy_result(
        self,
        plan_id: str,
        result: dict,
        ttl: Optional[int] = None,
        entity_id: Optional[str] = None,
    ) -> bool:
        """
        Cache a policy evaluation result.

        Args:
            plan_id: The plan identifier
            result: The result dict to cache
            ttl: Time-to-live in seconds (defaults to config value)
            entity_id: Optional entity identifier for namespacing

        Returns:
            bool: True if cached successfully
        """
        if not self._connected or not self._client:
            return False

        try:
            key = self._make_key("policy", plan_id, entity_id)
            ttl = ttl or self._settings.cache_ttl_policy_results

            await self._client.setex(
                key,
                ttl,
                json.dumps(result, default=str),
            )
            logger.debug(f"cache_set key={key} ttl={ttl}")
            return True
        except Exception as e:
            logger.warning(f"cache_set_error: {e}")
            return False

    async def get_trust_score(self, entity_id: str) -> Optional[dict]:
        """Get cached trust score for an entity."""
        if not self._connected or not self._client:
            return None

        try:
            key = self._make_key("trust", entity_id)
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"cache_get_trust_error: {e}")
            return None

    async def set_trust_score(
        self,
        entity_id: str,
        score_data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache a trust score."""
        if not self._connected or not self._client:
            return False

        try:
            key = self._make_key("trust", entity_id)
            ttl = ttl or self._settings.cache_ttl_trust_scores

            await self._client.setex(
                key,
                ttl,
                json.dumps(score_data, default=str),
            )
            return True
        except Exception as e:
            logger.warning(f"cache_set_trust_error: {e}")
            return False

    async def invalidate(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "cognigate:policy:*")

        Returns:
            Number of keys deleted
        """
        if not self._connected or not self._client:
            return 0

        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(f"cache_invalidate pattern={pattern} deleted={deleted}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"cache_invalidate_error: {e}")
            return 0

    def _make_key(self, namespace: str, *parts: Optional[str]) -> str:
        """Build a cache key with namespace prefix."""
        valid_parts = [p for p in parts if p]
        return f"cognigate:{namespace}:{':'.join(valid_parts)}"

    @property
    def is_connected(self) -> bool:
        """Check if cache is connected."""
        return self._connected


# Global cache manager instance
cache_manager = CacheManager()
