# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Stepped Trust Decay — 182-day half-life inactivity decay model.

Implements the Vorion stepped decay schedule as specified in the
BASIS trust-scoring spec. When an agent has no trust-relevant
activity for an extended period, its trust score decays along a
9-milestone staircase, reaching 50% (the floor) at 182 days.

The schedule is:
  Day   Cumulative  Per-Step
    0     1.00        —
    7     0.98        2%
   14     0.95        3%
   28     0.90        5%
   42     0.85        5%
   56     0.80        5%
   84     0.70       10%
  112     0.60       10%
  140     0.55        5%
  182     0.50        5%

After day 182 the score stays at the floor (50% of pre-decay value).
Any trust-relevant signal resets the inactivity timer.
"""

from __future__ import annotations

from typing import NamedTuple


class DecayMilestone(NamedTuple):
    """A single milestone in the stepped decay schedule."""
    day: int
    cumulative_factor: float


# Canonical 182-day stepped decay schedule.
# Aligned with BASIS spec § Trust Decay.
DECAY_MILESTONES: list[DecayMilestone] = [
    DecayMilestone(day=0,   cumulative_factor=1.00),
    DecayMilestone(day=7,   cumulative_factor=0.98),
    DecayMilestone(day=14,  cumulative_factor=0.95),
    DecayMilestone(day=28,  cumulative_factor=0.90),
    DecayMilestone(day=42,  cumulative_factor=0.85),
    DecayMilestone(day=56,  cumulative_factor=0.80),
    DecayMilestone(day=84,  cumulative_factor=0.70),
    DecayMilestone(day=112, cumulative_factor=0.60),
    DecayMilestone(day=140, cumulative_factor=0.55),
    DecayMilestone(day=182, cumulative_factor=0.50),
]

# Default floor: score never decays below this fraction of pre-decay value.
DECAY_FLOOR: float = 0.50

# Half-life in days (the day at which cumulative_factor == 0.50).
DECAY_HALF_LIFE_DAYS: int = 182


def compute_decay_factor(days_inactive: float, floor: float = DECAY_FLOOR) -> float:
    """
    Compute the cumulative decay factor for a given number of inactive days.

    Uses the stepped milestone schedule. Between milestones the factor is
    linearly interpolated. Beyond the last milestone the floor applies.

    Parameters
    ----------
    days_inactive : float
        Number of days since the agent's last trust-relevant activity.
    floor : float
        Minimum decay factor (default 0.50).

    Returns
    -------
    float
        Decay factor in [floor, 1.0] to multiply against the pre-decay score.
    """
    if days_inactive <= 0:
        return 1.0

    # Walk the milestones to find the surrounding pair.
    for i in range(len(DECAY_MILESTONES) - 1):
        current = DECAY_MILESTONES[i]
        nxt = DECAY_MILESTONES[i + 1]
        if days_inactive <= nxt.day:
            # Linear interpolation between milestones.
            span = nxt.day - current.day
            progress = (days_inactive - current.day) / span if span > 0 else 1.0
            factor = current.cumulative_factor + progress * (
                nxt.cumulative_factor - current.cumulative_factor
            )
            return max(factor, floor)

    # Beyond the last milestone — clamp to floor.
    return floor


def apply_decay(pre_decay_score: int, days_inactive: float, floor: float = DECAY_FLOOR) -> int:
    """
    Apply stepped inactivity decay to a trust score.

    Parameters
    ----------
    pre_decay_score : int
        The agent's trust score at the time of last activity.
    days_inactive : float
        Days since last trust-relevant activity.
    floor : float
        Minimum fraction of pre-decay score retained.

    Returns
    -------
    int
        Decayed score, clamped to [0, 1000].
    """
    factor = compute_decay_factor(days_inactive, floor)
    decayed = int(pre_decay_score * factor)
    return max(0, min(1000, decayed))
