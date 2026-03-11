# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Triple Modular Redundancy (TMR) Consensus Engine.

Inspired by NASA's TMR in spacecraft avionics (Curiosity, Perseverance),
this module implements fault-tolerant multi-model consensus for high-risk
AI agent actions.  When risk ρ ≥ 80 (CRITICAL), multiple parallel
inference replicas vote on outputs; divergence derates the composite
trust score via an exponential decay factor.

Degradation levels:
  FULL       — consensus_factor ≥ 0.90: full autonomy retained
  ELEVATED   — consensus_factor ∈ [0.70, 0.90): minor derate, log warning
  DEGRADED   — consensus_factor ∈ [0.50, 0.70): moderate derate, cap tier
  RESTRICTED — consensus_factor ∈ [0.30, 0.50): heavy derate, human review
  SAFE_MODE  — consensus_factor < 0.30: sandbox (T0), block execution

The composite trust score is:
    S_composite = min(S_i) × consensus_factor

where consensus_factor = exp(−avg_divergence / threshold).

Architecture:
  Pre-Action Gating → spin up N replicas → compare activations
  (via Paramesphere δ_e fingerprints) → vote → derate if divergent
  → return composite trust or trigger safe mode.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum risk score (0-100) to trigger consensus voting.
CONSENSUS_RISK_THRESHOLD: int = 80

# Default divergence threshold in trust-score points.
# Average divergence above this triggers exponential derating.
DEFAULT_DIVERGENCE_THRESHOLD: float = 10.0

# Minimum replicas required for valid consensus.
MIN_REPLICAS: int = 3

# Maximum safe-mode trust score (forced to T0 Sandbox).
SAFE_MODE_MAX_SCORE: int = 199


class DegradationLevel(str, Enum):
    """Graceful degradation levels based on consensus factor."""
    FULL = "FULL"              # ≥ 0.90 — no restrictions
    ELEVATED = "ELEVATED"      # 0.70–0.90 — minor derate
    DEGRADED = "DEGRADED"      # 0.50–0.70 — cap to T4
    RESTRICTED = "RESTRICTED"  # 0.30–0.50 — human review required
    SAFE_MODE = "SAFE_MODE"    # < 0.30 — sandbox (T0)


# Degradation level → tier ceiling map.  None means "no cap".
DEGRADATION_TIER_CAPS: dict[DegradationLevel, Optional[int]] = {
    DegradationLevel.FULL: None,
    DegradationLevel.ELEVATED: 7,      # T7 max
    DegradationLevel.DEGRADED: 4,      # T4 max
    DegradationLevel.RESTRICTED: 2,    # T2 max
    DegradationLevel.SAFE_MODE: 0,     # T0 forced
}


def _degradation_level(factor: float) -> DegradationLevel:
    """Classify a consensus factor into a degradation level."""
    if factor >= 0.90:
        return DegradationLevel.FULL
    if factor >= 0.70:
        return DegradationLevel.ELEVATED
    if factor >= 0.50:
        return DegradationLevel.DEGRADED
    if factor >= 0.30:
        return DegradationLevel.RESTRICTED
    return DegradationLevel.SAFE_MODE


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReplicaOutput:
    """Output from a single inference replica."""
    replica_id: str
    trust_score: int          # The trust score this replica reports
    activation_hash: str = "" # Paramesphere fingerprint (optional)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """Result of a TMR consensus vote."""
    composite_score: int
    consensus_factor: float
    degradation_level: DegradationLevel
    tier_cap: Optional[int]
    avg_divergence: float
    max_divergence: float
    replica_count: int
    min_score: int
    max_score: int
    requires_human_review: bool
    blocked: bool              # True if SAFE_MODE
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_consensus_factor(
    divergences: list[float],
    threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
) -> float:
    """
    Compute the consensus factor from pairwise divergences.

    Uses exponential decay:  factor = exp(−avg_div / threshold)

    Parameters
    ----------
    divergences : list[float]
        Pairwise absolute divergences between replica trust scores.
    threshold : float
        Divergence threshold — at this avg divergence, factor ≈ 0.368.

    Returns
    -------
    float
        Consensus factor in (0, 1].
    """
    if not divergences:
        return 1.0
    avg_div = statistics.mean(divergences)
    if avg_div <= 0:
        return 1.0
    return math.exp(-avg_div / max(threshold, 0.01))


def compute_pairwise_divergences(scores: list[int]) -> list[float]:
    """
    Compute all pairwise absolute divergences between scores.

    For N scores, produces N*(N-1)/2 divergence values.
    """
    divs: list[float] = []
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            divs.append(abs(scores[i] - scores[j]))
    return divs


def vote(
    replicas: list[ReplicaOutput],
    threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
    risk_score: float = 0.0,
) -> ConsensusResult:
    """
    Run TMR consensus vote on replica outputs.

    Parameters
    ----------
    replicas : list[ReplicaOutput]
        Outputs from N parallel inference replicas.
    threshold : float
        Divergence threshold for derating.
    risk_score : float
        The pre-action risk score (ρ). If < CONSENSUS_RISK_THRESHOLD,
        voting is a no-op and returns full trust.

    Returns
    -------
    ConsensusResult
        Composite trust score with degradation status.
    """
    if len(replicas) < MIN_REPLICAS:
        raise ValueError(
            f"TMR consensus requires at least {MIN_REPLICAS} replicas, "
            f"got {len(replicas)}"
        )

    scores = [r.trust_score for r in replicas]
    min_score = min(scores)
    max_score = max(scores)

    # If risk is below threshold, bypass voting — return minimum score directly.
    if risk_score < CONSENSUS_RISK_THRESHOLD:
        return ConsensusResult(
            composite_score=min_score,
            consensus_factor=1.0,
            degradation_level=DegradationLevel.FULL,
            tier_cap=None,
            avg_divergence=0.0,
            max_divergence=float(max_score - min_score),
            replica_count=len(replicas),
            min_score=min_score,
            max_score=max_score,
            requires_human_review=False,
            blocked=False,
            details={"bypassed": True, "reason": "risk_below_threshold"},
        )

    # Compute divergences and consensus factor.
    divs = compute_pairwise_divergences(scores)
    avg_div = statistics.mean(divs) if divs else 0.0
    max_div = max(divs) if divs else 0.0
    factor = compute_consensus_factor(divs, threshold)

    # Composite trust = min(S_i) × factor.
    composite = int(min_score * factor)
    composite = max(0, min(1000, composite))

    # Determine degradation level.
    level = _degradation_level(factor)
    tier_cap = DEGRADATION_TIER_CAPS[level]

    return ConsensusResult(
        composite_score=composite,
        consensus_factor=round(factor, 6),
        degradation_level=level,
        tier_cap=tier_cap,
        avg_divergence=round(avg_div, 2),
        max_divergence=round(max_div, 2),
        replica_count=len(replicas),
        min_score=min_score,
        max_score=max_score,
        requires_human_review=(level == DegradationLevel.RESTRICTED),
        blocked=(level == DegradationLevel.SAFE_MODE),
        details={
            "scores": scores,
            "pairwise_divergences": [round(d, 2) for d in divs],
        },
    )


def quick_consensus(
    scores: list[int],
    threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
    risk_score: float = 100.0,
) -> ConsensusResult:
    """
    Convenience wrapper — run consensus from raw trust scores.

    Creates anonymous ReplicaOutputs and runs ``vote()``.
    """
    replicas = [
        ReplicaOutput(replica_id=f"r{i}", trust_score=s)
        for i, s in enumerate(scores)
    ]
    return vote(replicas, threshold=threshold, risk_score=risk_score)
