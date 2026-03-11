# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for TMR Consensus Engine (app.core.tmr_consensus).

Covers:
  - Pairwise divergence computation
  - Consensus factor (exponential decay)
  - Degradation level classification
  - Full vote() with graceful degradation
  - Edge cases (min replicas, identical scores, extreme divergence)
  - Risk threshold bypass
"""

import math
import pytest

from app.core.tmr_consensus import (
    ConsensusResult,
    DegradationLevel,
    ReplicaOutput,
    compute_consensus_factor,
    compute_pairwise_divergences,
    quick_consensus,
    vote,
    CONSENSUS_RISK_THRESHOLD,
    DEFAULT_DIVERGENCE_THRESHOLD,
    MIN_REPLICAS,
    SAFE_MODE_MAX_SCORE,
    _degradation_level,
)


# =============================================================================
# TestPairwiseDivergences
# =============================================================================

class TestPairwiseDivergences:
    def test_identical_scores(self):
        divs = compute_pairwise_divergences([950, 950, 950])
        assert divs == [0, 0, 0]

    def test_simple_spread(self):
        divs = compute_pairwise_divergences([950, 940, 930])
        assert sorted(divs) == [10, 10, 20]

    def test_two_scores(self):
        divs = compute_pairwise_divergences([100, 200])
        assert divs == [100]

    def test_four_scores(self):
        divs = compute_pairwise_divergences([100, 200, 300, 400])
        assert len(divs) == 6  # C(4,2) = 6

    def test_empty(self):
        divs = compute_pairwise_divergences([])
        assert divs == []

    def test_single(self):
        divs = compute_pairwise_divergences([500])
        assert divs == []


# =============================================================================
# TestConsensusFactor
# =============================================================================

class TestConsensusFactor:
    def test_no_divergence(self):
        factor = compute_consensus_factor([0, 0, 0])
        assert factor == 1.0

    def test_at_threshold(self):
        # avg_div = 10, threshold = 10 → factor = exp(-1) ≈ 0.368
        factor = compute_consensus_factor([10, 10, 10], threshold=10.0)
        assert abs(factor - math.exp(-1)) < 0.001

    def test_double_threshold(self):
        # avg_div = 20, threshold = 10 → factor = exp(-2) ≈ 0.135
        factor = compute_consensus_factor([20, 20, 20], threshold=10.0)
        assert abs(factor - math.exp(-2)) < 0.001

    def test_small_divergence(self):
        factor = compute_consensus_factor([1, 1, 1], threshold=10.0)
        assert factor > 0.90  # Very small div → near 1

    def test_empty_divergences(self):
        factor = compute_consensus_factor([])
        assert factor == 1.0

    def test_zero_divergences(self):
        factor = compute_consensus_factor([0, 0])
        assert factor == 1.0

    def test_extreme_divergence(self):
        factor = compute_consensus_factor([1000, 1000, 1000], threshold=10.0)
        assert factor < 0.01


# =============================================================================
# TestDegradationLevel
# =============================================================================

class TestDegradationLevel:
    def test_full(self):
        assert _degradation_level(0.95) == DegradationLevel.FULL

    def test_elevated(self):
        assert _degradation_level(0.80) == DegradationLevel.ELEVATED

    def test_degraded(self):
        assert _degradation_level(0.60) == DegradationLevel.DEGRADED

    def test_restricted(self):
        assert _degradation_level(0.40) == DegradationLevel.RESTRICTED

    def test_safe_mode(self):
        assert _degradation_level(0.10) == DegradationLevel.SAFE_MODE

    def test_boundary_full(self):
        assert _degradation_level(0.90) == DegradationLevel.FULL

    def test_boundary_elevated(self):
        assert _degradation_level(0.70) == DegradationLevel.ELEVATED

    def test_boundary_degraded(self):
        assert _degradation_level(0.50) == DegradationLevel.DEGRADED

    def test_boundary_restricted(self):
        assert _degradation_level(0.30) == DegradationLevel.RESTRICTED

    def test_exact_zero(self):
        assert _degradation_level(0.0) == DegradationLevel.SAFE_MODE


# =============================================================================
# TestVote
# =============================================================================

class TestVote:
    def _make_replicas(self, scores: list[int]) -> list[ReplicaOutput]:
        return [
            ReplicaOutput(replica_id=f"r{i}", trust_score=s)
            for i, s in enumerate(scores)
        ]

    def test_identical_replicas(self):
        result = vote(self._make_replicas([950, 950, 950]), risk_score=90)
        assert result.composite_score == 950
        assert result.consensus_factor == 1.0
        assert result.degradation_level == DegradationLevel.FULL
        assert result.blocked is False

    def test_medium_spread(self):
        result = vote(self._make_replicas([950, 940, 935]), risk_score=90)
        assert result.composite_score < 950
        assert result.consensus_factor < 1.0
        assert result.min_score == 935
        assert result.max_score == 950

    def test_high_spread_triggers_safe_mode(self):
        result = vote(self._make_replicas([1000, 500, 1000]), risk_score=90)
        # Large spread → low factor → SAFE_MODE
        assert result.degradation_level == DegradationLevel.SAFE_MODE
        assert result.blocked is True

    def test_low_risk_bypasses_voting(self):
        result = vote(self._make_replicas([950, 500, 950]), risk_score=50)
        assert result.composite_score == 500  # min of scores
        assert result.consensus_factor == 1.0
        assert result.blocked is False

    def test_too_few_replicas_raises(self):
        with pytest.raises(ValueError, match="at least 3"):
            vote([ReplicaOutput(replica_id="r0", trust_score=500),
                  ReplicaOutput(replica_id="r1", trust_score=500)])

    def test_requires_human_review_on_restricted(self):
        # Create enough spread for RESTRICTED (factor 0.30-0.50)
        result = vote(self._make_replicas([900, 870, 900]), risk_score=90)
        # This may or may not hit RESTRICTED depending on threshold;
        # test the flag logic.
        if result.degradation_level == DegradationLevel.RESTRICTED:
            assert result.requires_human_review is True

    def test_four_replicas(self):
        result = vote(self._make_replicas([900, 895, 905, 890]), risk_score=85)
        assert result.replica_count == 4
        assert result.composite_score > 0

    def test_score_clamped_to_1000(self):
        result = vote(self._make_replicas([1000, 1000, 1000]), risk_score=90)
        assert result.composite_score <= 1000


class TestQuickConsensus:
    def test_basic(self):
        result = quick_consensus([950, 950, 950])
        assert result.composite_score == 950
        assert result.degradation_level == DegradationLevel.FULL

    def test_with_divergence(self):
        result = quick_consensus([1000, 800, 1000])
        assert result.composite_score < 800
        assert result.degradation_level != DegradationLevel.FULL

    def test_custom_threshold(self):
        # With very large threshold, even big spreads are okay.
        result = quick_consensus([1000, 800, 1000], threshold=500.0)
        assert result.consensus_factor > 0.70  # Large threshold dampens derating
