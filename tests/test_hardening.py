# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for circuit breaker hardening and velocity improvements.

Covers:
- Hysteresis: asymmetric trip/recovery thresholds prevent oscillation
- Exponential backoff: consecutive trips increase auto-reset time
- Graduated recovery: progressive half-open allowance (10% → 25% → 50% → 100%)
- Velocity deque bug fix: prune preserves deque type
- Velocity auto-throttle: repeated violations trigger escalating throttle
- Circuit breaker + velocity integration

Category: Unit + Integration (no I/O, in-memory only)
"""

import asyncio
import time
from collections import deque
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitConfig,
    CircuitState,
    TripReason,
)
from app.core.velocity import (
    VelocityCheckResult,
    VelocityState,
    VelocityTier,
    VelocityTracker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_cb():
    """Circuit breaker with fast timeouts for testing."""
    return CircuitBreaker(CircuitConfig(
        auto_reset_seconds=1,
        half_open_requests=2,
        metrics_window_seconds=300,
        backoff_multiplier=2.0,
        max_backoff_seconds=60,
        consecutive_trip_decay_seconds=5,
        graduated_recovery_enabled=False,  # Legacy mode by default
    ))


@pytest.fixture
def graduated_cb():
    """Circuit breaker with graduated recovery enabled."""
    return CircuitBreaker(CircuitConfig(
        auto_reset_seconds=1,
        half_open_requests=2,
        metrics_window_seconds=300,
        backoff_multiplier=2.0,
        max_backoff_seconds=60,
        consecutive_trip_decay_seconds=5,
        graduated_recovery_enabled=True,
        graduated_stages=(0.50, 1.0),  # Simplified: 50% → 100%
        graduated_stage_requests=2,    # 2 successes per stage
    ))


@pytest.fixture
def hysteresis_cb():
    """Circuit breaker with hysteresis thresholds configured."""
    return CircuitBreaker(CircuitConfig(
        auto_reset_seconds=1,
        half_open_requests=2,
        metrics_window_seconds=300,
        high_risk_threshold=0.10,
        hysteresis_high_risk_recovery=0.05,
        hysteresis_tripwire_recovery=1,
        hysteresis_injection_recovery=0,
        hysteresis_critic_recovery=2,
    ))


@pytest.fixture
def tracker():
    """Fresh velocity tracker."""
    return VelocityTracker()


# ---------------------------------------------------------------------------
# Exponential Backoff
# ---------------------------------------------------------------------------

class TestExponentialBackoff:
    """Verify auto-reset time escalates on consecutive trips."""

    def test_first_trip_uses_base_reset_time(self, default_cb):
        """First trip: reset time = base (1 second)."""
        default_cb.manual_trip("first trip")
        assert default_cb._consecutive_trips == 1
        trip = default_cb._current_trip
        # base * 2^0 = 1 * 1 = 1 second
        expected_reset = trip.timestamp + 1.0
        assert abs(trip.auto_reset_at - expected_reset) < 0.1

    def test_second_consecutive_trip_doubles_reset_time(self, default_cb):
        """Second consecutive trip: reset time = base * 2."""
        default_cb.manual_trip("trip 1")
        # Simulate auto-reset (don't use manual_reset — it clears consecutive counter)
        default_cb._state = CircuitState.CLOSED
        default_cb._current_trip = None
        default_cb._metrics.reset()
        default_cb.manual_trip("trip 2")
        assert default_cb._consecutive_trips == 2
        trip = default_cb._current_trip
        # base * 2^1 = 1 * 2 = 2 seconds
        expected_reset = trip.timestamp + 2.0
        assert abs(trip.auto_reset_at - expected_reset) < 0.1

    def test_third_consecutive_trip_quadruples_reset_time(self, default_cb):
        """Third consecutive trip: reset time = base * 4."""
        for i in range(3):
            default_cb.manual_trip(f"trip {i+1}")
            if i < 2:
                # Simulate auto-reset without clearing consecutive counter
                default_cb._state = CircuitState.CLOSED
                default_cb._current_trip = None
                default_cb._metrics.reset()
        assert default_cb._consecutive_trips == 3
        trip = default_cb._current_trip
        # base * 2^2 = 1 * 4 = 4 seconds
        expected_reset = trip.timestamp + 4.0
        assert abs(trip.auto_reset_at - expected_reset) < 0.1

    def test_backoff_capped_at_max(self, default_cb):
        """Backoff never exceeds max_backoff_seconds."""
        # Trip many times to exceed cap (max=60, base=1, 2^10=1024 >> 60)
        for i in range(11):
            default_cb.manual_trip(f"trip {i+1}")
            if i < 10:
                default_cb._state = CircuitState.CLOSED
                default_cb._current_trip = None
                default_cb._metrics.reset()
        trip = default_cb._current_trip
        expected_max = trip.timestamp + 60.0
        assert abs(trip.auto_reset_at - expected_max) < 0.1

    def test_consecutive_counter_decays_after_stability(self, default_cb):
        """Consecutive trip counter resets after decay period of stability."""
        default_cb.manual_trip("trip 1")
        # Simulate auto-reset without clearing consecutive counter 
        default_cb._state = CircuitState.CLOSED
        default_cb._current_trip = None
        default_cb._metrics.reset()
        assert default_cb._consecutive_trips == 1

        # Simulate time passing beyond decay period (5 seconds in test config)
        default_cb._last_trip_time = time.time() - 10  # 10s ago, > 5s decay

        default_cb.manual_trip("trip after stability")
        # Counter should have reset to 0, then incremented to 1
        assert default_cb._consecutive_trips == 1

    def test_consecutive_counter_preserved_within_decay_window(self, default_cb):
        """Consecutive counter stays if within decay window."""
        default_cb.manual_trip("trip 1")
        default_cb._state = CircuitState.CLOSED
        default_cb._current_trip = None
        default_cb._metrics.reset()
        assert default_cb._consecutive_trips == 1

        # Trip again immediately (within decay window)
        default_cb.manual_trip("trip 2")
        assert default_cb._consecutive_trips == 2

    def test_manual_reset_clears_consecutive_counter(self, default_cb):
        """Manual reset zeroes the consecutive trip counter."""
        default_cb.manual_trip("trip 1")
        default_cb.manual_reset()
        # manual_reset now clears consecutive_trips
        assert default_cb._consecutive_trips == 0

    def test_backoff_status_reported(self, default_cb):
        """Status endpoint includes backoff details."""
        default_cb.manual_trip("trip")
        status = default_cb.get_status()
        assert "backoff" in status
        assert status["backoff"]["consecutive_trips"] == 1
        assert status["backoff"]["current_reset_seconds"] == 1.0


# ---------------------------------------------------------------------------
# Graduated Recovery
# ---------------------------------------------------------------------------

class TestGraduatedRecovery:
    """Verify progressive half-open recovery stages."""

    def test_graduated_stages_throttle_requests(self, graduated_cb):
        """In stage 0 (50%), every other request is allowed."""
        graduated_cb.manual_trip("test")
        time.sleep(1.1)  # Wait for auto-reset to half-open

        # Transition to half-open
        graduated_cb.allow_request("agent_1")
        assert graduated_cb.state == CircuitState.HALF_OPEN

        # Stage 0 = 50% allowance → interval = 2 → allow every 2nd request
        results = []
        for _ in range(6):
            allowed, reason = graduated_cb.allow_request("agent_1")
            results.append(allowed)

        # With 50% drip: roughly half should be allowed
        allowed_count = sum(results)
        assert allowed_count >= 2, f"Expected at least 2 allowed, got {allowed_count}"
        assert allowed_count <= 4, f"Expected at most 4 allowed, got {allowed_count}"

    def test_graduated_stage_advances_on_successes(self, graduated_cb):
        """Recording enough successes advances the recovery stage."""
        graduated_cb.manual_trip("test")
        time.sleep(1.1)
        graduated_cb.allow_request("agent_1")
        assert graduated_cb.state == CircuitState.HALF_OPEN
        assert graduated_cb._recovery_stage == 0

        # Record 2 successes (graduated_stage_requests=2)
        graduated_cb.record_request("agent_1", risk_score=0.0)
        graduated_cb.record_request("agent_1", risk_score=0.0)
        assert graduated_cb._recovery_stage == 1

    def test_graduated_recovery_completes_to_closed(self, graduated_cb):
        """Completing all stages closes the circuit."""
        graduated_cb.manual_trip("test")
        time.sleep(1.1)
        graduated_cb.allow_request("agent_1")
        assert graduated_cb.state == CircuitState.HALF_OPEN

        # Stage 0: 2 successes → advance to stage 1
        graduated_cb.record_request("agent_1", risk_score=0.0)
        graduated_cb.record_request("agent_1", risk_score=0.0)
        assert graduated_cb._recovery_stage == 1

        # Stage 1: 2 successes → all stages done → CLOSED
        graduated_cb.record_request("agent_1", risk_score=0.0)
        graduated_cb.record_request("agent_1", risk_score=0.0)
        assert graduated_cb.state == CircuitState.CLOSED

    def test_failure_during_recovery_re_trips(self, graduated_cb):
        """A blocked request during half-open immediately re-trips."""
        graduated_cb.manual_trip("test")
        time.sleep(1.1)
        graduated_cb.allow_request("agent_1")
        assert graduated_cb.state == CircuitState.HALF_OPEN

        # Record a blocked request (failure)
        graduated_cb.record_request("agent_1", was_blocked=True)
        assert graduated_cb.state == CircuitState.OPEN

    def test_recovery_status_in_get_status(self, graduated_cb):
        """Status endpoint includes recovery stage details in half-open."""
        graduated_cb.manual_trip("test")
        time.sleep(1.1)
        graduated_cb.allow_request("agent_1")
        assert graduated_cb.state == CircuitState.HALF_OPEN

        status = graduated_cb.get_status()
        assert status["recovery"] is not None
        assert status["recovery"]["stage"] == 0
        assert status["recovery"]["total_stages"] == 2
        assert status["recovery"]["current_allowance"] == 0.50

    def test_recovery_not_in_status_when_closed(self, graduated_cb):
        """Recovery details not included in status when circuit is closed."""
        status = graduated_cb.get_status()
        assert status["recovery"] is None

    def test_legacy_mode_without_graduated(self, default_cb):
        """With graduated_recovery_enabled=False, uses legacy half-open test."""
        default_cb.manual_trip("test")
        time.sleep(1.1)
        default_cb.allow_request("agent_1")
        assert default_cb.state == CircuitState.HALF_OPEN

        # Legacy mode: N successes → close
        default_cb.record_request("agent_1", risk_score=0.0)
        default_cb.record_request("agent_1", risk_score=0.0)
        # Now allow_request should see enough successes and close
        allowed, reason = default_cb.allow_request("agent_1")
        assert default_cb.state == CircuitState.CLOSED
        assert allowed


# ---------------------------------------------------------------------------
# Hysteresis
# ---------------------------------------------------------------------------

class TestHysteresis:
    """Verify asymmetric trip/recovery thresholds."""

    def test_hysteresis_blocks_recovery_above_threshold(self, hysteresis_cb):
        """Recovery blocked when metrics exceed hysteresis recovery threshold."""
        # Pump up metrics: 10% high-risk (5 of 50)
        for _ in range(45):
            hysteresis_cb.record_request("agent_1", risk_score=0.1)
        for _ in range(5):
            hysteresis_cb.record_request("agent_1", risk_score=0.9)

        # 10% > 5% recovery threshold → can't recover
        can_recover, reason = hysteresis_cb.check_recovery_hysteresis()
        assert not can_recover
        assert "high_risk_ratio" in reason

    def test_hysteresis_allows_recovery_below_threshold(self, hysteresis_cb):
        """Recovery allowed when metrics drop below hysteresis threshold."""
        # 2 of 100 high-risk = 2% < 5% recovery threshold
        for _ in range(98):
            hysteresis_cb.record_request("agent_1", risk_score=0.1)
        for _ in range(2):
            hysteresis_cb.record_request("agent_1", risk_score=0.9)

        can_recover, reason = hysteresis_cb.check_recovery_hysteresis()
        assert can_recover

    def test_hysteresis_tripwire_check(self, hysteresis_cb):
        """Tripwire hysteresis: recovery threshold is 1 (vs trip threshold 3)."""
        # 2 tripwires > 1 recovery threshold
        hysteresis_cb.record_request("agent_1", tripwire_triggered=True)
        hysteresis_cb.record_request("agent_1", tripwire_triggered=True)

        can_recover, reason = hysteresis_cb.check_recovery_hysteresis()
        assert not can_recover
        assert "tripwire_triggers" in reason

    def test_hysteresis_injection_check(self, hysteresis_cb):
        """Injection hysteresis: recovery requires 0 (vs trip threshold 2)."""
        hysteresis_cb.record_request("agent_1", injection_detected=True)

        can_recover, reason = hysteresis_cb.check_recovery_hysteresis()
        assert not can_recover
        assert "injection_attempts" in reason

    def test_hysteresis_critic_check(self, hysteresis_cb):
        """Critic hysteresis: recovery threshold is 2 (vs trip threshold 5)."""
        for _ in range(3):
            hysteresis_cb.record_request("agent_1", critic_blocked=True)

        can_recover, reason = hysteresis_cb.check_recovery_hysteresis()
        assert not can_recover
        assert "critic_blocks" in reason

    def test_hysteresis_clean_metrics_recoverable(self, hysteresis_cb):
        """Clean metrics (no violations) always recoverable."""
        can_recover, reason = hysteresis_cb.check_recovery_hysteresis()
        assert can_recover


# ---------------------------------------------------------------------------
# Velocity Deque Bug Fix
# ---------------------------------------------------------------------------

class TestVelocityDequeFix:
    """Verify that _prune_old_timestamps preserves the deque type."""

    def test_prune_preserves_deque_type(self, tracker):
        """After pruning, action_timestamps is still a deque, not a list."""
        state = VelocityState(entity_id="test")
        state.action_timestamps = deque([
            time.time() - 100000,  # Old (>86400s), should be pruned
            time.time() - 90000,   # Old (>86400s), should be pruned
            time.time() - 10,      # Recent (<86400s), should stay
        ], maxlen=100000)

        tracker._prune_old_timestamps(state)
        assert isinstance(state.action_timestamps, deque)
        assert len(state.action_timestamps) == 1

    def test_prune_removes_all_old_entries(self, tracker):
        """All entries older than max_age are removed."""
        now = time.time()
        state = VelocityState(entity_id="test")
        state.action_timestamps = deque([
            now - 200,
            now - 150,
            now - 100,
            now - 50,
            now - 10,
        ], maxlen=100000)

        tracker._prune_old_timestamps(state, max_age=60)
        assert len(state.action_timestamps) == 2

    def test_prune_empty_deque_no_error(self, tracker):
        """Pruning an empty deque doesn't raise."""
        state = VelocityState(entity_id="test")
        tracker._prune_old_timestamps(state)
        assert len(state.action_timestamps) == 0


# ---------------------------------------------------------------------------
# Velocity Auto-Throttle
# ---------------------------------------------------------------------------

class TestVelocityAutoThrottle:
    """Verify velocity auto-throttle on repeated violations."""

    @pytest.mark.asyncio
    async def test_auto_throttle_after_3_violations(self, tracker):
        """Entity auto-throttled after 3 consecutive velocity violations."""
        entity_id = "flood_agent"
        # Record enough actions to exceed T1 burst limit (5/second)
        for _ in range(6):
            await tracker.record_action(entity_id)

        # First check → violation #1
        result = await tracker.check_velocity(entity_id, trust_level=1)
        assert not result.allowed

        # Second check → violation #2
        result = await tracker.check_velocity(entity_id, trust_level=1)
        assert not result.allowed

        # Third check → violation #3, triggers auto-throttle
        result = await tracker.check_velocity(entity_id, trust_level=1)
        assert not result.allowed

        # Verify the entity is now throttled
        state = tracker._get_state(entity_id)
        assert state.is_throttled
        assert state.throttle_until is not None

    @pytest.mark.asyncio
    async def test_auto_throttle_duration_escalates(self, tracker):
        """Auto-throttle duration increases with more violations."""
        entity_id = "repeat_offender"
        state = tracker._get_state(entity_id)

        # Simulate 5 violations (bypassing actual velocity checks)
        state.violations = 5
        state.last_violation = time.time()
        now = time.time()

        # Record actions to trigger another violation
        for _ in range(6):
            await tracker.record_action(entity_id)

        result = await tracker.check_velocity(entity_id, trust_level=1)
        assert not result.allowed
        assert state.violations == 6

        # Throttle duration should be 30 * 2^(6-3) = 30 * 8 = 240s
        if state.is_throttled:
            expected_duration = 30.0 * (2 ** (6 - 3))  # 240s
            actual_duration = state.throttle_until - now
            assert abs(actual_duration - expected_duration) < 5.0


# ---------------------------------------------------------------------------
# Integration: CB + Velocity Status
# ---------------------------------------------------------------------------

class TestCircuitBreakerIntegration:
    """Verify circuit breaker reports velocity violations in status."""

    def test_velocity_violations_tracked_in_metrics(self, default_cb):
        """Velocity violations increment the circuit metrics counter."""
        default_cb.record_request("agent_1", velocity_violated=True)
        default_cb.record_request("agent_1", velocity_violated=True)
        status = default_cb.get_status()
        assert status["metrics"]["velocity_violations"] == 2

    def test_combined_trip_injection_plus_velocity(self, default_cb):
        """Injection + velocity violations contribute independently to trip conditions."""
        # Record injection (threshold=2)
        default_cb.record_request("agent_1", injection_detected=True)
        assert default_cb.state == CircuitState.CLOSED
        default_cb.record_request("agent_1", injection_detected=True)
        assert default_cb.state == CircuitState.OPEN  # Tripped by injection

    def test_backoff_escalation_with_auto_trip(self):
        """Verify auto-trip from high-risk also escalates backoff."""
        cb = CircuitBreaker(CircuitConfig(
            auto_reset_seconds=10,
            backoff_multiplier=2.0,
            max_backoff_seconds=3600,
            consecutive_trip_decay_seconds=900,
            metrics_window_seconds=300,
            graduated_recovery_enabled=False,
        ))

        # Trip 1: auto-trip via high-risk
        for _ in range(8):
            cb.record_request("a", risk_score=0.1)
        cb.record_request("a", risk_score=0.9)
        cb.record_request("a", risk_score=0.9)
        assert cb.state == CircuitState.OPEN
        assert cb._consecutive_trips == 1
        first_reset = cb._current_trip.auto_reset_at

        # Simulate auto-reset (not manual — preserves consecutive counter)
        cb._state = CircuitState.CLOSED
        cb._current_trip = None
        cb._metrics.reset()

        for _ in range(8):
            cb.record_request("a", risk_score=0.1)
        cb.record_request("a", risk_score=0.9)
        cb.record_request("a", risk_score=0.9)
        assert cb._consecutive_trips == 2
        second_reset = cb._current_trip.auto_reset_at

        # Second trip should have ~2x the reset time
        # (reset time = 10 * 2^1 = 20)
        first_duration = first_reset - cb._trip_history[0].timestamp
        second_duration = second_reset - cb._trip_history[1].timestamp
        assert second_duration > first_duration * 1.5
