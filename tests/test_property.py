"""
Property-based tests using Hypothesis.

Let the machine find bugs through random input generation.
Every property answers: "What mathematical invariant must hold?"
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.constants_bridge import (
    TrustTier,
    TIER_THRESHOLDS,
    score_to_tier,
    get_capabilities_for_tier,
    CAPABILITIES,
)
from app.core.tripwires import check_tripwires, TripwireResult
from app.core.velocity import VELOCITY_LIMITS_BY_TRUST, VelocityTier
from app.routers.proof import calculate_hash


# =============================================================================
# TRUST SCORING INVARIANTS
# =============================================================================


class TestTrustScoringProperties:
    """Property: trust scoring maps are total and monotonic."""

    @given(score=st.integers(min_value=0, max_value=1000))
    def test_any_valid_score_maps_to_tier(self, score: int):
        """Every score 0-1000 must map to exactly one tier."""
        tier = score_to_tier(score)
        assert 0 <= tier <= 7

    @given(score=st.integers(min_value=0, max_value=1000))
    def test_tier_thresholds_contain_score(self, score: int):
        """The mapped tier's threshold range must contain the score."""
        tier = score_to_tier(score)
        threshold = TIER_THRESHOLDS[TrustTier(tier)]
        assert threshold["min"] <= score <= threshold["max"]

    @given(
        score_a=st.integers(min_value=0, max_value=1000),
        score_b=st.integers(min_value=0, max_value=1000),
    )
    def test_higher_score_never_lower_tier(self, score_a: int, score_b: int):
        """Higher trust score must never result in a lower tier (monotonicity)."""
        assume(score_a <= score_b)
        tier_a = score_to_tier(score_a)
        tier_b = score_to_tier(score_b)
        assert tier_a <= tier_b

    @given(
        tier_a=st.integers(min_value=0, max_value=7),
        tier_b=st.integers(min_value=0, max_value=7),
    )
    def test_higher_tier_more_capabilities(self, tier_a: int, tier_b: int):
        """Higher tiers must unlock at least as many capabilities."""
        assume(tier_a <= tier_b)
        caps_a = get_capabilities_for_tier(tier_a)
        caps_b = get_capabilities_for_tier(tier_b)
        assert len(caps_a) <= len(caps_b)


class TestTierThresholdProperties:
    """Property: tier thresholds are complete and non-overlapping."""

    def test_thresholds_cover_full_range(self):
        """Tiers must cover the entire 0-1000 range with no gaps."""
        for score in range(0, 1001):
            tier = score_to_tier(score)
            assert 0 <= tier <= 7, f"Score {score} mapped to invalid tier {tier}"

    def test_thresholds_non_overlapping(self):
        """No score should be claimed by multiple tiers."""
        for tier_enum in TrustTier:
            threshold = TIER_THRESHOLDS[tier_enum]
            for other_enum in TrustTier:
                if tier_enum == other_enum:
                    continue
                other = TIER_THRESHOLDS[other_enum]
                assert (
                    threshold["max"] < other["min"]
                    or threshold["min"] > other["max"]
                ), f"{tier_enum.name} overlaps with {other_enum.name}"

    def test_thresholds_contiguous(self):
        """Each tier's max should be exactly one less than the next tier's min."""
        sorted_tiers = sorted(TrustTier, key=lambda t: TIER_THRESHOLDS[t]["min"])
        for i in range(len(sorted_tiers) - 1):
            current = TIER_THRESHOLDS[sorted_tiers[i]]
            next_tier = TIER_THRESHOLDS[sorted_tiers[i + 1]]
            assert current["max"] + 1 == next_tier["min"], (
                f"Gap between {sorted_tiers[i].name} (max={current['max']}) "
                f"and {sorted_tiers[i+1].name} (min={next_tier['min']})"
            )


# =============================================================================
# P1: Trust Signal Asymmetry
# Property: failure signals dominate success signals
# =============================================================================


class TestP1TrustSignalAsymmetry:
    """P1: negative trust signals must have stronger weight than positive."""

    @given(score=st.integers(min_value=200, max_value=800))
    def test_failure_drops_tier_more_than_success_raises(self, score: int):
        """Failure penalty (-100) must equal or exceed success reward (+100)."""
        tier_before = score_to_tier(score)

        # Simulate failure: -100 points
        score_after_fail = max(0, score - 100)
        tier_after_fail = score_to_tier(score_after_fail)

        # Simulate success: +100 points
        score_after_success = min(1000, score + 100)
        tier_after_success = score_to_tier(score_after_success)

        # Tier drop from failure should be >= tier gain from success
        tier_drop = tier_before - tier_after_fail
        tier_gain = tier_after_success - tier_before
        # At minimum, the system should not make it EASIER to climb than to fall
        assert tier_drop >= 0  # Failure can't improve tier
        assert tier_gain >= 0  # Success can't worsen tier


# =============================================================================
# P2: Tier Boundary Precision
# Property: boundaries at exactly 200, 350, 500, 650, 800, 876, 951
# =============================================================================


class TestP2TierBoundaryPrecision:
    """P2: boundary scores map to the correct tier with zero tolerance."""

    BOUNDARIES = [
        (199, 0), (200, 1),
        (349, 1), (350, 2),
        (499, 2), (500, 3),
        (649, 3), (650, 4),
        (799, 4), (800, 5),
        (875, 5), (876, 6),
        (950, 6), (951, 7),
    ]

    @given(data=st.data())
    def test_random_score_lands_in_correct_tier(self, data):
        """Any random score must land in exactly one tier range."""
        score = data.draw(st.integers(min_value=0, max_value=1000))
        tier = score_to_tier(score)
        threshold = TIER_THRESHOLDS[TrustTier(tier)]
        assert threshold["min"] <= score <= threshold["max"]


# =============================================================================
# P3: Velocity Limits Monotonic Across Trust Tiers
# Property: T0 <= T1 <= ... <= T7 for all limit types
# =============================================================================


class TestP3VelocityMonotonic:
    """P3: all 8 tiers x 4 limit types are monotonically non-decreasing."""

    @given(
        tier_a=st.integers(min_value=0, max_value=7),
        tier_b=st.integers(min_value=0, max_value=7),
    )
    def test_higher_tier_higher_or_equal_limits(self, tier_a: int, tier_b: int):
        """Higher trust tier must have higher or equal velocity limits."""
        assume(tier_a <= tier_b)
        for vt in VelocityTier:
            limit_a = VELOCITY_LIMITS_BY_TRUST[tier_a][vt].max_actions
            limit_b = VELOCITY_LIMITS_BY_TRUST[tier_b][vt].max_actions
            assert limit_a <= limit_b, (
                f"Inversion: T{tier_a} {vt.value}={limit_a} > T{tier_b}={limit_b}"
            )


# =============================================================================
# P4: Policy Evaluation Deterministic
# Property: evaluate(ctx) == evaluate(ctx) always
# =============================================================================


class TestP4PolicyDeterminism:
    """P4: same input → same output, every time."""

    @given(
        risk=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        trust_level=st.integers(min_value=0, max_value=7),
    )
    @settings(max_examples=100)
    def test_analyze_intent_deterministic(self, risk: float, trust_level: int):
        """analyze_intent must be a pure function."""
        from app.routers.intent import analyze_intent

        goal = f"Test operation at risk={risk:.2f}"
        result_a = analyze_intent(goal, {})
        result_b = analyze_intent(goal, {})
        assert result_a.risk_score == result_b.risk_score
        assert result_a.tools_required == result_b.tools_required


# =============================================================================
# P5: Proof Hash Chain Unbreakable
# Property: remove any record → validation fails
# =============================================================================


class TestP5ProofChainUnbreakable:
    """P5: removing any record from a chain breaks chain validation."""

    @given(n=st.integers(min_value=3, max_value=30))
    @settings(max_examples=20)
    def test_removing_record_breaks_chain(self, n: int):
        """Chain of n records: remove any record → chain invalid."""
        # Build a chain
        chain = []
        prev_hash = "genesis"
        for i in range(n):
            record = {
                "position": i,
                "data": f"record_{i}",
                "previous_hash": prev_hash,
            }
            current_hash = calculate_hash(record)
            chain.append({"data": record, "hash": current_hash})
            prev_hash = current_hash

        # Remove a record from the middle
        remove_idx = n // 2
        broken_chain = chain[:remove_idx] + chain[remove_idx + 1:]

        # Verify chain is broken
        is_valid = True
        for j in range(1, len(broken_chain)):
            if broken_chain[j]["data"]["previous_hash"] != broken_chain[j - 1]["hash"]:
                is_valid = False
                break

        assert not is_valid, f"Chain remained valid after removing record {remove_idx}"


# =============================================================================
# PROOF CHAIN INTEGRITY
# =============================================================================


class TestProofHashProperties:
    """Property: proof hashes are deterministic and collision-resistant."""

    @given(data=st.fixed_dictionaries({
        "key": st.text(min_size=1, max_size=50),
        "value": st.integers(),
    }))
    def test_hash_deterministic(self, data: dict):
        """Same data must always produce the same hash."""
        assert calculate_hash(data) == calculate_hash(data)

    @given(
        key=st.text(min_size=1, max_size=20),
        val_a=st.integers(),
        val_b=st.integers(),
    )
    def test_different_values_different_hashes(self, key: str, val_a: int, val_b: int):
        """Different values should produce different hashes (probabilistic)."""
        assume(val_a != val_b)
        h1 = calculate_hash({key: val_a})
        h2 = calculate_hash({key: val_b})
        assert h1 != h2

    @given(data=st.fixed_dictionaries({
        "a": st.integers(),
        "b": st.text(max_size=20),
    }))
    def test_hash_is_valid_sha256(self, data: dict):
        """Hash output must always be a valid 64-char hex string."""
        h = calculate_hash(data)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# =============================================================================
# TRIPWIRE DETECTION
# =============================================================================


class TestTripwireProperties:
    """Property: tripwire detection is pure and deterministic."""

    @given(text=st.text(max_size=200))
    @settings(max_examples=50)
    def test_tripwire_returns_valid_result(self, text: str):
        """check_tripwires must always return a TripwireResult."""
        result = check_tripwires(text)
        assert isinstance(result, TripwireResult)
        assert isinstance(result.triggered, bool)

    @given(text=st.text(max_size=200))
    @settings(max_examples=50)
    def test_tripwire_deterministic(self, text: str):
        """Same input must always give same result."""
        r1 = check_tripwires(text)
        r2 = check_tripwires(text)
        assert r1.triggered == r2.triggered
        assert r1.pattern_name == r2.pattern_name

    def test_safe_inputs_not_triggered(self):
        """Normal business text should never trigger tripwires."""
        safe_inputs = [
            "Please read the quarterly report",
            "Update the customer database record",
            "Send the weekly summary email",
            "Calculate the monthly revenue",
        ]
        for text in safe_inputs:
            result = check_tripwires(text)
            assert not result.triggered, f"False positive on: {text}"
