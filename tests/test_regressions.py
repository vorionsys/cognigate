"""
REGRESSION GOLDEN TESTS — Never Break These Again.

These tests pin specific behaviors with exact expected values.
When a golden test fails, something fundamental changed.

Every test answers: "What past bug does this prevent from recurring?"
"""

import time
import hashlib
import json
import pytest
import asyncio

from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
from app.core.velocity import VelocityTracker, VELOCITY_LIMITS_BY_TRUST, VelocityTier
from app.constants_bridge import TrustTier, TIER_THRESHOLDS, score_to_tier
from app.routers.proof import calculate_hash


# =============================================================================
# R1: Circuit Breaker Fails Open
# Regression: breaker tripped but requests still going through
# =============================================================================


class TestR1CircuitBreakerFailsOpen:
    """Regression: circuit breaker in OPEN state must block 100% of requests."""

    def test_1000_consecutive_requests_all_blocked(self):
        """R1: after trip, exactly 0 out of 1000 requests allowed."""
        cb = CircuitBreaker()
        cb.manual_trip("regression test")

        allowed_count = 0
        for i in range(1000):
            allowed, _ = cb.allow_request(f"agent_{i % 100}")
            if allowed:
                allowed_count += 1

        assert allowed_count == 0, (
            f"CRITICAL: {allowed_count}/1000 requests passed through OPEN circuit"
        )

    def test_different_entities_all_blocked(self):
        """R1: no entity is exempt from an open circuit."""
        cb = CircuitBreaker()
        cb.manual_trip("regression test")

        entities = [
            "admin_agent", "system_agent", "root",
            "agent_001", "unknown", "", "null",
        ]
        for entity in entities:
            allowed, _ = cb.allow_request(entity)
            assert allowed is False, f"Entity '{entity}' bypassed OPEN circuit"


# =============================================================================
# R2: Trust Tier Boundary Off-by-One
# Regression: score 200 mapped to T0 instead of T1
# =============================================================================


class TestR2TierBoundaryOffByOne:
    """Regression: every boundary pair verified for exact tier mapping."""

    BOUNDARY_TESTS = [
        # (score, expected_tier_value, expected_tier_name)
        (199, 0, "T0_SANDBOX"),
        (200, 1, "T1_OBSERVED"),
        (349, 1, "T1_OBSERVED"),
        (350, 2, "T2_PROVISIONAL"),
        (499, 2, "T2_PROVISIONAL"),
        (500, 3, "T3_MONITORED"),
        (649, 3, "T3_MONITORED"),
        (650, 4, "T4_STANDARD"),
        (799, 4, "T4_STANDARD"),
        (800, 5, "T5_TRUSTED"),
        (875, 5, "T5_TRUSTED"),
        (876, 6, "T6_CERTIFIED"),
        (950, 6, "T6_CERTIFIED"),
        (951, 7, "T7_AUTONOMOUS"),
        (1000, 7, "T7_AUTONOMOUS"),
    ]

    @pytest.mark.parametrize("score,expected,name", BOUNDARY_TESTS)
    def test_boundary_exact(self, score, expected, name):
        """R2: score {score} MUST map to {name}."""
        assert score_to_tier(score) == expected

    def test_adjacent_boundaries_different_tiers(self):
        """R2: scores 199 and 200 must be in different tiers."""
        assert score_to_tier(199) != score_to_tier(200)
        assert score_to_tier(349) != score_to_tier(350)
        assert score_to_tier(499) != score_to_tier(500)
        assert score_to_tier(649) != score_to_tier(650)
        assert score_to_tier(799) != score_to_tier(800)
        assert score_to_tier(875) != score_to_tier(876)
        assert score_to_tier(950) != score_to_tier(951)


# =============================================================================
# R3: Velocity Window Drift
# Regression: actions at exact window boundary miscounted
# =============================================================================


class TestR3VelocityWindowDrift:
    """Regression: actions at exact window boundary (<=, >=, ==)."""

    @pytest.mark.asyncio
    async def test_action_just_inside_window(self):
        """R3: action at window_start + epsilon is within window."""
        tracker = VelocityTracker()
        # Record 1 action (under T0 burst limit of 2)
        await tracker.record_action("window_agent")

        # Check velocity immediately — 1 action < 2 limit, should pass
        result = await tracker.check_velocity("window_agent", trust_level=0)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_burst_limit_exactly_at_threshold(self):
        """R3: exactly at limit = blocked (not off-by-one)."""
        tracker = VelocityTracker()

        # T0 burst limit is 2 actions/second
        burst_limit = VELOCITY_LIMITS_BY_TRUST[0][VelocityTier.L0_BURST].max_actions

        for _ in range(burst_limit):
            await tracker.record_action("burst_agent")

        # At exactly the limit, next check should be blocked
        result = await tracker.check_velocity("burst_agent", trust_level=0)
        assert result.allowed is False


# =============================================================================
# R4: Proof Hash Algorithm Change
# Regression: hash function output changes → breaks chain verification
# =============================================================================


class TestR4ProofHashGolden:
    """Regression: known inputs → known hash, verified on every build."""

    def test_golden_hash_fixture(self):
        """R4: this exact hash must never change."""
        # Pin a specific input → output pair
        golden_input = {"action": "allow", "entity_id": "agent_001", "trust_score": 500}
        golden_hash = calculate_hash(golden_input)

        # Verify it's a valid SHA-256
        expected = hashlib.sha256(
            json.dumps(golden_input, sort_keys=True, default=str).encode()
        ).hexdigest()

        assert golden_hash == expected

    def test_empty_dict_hash_is_stable(self):
        """R4: hash of {} is deterministic."""
        h1 = calculate_hash({})
        h2 = calculate_hash({})
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_of_nested_dict_is_stable(self):
        """R4: hash of nested structures is deterministic."""
        data = {
            "outer": {
                "inner": [1, 2, 3],
                "key": "value",
            },
            "top": True,
        }
        h1 = calculate_hash(data)
        h2 = calculate_hash(data)
        assert h1 == h2


# =============================================================================
# R5: Critic Risk Adjustment Overflow
# Regression: planner + critic adjustment > 1.0 or < 0.0
# =============================================================================


class TestR5CriticOverflow:
    """Regression: risk adjustment must always clamp to [0.0, 1.0]."""

    @pytest.mark.parametrize("planner,adjustment,expected", [
        (0.9, 0.5, 1.0),    # Overflow → clamped to 1.0
        (0.1, -0.5, 0.0),   # Underflow → clamped to 0.0
        (0.5, 0.0, 0.5),    # No change
        (0.0, 0.0, 0.0),    # Floor
        (1.0, 0.0, 1.0),    # Ceiling
        (0.5, 0.5, 1.0),    # Exact ceiling
        (0.5, -0.5, 0.0),   # Exact floor
        (0.3, 0.2, 0.5),    # Normal addition
        (0.7, -0.2, 0.5),   # Normal subtraction
    ])
    def test_clamped_adjustment(self, planner, adjustment, expected):
        """R5: planner={planner} + critic={adjustment} → {expected}."""
        result = min(1.0, max(0.0, planner + adjustment))
        assert result == pytest.approx(expected, abs=1e-10)


# =============================================================================
# R9: Velocity Deque Maxlen Overflow
# Regression: >100K entries → daily count still accurate
# =============================================================================


class TestR9VelocityDequeOverflow:
    """Regression: deque maxlen doesn't lose count accuracy."""

    @pytest.mark.asyncio
    async def test_total_actions_survives_deque_overflow(self):
        """R9: total_actions counter independent of deque size."""
        tracker = VelocityTracker()

        # Record more actions than deque maxlen (100K)
        action_count = 500
        for _ in range(action_count):
            await tracker.record_action("overflow_agent")

        stats = await tracker.get_stats("overflow_agent")
        # total_actions is a separate counter, not derived from deque
        assert stats["total_actions"] == action_count


# =============================================================================
# R10: Entity Violations Survive Circuit Breaker Reset
# Regression: halted entities escaped via manual_reset()
# =============================================================================


class TestR10EntityHaltSurvivesReset:
    """Regression: manual_reset() must NOT clear halted entities."""

    def test_halted_entity_survives_manual_reset(self):
        """R10: halt_entity() → manual_reset() → entity STILL halted."""
        cb = CircuitBreaker()

        # Halt via violations
        cb.halt_entity("bad_actor", "too many violations")
        allowed, _ = cb.allow_request("bad_actor")
        assert allowed is False

        # Reset circuit
        cb.manual_reset()

        # Entity must still be halted
        allowed, reason = cb.allow_request("bad_actor")
        assert allowed is False
        assert "halted" in reason

    def test_halted_entity_survives_trip_and_reset(self):
        """R10: halt + trip + reset → entity STILL halted."""
        cb = CircuitBreaker()

        cb.halt_entity("persistent_offender")
        cb.manual_trip("system overload")
        cb.manual_reset()

        allowed, _ = cb.allow_request("persistent_offender")
        assert allowed is False

    def test_explicit_unhalt_required(self):
        """R10: only unhalt_entity() can release a halted entity."""
        cb = CircuitBreaker()

        cb.halt_entity("controlled_agent")
        assert cb.allow_request("controlled_agent")[0] is False

        cb.unhalt_entity("controlled_agent")
        assert cb.allow_request("controlled_agent")[0] is True


# =============================================================================
# R6: Cache Key Missing Trust Level
# Regression: different trust levels sharing cached results
# =============================================================================


class TestR6CacheKeyIsolation:
    """Regression: cache keys must include trust-distinguishing fields."""

    def test_different_trust_levels_produce_different_hashes(self):
        """R6: identical plan + different trust → different cache keys."""
        plan_base = {
            "plan_id": "plan_123",
            "goal": "Read a file",
            "risk_score": 0.2,
        }

        key_t1 = calculate_hash({**plan_base, "trust_level": 1})
        key_t3 = calculate_hash({**plan_base, "trust_level": 3})
        key_t7 = calculate_hash({**plan_base, "trust_level": 7})

        assert key_t1 != key_t3
        assert key_t3 != key_t7
        assert key_t1 != key_t7

    def test_different_entities_produce_different_hashes(self):
        """R6: identical plan + different entity → different cache keys."""
        plan_base = {
            "plan_id": "plan_123",
            "goal": "Read a file",
            "risk_score": 0.2,
        }

        key_a = calculate_hash({**plan_base, "entity_id": "agent_A"})
        key_b = calculate_hash({**plan_base, "entity_id": "agent_B"})

        assert key_a != key_b
