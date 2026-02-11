"""
Unit tests for the Cache module.

Tests the CacheManager graceful degradation when Redis is unavailable.
"""

import pytest
from app.core.cache import CacheManager


class TestCacheManagerCreation:
    """Test CacheManager initialization."""

    def test_creates_instance(self):
        cm = CacheManager()
        assert cm is not None
        assert cm.is_connected is False

    def test_not_connected_by_default(self):
        cm = CacheManager()
        assert cm._client is None
        assert cm._connected is False


@pytest.mark.anyio
class TestCacheManagerDisconnected:
    """Test CacheManager when not connected (graceful degradation)."""

    async def test_get_policy_result_returns_none(self):
        cm = CacheManager()
        result = await cm.get_policy_result("plan_123")
        assert result is None

    async def test_get_policy_result_with_entity(self):
        cm = CacheManager()
        result = await cm.get_policy_result("plan_123", entity_id="agent_456")
        assert result is None

    async def test_set_policy_result_returns_false(self):
        cm = CacheManager()
        result = await cm.set_policy_result("plan_123", {"allowed": True})
        assert result is False

    async def test_get_trust_score_returns_none(self):
        cm = CacheManager()
        result = await cm.get_trust_score("agent_123")
        assert result is None

    async def test_set_trust_score_returns_false(self):
        cm = CacheManager()
        result = await cm.set_trust_score("agent_123", {"score": 500})
        assert result is False

    async def test_invalidate_returns_zero(self):
        cm = CacheManager()
        result = await cm.invalidate("cognigate:*")
        assert result == 0

    async def test_disconnect_is_safe(self):
        cm = CacheManager()
        await cm.disconnect()  # Should not raise
        assert cm._connected is False

    async def test_connect_without_redis_returns_false(self):
        cm = CacheManager()
        result = await cm.connect()
        assert isinstance(result, bool)


class TestCacheKeyBuilder:
    """Test the cache key construction."""

    def test_make_key_single_part(self):
        cm = CacheManager()
        key = cm._make_key("policy", "plan_123")
        assert key == "cognigate:policy:plan_123"

    def test_make_key_multiple_parts(self):
        cm = CacheManager()
        key = cm._make_key("policy", "plan_123", "agent_456")
        assert key == "cognigate:policy:plan_123:agent_456"

    def test_make_key_filters_none(self):
        cm = CacheManager()
        key = cm._make_key("trust", "agent_123", None)
        assert key == "cognigate:trust:agent_123"
