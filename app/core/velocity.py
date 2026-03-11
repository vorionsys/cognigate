# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
VELOCITY CAPS - Rate Limiting for Autonomous Agents (L0-L2)

Prevents "runaway" agents by enforcing hard limits on action frequency.
Even if an agent's logic says "spam 1000 emails," the velocity cap
physically blocks the API calls.

Three tiers of velocity control:
- L0: Per-second burst limit (prevents instant floods)
- L1: Per-minute sustained limit (prevents short-term abuse)
- L2: Per-hour/day quotas (prevents long-term resource drain)

All limits are per-entity, meaning each agent has its own quota.
"""

import bisect
import time
import asyncio
import structlog
from typing import Optional
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class VelocityTier(Enum):
    """Velocity limit tiers."""
    L0_BURST = "L0_burst"      # Per-second
    L1_SUSTAINED = "L1_sustained"  # Per-minute
    L2_HOURLY = "L2_hourly"    # Per-hour
    L2_DAILY = "L2_daily"      # Per-day


@dataclass
class VelocityLimit:
    """Configuration for a velocity limit."""
    tier: VelocityTier
    max_actions: int
    window_seconds: int
    description: str


@dataclass
class VelocityState:
    """Tracks velocity state for an entity."""
    entity_id: str
    action_timestamps: deque = field(default_factory=lambda: deque(maxlen=100000))  # Use deque for O(1) operations
    total_actions: int = 0
    violations: int = 0
    last_violation: Optional[float] = None
    is_throttled: bool = False
    throttle_until: Optional[float] = None


@dataclass
class VelocityCheckResult:
    """Result of a velocity check."""
    allowed: bool
    tier_violated: Optional[VelocityTier] = None
    current_rate: float = 0.0
    limit: int = 0
    window: str = ""
    retry_after_seconds: Optional[float] = None
    message: str = ""


# Default velocity limits by trust level — canonical 8-tier model (T0-T7)
# Higher trust = higher limits
VELOCITY_LIMITS_BY_TRUST = {
    0: {  # T0 Sandbox
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 2, 1, "2 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 10, 60, "10 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 50, 3600, "50 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 200, 86400, "200 actions/day"),
    },
    1: {  # T1 Observed
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 5, 1, "5 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 30, 60, "30 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 200, 3600, "200 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 1000, 86400, "1000 actions/day"),
    },
    2: {  # T2 Provisional
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 10, 1, "10 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 60, 60, "60 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 500, 3600, "500 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 5000, 86400, "5000 actions/day"),
    },
    3: {  # T3 Monitored
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 20, 1, "20 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 120, 60, "120 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 2000, 3600, "2000 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 20000, 86400, "20000 actions/day"),
    },
    4: {  # T4 Standard
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 50, 1, "50 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 300, 60, "300 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 10000, 3600, "10000 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 100000, 86400, "100000 actions/day"),
    },
    5: {  # T5 Trusted
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 100, 1, "100 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 600, 60, "600 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 25000, 3600, "25000 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 250000, 86400, "250000 actions/day"),
    },
    6: {  # T6 Certified
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 200, 1, "200 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 1200, 60, "1200 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 50000, 3600, "50000 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 500000, 86400, "500000 actions/day"),
    },
    7: {  # T7 Autonomous
        VelocityTier.L0_BURST: VelocityLimit(VelocityTier.L0_BURST, 500, 1, "500 actions/second"),
        VelocityTier.L1_SUSTAINED: VelocityLimit(VelocityTier.L1_SUSTAINED, 3000, 60, "3000 actions/minute"),
        VelocityTier.L2_HOURLY: VelocityLimit(VelocityTier.L2_HOURLY, 100000, 3600, "100000 actions/hour"),
        VelocityTier.L2_DAILY: VelocityLimit(VelocityTier.L2_DAILY, 1000000, 86400, "1000000 actions/day"),
    },
}


class VelocityTracker:
    """
    Async-safe velocity tracker for all entities.

    In production, this would be backed by Redis for distributed tracking.
    Current implementation uses in-memory storage with async/await patterns.
    """

    def __init__(self):
        self._states: dict[str, VelocityState] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, entity_id: str) -> VelocityState:
        """Get or create state for an entity."""
        if entity_id not in self._states:
            self._states[entity_id] = VelocityState(entity_id=entity_id)
        return self._states[entity_id]

    def _prune_old_timestamps(self, state: VelocityState, max_age: int = 86400):
        """Remove timestamps older than max_age seconds.

        Preserves the deque type with its maxlen constraint.
        Previous implementation replaced deque with list — this was a bug
        that lost the O(1) append guarantees and maxlen safety.
        """
        now = time.time()
        cutoff = now - max_age
        # Pop from left while entries are older than cutoff.
        # Timestamps are appended in order, so leftmost is oldest.
        while state.action_timestamps and state.action_timestamps[0] <= cutoff:
            state.action_timestamps.popleft()

    def _count_actions_in_window(self, state: VelocityState, window_seconds: int) -> int:
        """Count actions within a time window.

        Uses bisect for O(log n) lookup since timestamps are monotonically
        increasing (always appended via record_action).
        """
        cutoff = time.time() - window_seconds
        # bisect_right returns the insertion point after all entries <= cutoff.
        # Everything from that index onwards is strictly > cutoff.
        idx = bisect.bisect_right(state.action_timestamps, cutoff)
        return len(state.action_timestamps) - idx

    async def check_velocity(
        self,
        entity_id: str,
        trust_level: int = 1,
    ) -> VelocityCheckResult:
        """
        Check if an entity is within velocity limits.

        Args:
            entity_id: The entity to check
            trust_level: Entity's trust level (0-7)

        Returns:
            VelocityCheckResult with allowed=True/False
        """
        async with self._lock:
            state = self._get_state(entity_id)
            now = time.time()

            # Check if currently throttled
            if state.is_throttled and state.throttle_until:
                if now < state.throttle_until:
                    return VelocityCheckResult(
                        allowed=False,
                        message=f"Entity is throttled until {state.throttle_until}",
                        retry_after_seconds=state.throttle_until - now,
                    )
                else:
                    # Throttle expired
                    state.is_throttled = False
                    state.throttle_until = None

            # Prune old timestamps
            self._prune_old_timestamps(state)

            # Get limits for trust level
            limits = VELOCITY_LIMITS_BY_TRUST.get(trust_level, VELOCITY_LIMITS_BY_TRUST[1])

            # Check each tier (L0 → L1 → L2)
            for tier in [VelocityTier.L0_BURST, VelocityTier.L1_SUSTAINED,
                        VelocityTier.L2_HOURLY, VelocityTier.L2_DAILY]:
                limit = limits[tier]
                count = self._count_actions_in_window(state, limit.window_seconds)

                if count >= limit.max_actions:
                    state.violations += 1
                    state.last_violation = now

                    # Calculate retry time: find first timestamp inside the window
                    # (bisect_right gives index of first entry > cutoff)
                    cutoff = now - limit.window_seconds
                    idx = bisect.bisect_right(state.action_timestamps, cutoff)
                    oldest_in_window = state.action_timestamps[idx] if idx < len(state.action_timestamps) else now
                    retry_after = (oldest_in_window + limit.window_seconds) - now

                    logger.warning(
                        "velocity_limit_exceeded",
                        entity_id=entity_id,
                        tier=tier.value,
                        count=count,
                        limit=limit.max_actions,
                        violations=state.violations,
                    )

                    # Escalation: auto-throttle on repeated violations (3+)
                    # Exponential throttle duration: 30s, 60s, 120s, ...
                    if state.violations >= 3:
                        escalation_duration = min(
                            30.0 * (2 ** (state.violations - 3)),
                            3600.0,  # Cap at 1 hour
                        )
                        state.is_throttled = True
                        state.throttle_until = now + escalation_duration
                        logger.warning(
                            "velocity_auto_throttle",
                            entity_id=entity_id,
                            violations=state.violations,
                            throttle_seconds=escalation_duration,
                        )

                    return VelocityCheckResult(
                        allowed=False,
                        tier_violated=tier,
                        current_rate=count,
                        limit=limit.max_actions,
                        window=limit.description,
                        retry_after_seconds=retry_after,
                        message=f"Velocity limit exceeded: {count}/{limit.max_actions} ({limit.description})",
                    )

            return VelocityCheckResult(
                allowed=True,
                message="Within velocity limits",
            )

    async def record_action(self, entity_id: str):
        """Record an action for an entity."""
        async with self._lock:
            state = self._get_state(entity_id)
            state.action_timestamps.append(time.time())
            state.total_actions += 1

    async def throttle_entity(self, entity_id: str, duration_seconds: float = 300):
        """Manually throttle an entity."""
        async with self._lock:
            state = self._get_state(entity_id)
            state.is_throttled = True
            state.throttle_until = time.time() + duration_seconds
            logger.warning(
                "entity_throttled",
                entity_id=entity_id,
                duration_seconds=duration_seconds,
            )

    async def unthrottle_entity(self, entity_id: str):
        """Remove throttle from an entity."""
        async with self._lock:
            state = self._get_state(entity_id)
            state.is_throttled = False
            state.throttle_until = None
            logger.info("entity_unthrottled", entity_id=entity_id)

    async def get_stats(self, entity_id: str) -> dict:
        """Get velocity statistics for an entity."""
        async with self._lock:
            state = self._get_state(entity_id)

            return {
                "entity_id": entity_id,
                "total_actions": state.total_actions,
                "violations": state.violations,
                "is_throttled": state.is_throttled,
                "throttle_until": state.throttle_until,
                "actions_last_minute": self._count_actions_in_window(state, 60),
                "actions_last_hour": self._count_actions_in_window(state, 3600),
                "actions_last_day": self._count_actions_in_window(state, 86400),
            }

    async def get_all_stats(self) -> list[dict]:
        """Get velocity statistics for all entities.

        Uses _get_stats_unlocked instead of get_stats to avoid
        re-acquiring the async lock (which would cause a deadlock).
        """
        async with self._lock:
            stats = []
            for eid in self._states.keys():
                stats.append(self._get_stats_unlocked(eid))
            return stats

    def _get_stats_unlocked(self, entity_id: str) -> dict:
        """Get velocity statistics without acquiring the lock.

        Used internally by get_all_stats to avoid deadlock.
        Caller MUST hold self._lock.
        """
        state = self._get_state(entity_id)
        return {
            "entity_id": entity_id,
            "total_actions": state.total_actions,
            "violations": state.violations,
            "is_throttled": state.is_throttled,
            "throttle_until": state.throttle_until,
            "actions_last_minute": self._count_actions_in_window(state, 60),
            "actions_last_hour": self._count_actions_in_window(state, 3600),
            "actions_last_day": self._count_actions_in_window(state, 86400),
        }


# Global velocity tracker instance
velocity_tracker = VelocityTracker()


def reset_velocity_tracker():
    """Reset the global velocity tracker state.

    Used between tests to prevent state pollution. In production, state
    is per-process and reset on restart.
    """
    global velocity_tracker
    velocity_tracker = VelocityTracker()


async def check_velocity(entity_id: str, trust_level: int = 1) -> VelocityCheckResult:
    """Check velocity limits for an entity."""
    return await velocity_tracker.check_velocity(entity_id, trust_level)


async def record_action(entity_id: str):
    """Record an action for velocity tracking."""
    await velocity_tracker.record_action(entity_id)


async def throttle_entity(entity_id: str, duration_seconds: float = 300):
    """Throttle an entity."""
    await velocity_tracker.throttle_entity(entity_id, duration_seconds)


async def get_velocity_stats(entity_id: str) -> dict:
    """Get velocity stats for an entity."""
    return await velocity_tracker.get_stats(entity_id)
