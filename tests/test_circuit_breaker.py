"""
Tests for circuit breaker - autonomous safety halts.

Tests state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED),
trip conditions, entity-level halts, cascade halts, and auto-reset.
"""

import time
from unittest.mock import patch

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitConfig,
    CircuitState,
    TripReason,
)


@pytest.fixture
def cb():
    """Fresh circuit breaker for each test."""
    return CircuitBreaker(CircuitConfig(
        auto_reset_seconds=1,
        half_open_requests=2,
        metrics_window_seconds=300,
    ))


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self, cb):
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open

    def test_manual_trip_opens_circuit(self, cb):
        cb.manual_trip("test halt")
        assert cb.state == CircuitState.OPEN
        assert cb.is_open

    def test_manual_reset_closes_circuit(self, cb):
        cb.manual_trip("test halt")
        cb.manual_reset()
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open

    def test_open_circuit_blocks_requests(self, cb):
        cb.manual_trip("test halt")
        allowed, reason = cb.allow_request("agent_1")
        assert not allowed
        assert "OPEN" in reason

    def test_closed_circuit_allows_requests(self, cb):
        allowed, reason = cb.allow_request("agent_1")
        assert allowed

    def test_auto_reset_transitions_to_half_open(self, cb):
        cb.manual_trip("test halt")
        assert cb.state == CircuitState.OPEN
        # Wait for auto-reset (configured at 1 second)
        time.sleep(1.1)
        allowed, reason = cb.allow_request("agent_1")
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_recovers_after_successes(self, cb):
        cb.manual_trip("test halt")
        time.sleep(1.1)
        # First request transitions to half-open
        cb.allow_request("agent_1")
        assert cb.state == CircuitState.HALF_OPEN
        # Record successful requests
        cb.record_request("agent_1", risk_score=0.0)
        cb.record_request("agent_1", risk_score=0.0)
        # After enough successes, next allow_request closes it
        allowed, reason = cb.allow_request("agent_1")
        assert cb.state == CircuitState.CLOSED
        assert allowed


class TestTripConditions:
    """Test automatic trip conditions."""

    def test_high_risk_threshold_trips_circuit(self, cb):
        """Circuit trips when >10% of 10+ requests are high-risk."""
        # Record 8 normal + 2 high-risk (20% > 10% threshold)
        for _ in range(8):
            cb.record_request("agent_1", risk_score=0.1)
        cb.record_request("agent_1", risk_score=0.9)
        cb.record_request("agent_1", risk_score=0.8)
        assert cb.state == CircuitState.OPEN

    def test_below_threshold_stays_closed(self, cb):
        """Circuit stays closed when high-risk ratio is below threshold."""
        for _ in range(9):
            cb.record_request("agent_1", risk_score=0.1)
        cb.record_request("agent_1", risk_score=0.9)  # 10% exactly, not > 10%
        assert cb.state == CircuitState.CLOSED

    def test_tripwire_cascade_trips_circuit(self, cb):
        """Circuit trips on 3 tripwire triggers in window."""
        cb.record_request("agent_1", tripwire_triggered=True)
        cb.record_request("agent_1", tripwire_triggered=True)
        assert cb.state == CircuitState.CLOSED
        cb.record_request("agent_1", tripwire_triggered=True)
        assert cb.state == CircuitState.OPEN

    def test_injection_detected_trips_circuit(self, cb):
        """Circuit trips on 2 injection attempts."""
        cb.record_request("agent_1", injection_detected=True)
        assert cb.state == CircuitState.CLOSED
        cb.record_request("agent_1", injection_detected=True)
        assert cb.state == CircuitState.OPEN

    def test_critic_block_cascade_trips_circuit(self, cb):
        """Circuit trips on 5 critic blocks."""
        for i in range(4):
            cb.record_request("agent_1", critic_blocked=True)
        assert cb.state == CircuitState.CLOSED
        cb.record_request("agent_1", critic_blocked=True)
        assert cb.state == CircuitState.OPEN

    def test_no_trip_when_too_few_requests_for_ratio(self, cb):
        """High-risk ratio check requires >= 10 requests."""
        # 5 high-risk out of 5 = 100% but < 10 requests
        for _ in range(5):
            cb.record_request("agent_1", risk_score=0.9)
        assert cb.state == CircuitState.CLOSED


class TestEntityHalts:
    """Test entity-level halting."""

    def test_halt_entity_blocks_requests(self, cb):
        cb.halt_entity("bad_agent", reason="misbehaving")
        allowed, reason = cb.allow_request("bad_agent")
        assert not allowed
        assert "halted" in reason

    def test_halt_entity_does_not_affect_others(self, cb):
        cb.halt_entity("bad_agent")
        allowed, _ = cb.allow_request("good_agent")
        assert allowed

    def test_unhalt_entity_restores_access(self, cb):
        cb.halt_entity("agent_1")
        cb.unhalt_entity("agent_1")
        allowed, _ = cb.allow_request("agent_1")
        assert allowed

    def test_velocity_violations_auto_halt_entity(self, cb):
        """Entity auto-halted after exceeding violation threshold (default 10)."""
        for _ in range(10):
            cb.record_request("bad_agent", velocity_violated=True)
        allowed, reason = cb.allow_request("bad_agent")
        assert not allowed
        assert "halted" in reason

    def test_cascade_halt_halts_parent_and_children(self, cb):
        cb.register_child("parent", "child_1")
        cb.register_child("parent", "child_2")
        cb.cascade_halt("parent", reason="cascade test")
        assert not cb.allow_request("parent")[0]
        assert not cb.allow_request("child_1")[0]
        assert not cb.allow_request("child_2")[0]
        # Unrelated agent still works
        assert cb.allow_request("unrelated")[0]


class TestCircuitBreakerStatus:
    """Test status reporting."""

    def test_status_reports_closed(self, cb):
        status = cb.get_status()
        assert status["state"] == "closed"
        assert not status["is_open"]
        assert status["current_trip"] is None

    def test_status_reports_open_with_trip_info(self, cb):
        cb.manual_trip("test reason")
        status = cb.get_status()
        assert status["state"] == "open"
        assert status["is_open"]
        assert status["current_trip"]["reason"] == "manual_halt"
        assert "test reason" in status["current_trip"]["details"]

    def test_trip_history_records_trips(self, cb):
        cb.manual_trip("first trip")
        cb.manual_reset()
        cb.manual_trip("second trip")
        history = cb.get_trip_history()
        assert len(history) == 2
        assert history[0]["details"] == "first trip"
        assert history[1]["details"] == "second trip"

    def test_metrics_tracked(self, cb):
        cb.record_request("a", risk_score=0.9)
        cb.record_request("a", was_blocked=True)
        cb.record_request("a", tripwire_triggered=True)
        status = cb.get_status()
        m = status["metrics"]
        assert m["total_requests"] == 3
        assert m["high_risk_requests"] == 1
        assert m["blocked_requests"] == 1
        assert m["tripwire_triggers"] == 1
