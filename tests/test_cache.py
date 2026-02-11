"""
Tests for cache manager - Redis caching with graceful degradation.

Tests that all operations gracefully degrade when Redis is unavailable,
key generation, and the cache interface.
"""

import pytest
import pytest_asyncio

from app.core.cache import CacheManager


@pytest_asyncio.fixture
async def cache():
    """Cache manager that is NOT connected (graceful degradation mode)."""
    manager = CacheManager()
    # Don't connect — test graceful degradation
    yield manager


@pytest.mark.asyncio
class TestGracefulDegradation:
    """Test that cache operations are no-ops when disconnected."""

    async def test_not_connected_by_default(self, cache):
        assert not cache.is_connected

    async def test_get_policy_result_returns_none(self, cache):
        result = await cache.get_policy_result("plan_123")
        assert result is None

    async def test_set_policy_result_returns_false(self, cache):
        result = await cache.set_policy_result("plan_123", {"allowed": True})
        assert result is False

    async def test_get_trust_score_returns_none(self, cache):
        result = await cache.get_trust_score("agent_1")
        assert result is None

    async def test_set_trust_score_returns_false(self, cache):
        result = await cache.set_trust_score("agent_1", {"score": 500})
        assert result is False

    async def test_invalidate_returns_zero(self, cache):
        result = await cache.invalidate("cognigate:*")
        assert result == 0

    async def test_disconnect_when_not_connected(self, cache):
        """Disconnect is safe even when not connected."""
        await cache.disconnect()  # Should not raise
        assert not cache.is_connected


class TestCacheKeyGeneration:
    """Test internal key generation."""

    def test_make_key_simple(self, cache):
        key = cache._make_key("policy", "plan_123")
        assert key == "cognigate:policy:plan_123"

    def test_make_key_with_entity(self, cache):
        key = cache._make_key("policy", "plan_123", "agent_1")
        assert key == "cognigate:policy:plan_123:agent_1"

    def test_make_key_filters_none(self, cache):
        key = cache._make_key("trust", "agent_1", None)
        assert key == "cognigate:trust:agent_1"

    def test_make_key_namespace_only(self, cache):
        key = cache._make_key("test")
        assert key == "cognigate:test:"


@pytest.mark.asyncio
class TestConnectionFailure:
    """Test behavior when Redis connection fails."""

    async def test_connect_with_disabled_redis(self):
        """Connection returns False when redis_enabled is False."""
        manager = CacheManager()
        # redis_enabled defaults to False in settings
        connected = await manager.connect()
        assert not connected
        assert not manager.is_connected
