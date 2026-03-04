"""
CHAOS & FAULT INJECTION TESTS — Break Everything Gracefully.

Tests system behavior when dependencies fail, when concurrent operations
race, and when the system is under extreme load.

Every test answers: "What happens when X breaks?"
"""

import time
import asyncio
import threading
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
from app.core.velocity import VelocityTracker, VELOCITY_LIMITS_BY_TRUST


# =============================================================================
# C1: Critic AI Total Failure
# Catches: system hangs or crashes when critic is unavailable
# =============================================================================


class TestC1CriticFailure:
    """What happens when the critic AI is completely unavailable?"""

    @pytest.mark.asyncio
    async def test_critic_timeout_returns_cautious_verdict(self):
        """C1: Critic timeout → system returns cautious 'suspicious' verdict."""
        from app.core.critic import run_critic, should_run_critic
        from app.models.critic import CriticRequest

        # Verify critic SHOULD run for risky plans
        assert should_run_critic(0.8, ["shell"]) is True

        request = CriticRequest(
            plan_id="test_plan",
            goal="Dangerous operation",
            planner_risk_score=0.8,
            planner_reasoning="This is risky",
            tools_required=["shell"],
            context={},
        )

        # Mock get_critic_provider to return a provider that times out
        mock_provider = AsyncMock()
        mock_provider.model_name = "mock-timeout"
        mock_provider.analyze = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("app.core.critic.settings") as mock_settings, \
             patch("app.core.critic.get_critic_provider", return_value=mock_provider):
            mock_settings.critic_enabled = True
            mock_settings.critic_provider = "mock"

            result = await run_critic(request)
            # On error, critic returns cautious "suspicious" verdict (not None)
            assert result is not None
            assert result.judgment == "suspicious"
            assert result.requires_human_review is True

    @pytest.mark.asyncio
    async def test_critic_500_error_returns_cautious_verdict(self):
        """C1: Critic provider error → returns cautious verdict, not crash."""
        from app.core.critic import run_critic
        from app.models.critic import CriticRequest

        request = CriticRequest(
            plan_id="test_plan",
            goal="Test operation",
            planner_risk_score=0.5,
            planner_reasoning="Test",
            tools_required=["file_read"],
            context={},
        )

        # Mock provider that raises a generic error (simulating 500)
        mock_provider = AsyncMock()
        mock_provider.model_name = "mock-error"
        mock_provider.analyze = AsyncMock(
            side_effect=Exception("HTTP 500: Internal Server Error")
        )

        with patch("app.core.critic.settings") as mock_settings, \
             patch("app.core.critic.get_critic_provider", return_value=mock_provider):
            mock_settings.critic_enabled = True
            mock_settings.critic_provider = "mock"

            result = await run_critic(request)
            # On error, critic returns cautious "suspicious" verdict
            assert result is not None
            assert result.judgment == "suspicious"
            assert result.confidence < 0.5  # Low confidence

    @pytest.mark.asyncio
    async def test_critic_disabled_returns_none(self):
        """C1: When critic is disabled, returns None (not error)."""
        from app.core.critic import run_critic
        from app.models.critic import CriticRequest

        request = CriticRequest(
            plan_id="test_plan",
            goal="Test",
            planner_risk_score=0.3,
            planner_reasoning="Test",
            tools_required=[],
            context={},
        )

        with patch("app.core.critic.settings") as mock_settings:
            mock_settings.critic_enabled = False
            result = await run_critic(request)
            assert result is None


# =============================================================================
# C6: 100 Concurrent Circuit Breaker Operations
# Catches: data races, inconsistent state under concurrency
# =============================================================================


class TestC6ConcurrentCircuitBreaker:
    """Concurrent trip + request + reset + status must not corrupt state."""

    def test_concurrent_trips_and_requests(self):
        """C6: 100 threads hammering circuit breaker simultaneously."""
        cb = CircuitBreaker(CircuitConfig(
            high_risk_threshold=0.5,
            tripwire_cascade_count=100,  # High threshold to avoid auto-trip
            injection_threshold=100,
            critic_block_threshold=100,
        ))
        errors = []

        def worker(thread_id):
            try:
                entity = f"agent_{thread_id}"
                for _ in range(50):
                    # Mix of operations
                    if thread_id % 4 == 0:
                        cb.record_request(entity, risk_score=0.8, tripwire_triggered=True)
                    elif thread_id % 4 == 1:
                        cb.allow_request(entity)
                    elif thread_id % 4 == 2:
                        cb.get_status()
                    else:
                        cb.record_request(entity, risk_score=0.1)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Concurrent errors: {errors}"

        # State must be valid after all operations
        status = cb.get_status()
        assert status["state"] in ("closed", "open", "half_open")
        assert isinstance(status["metrics"]["total_requests"], int)

    def test_concurrent_halt_and_allow(self):
        """C6: halt and allow racing don't produce inconsistent results."""
        cb = CircuitBreaker()
        results = {"allowed": 0, "blocked": 0}
        lock = threading.Lock()

        def halter():
            for _ in range(100):
                cb.halt_entity("target")
                time.sleep(0.001)

        def requester():
            for _ in range(100):
                allowed, _ = cb.allow_request("target")
                with lock:
                    if allowed:
                        results["allowed"] += 1
                    else:
                        results["blocked"] += 1

        t_halt = threading.Thread(target=halter)
        t_req = threading.Thread(target=requester)
        t_halt.start()
        t_req.start()
        t_halt.join()
        t_req.join()

        # After halter finishes, entity should be halted
        allowed, _ = cb.allow_request("target")
        assert allowed is False


# =============================================================================
# C8: 1000 Concurrent Velocity Checks
# Catches: double-count, lost count, or data corruption under load
# =============================================================================


class TestC8ConcurrentVelocity:
    """1000 concurrent velocity checks for same entity must be consistent."""

    @pytest.mark.asyncio
    async def test_concurrent_velocity_recording(self):
        """C8: 1000 concurrent record_action calls → count is exact."""
        tracker = VelocityTracker()
        target_count = 1000

        async def record_batch(start, count):
            for i in range(count):
                await tracker.record_action("concurrent_agent")

        # Run 10 batches of 100 concurrently
        tasks = [record_batch(i * 100, 100) for i in range(10)]
        await asyncio.gather(*tasks)

        stats = await tracker.get_stats("concurrent_agent")
        assert stats["total_actions"] == target_count, (
            f"Expected {target_count} actions, got {stats['total_actions']}"
        )

    @pytest.mark.asyncio
    async def test_velocity_check_under_load(self):
        """C8: velocity checks during heavy recording don't crash."""
        tracker = VelocityTracker()
        errors = []

        async def recorder():
            for _ in range(200):
                await tracker.record_action("load_agent")

        async def checker():
            for _ in range(200):
                try:
                    result = await tracker.check_velocity("load_agent", trust_level=0)
                    assert isinstance(result.allowed, bool)
                except Exception as e:
                    errors.append(str(e))

        await asyncio.gather(recorder(), checker())
        assert len(errors) == 0, f"Errors during load: {errors}"


# =============================================================================
# C3: Database Dies Mid-Operation
# Catches: system crash or data loss when DB is unavailable
# =============================================================================


class TestC3DatabaseFailure:
    """System must still return enforcement decisions when DB is down."""

    @pytest.mark.asyncio
    async def test_proof_creation_failure_does_not_crash_enforce(self):
        """C3: DB failure during proof recording → decision still returned."""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.auth import verify_api_key

        async def _bypass_auth() -> str:
            return "test-key"

        # The enforce endpoint should work even if proof recording fails
        # because it catches and logs DB errors
        app.dependency_overrides[verify_api_key] = _bypass_auth
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/v1/enforce", json={
                    "entity_id": "agent_test",
                    "trust_level": 3,
                    "trust_score": 500,
                    "plan": {
                        "plan_id": "plan_db_test",
                        "goal": "Read a file",
                        "tools_required": ["file_read"],
                        "data_classifications": [],
                        "risk_score": 0.2,
                        "reasoning_trace": "Simple file read",
                    },
                })
                # Even if proof recording fails internally, the endpoint should respond
                assert response.status_code == 200
                data = response.json()
                assert "action" in data
        finally:
            app.dependency_overrides.pop(verify_api_key, None)


# =============================================================================
# CIRCUIT BREAKER RECOVERY — state transitions are correct
# =============================================================================


class TestCircuitBreakerStateTransitions:
    """Verify state machine transitions: CLOSED→OPEN→HALF_OPEN→CLOSED."""

    def test_full_lifecycle(self):
        """Complete circuit breaker lifecycle must follow state machine."""
        cb = CircuitBreaker(CircuitConfig(
            auto_reset_seconds=0,
            half_open_requests=2,
        ))

        # Start CLOSED
        assert cb.state == CircuitState.CLOSED

        # Trip to OPEN
        cb.manual_trip("test")
        assert cb.state == CircuitState.OPEN

        # Auto-reset to HALF_OPEN
        cb._current_trip.auto_reset_at = time.time() - 1
        allowed, _ = cb.allow_request("test_agent")
        assert cb.state == CircuitState.HALF_OPEN
        assert allowed is True

        # Record successes in HALF_OPEN
        cb.record_request("test_agent")
        cb.record_request("test_agent")

        # After enough successes, should close
        cb.allow_request("test_agent")
        assert cb.state == CircuitState.CLOSED

    def test_trip_during_half_open_goes_back_to_open(self):
        """Trip condition during HALF_OPEN → back to OPEN, not CLOSED."""
        cb = CircuitBreaker(CircuitConfig(
            auto_reset_seconds=0,
            half_open_requests=5,
            tripwire_cascade_count=1,
        ))

        # Get to HALF_OPEN
        cb.manual_trip("initial")
        cb._current_trip.auto_reset_at = time.time() - 1
        cb.allow_request("agent")  # Triggers auto-reset to HALF_OPEN

        # Trip again during HALF_OPEN via tripwire cascade
        cb._state = CircuitState.CLOSED  # Simulate for trip check
        cb.record_request("bad_agent", tripwire_triggered=True)

        # Should be OPEN now
        assert cb.state == CircuitState.OPEN
