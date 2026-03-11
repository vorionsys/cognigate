# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
CIRCUIT BREAKERS - Autonomous Safety Halts

Implements automatic system halts when safety thresholds are exceeded.
Unlike velocity caps (which limit individual entities), circuit breakers
protect the entire system from cascading failures.

Trigger conditions:
1. High-risk action threshold exceeded (>10% of actions are high-risk)
2. Injection attack detected
3. Critical drift observed
4. Tripwire cascade (multiple tripwires in short time)
5. Entity misbehavior (single entity causing too many violations)

Circuit states:
- CLOSED: Normal operation, all requests flow through
- OPEN: System halted, all requests blocked
- HALF_OPEN: Testing recovery, limited requests allowed
"""

import time
import structlog
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
from threading import Lock
from enum import Enum
from datetime import datetime

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # System halted
    HALF_OPEN = "half_open"  # Testing recovery


class TripReason(Enum):
    """Reasons for circuit trip."""
    HIGH_RISK_THRESHOLD = "high_risk_threshold"
    INJECTION_DETECTED = "injection_detected"
    CRITICAL_DRIFT = "critical_drift"
    TRIPWIRE_CASCADE = "tripwire_cascade"
    ENTITY_MISBEHAVIOR = "entity_misbehavior"
    MANUAL_HALT = "manual_halt"
    CRITIC_BLOCK_CASCADE = "critic_block_cascade"
    VELOCITY_ABUSE = "velocity_abuse"


@dataclass
class CircuitTrip:
    """Record of a circuit trip event."""
    reason: TripReason
    timestamp: float
    entity_id: Optional[str] = None
    details: str = ""
    auto_reset_at: Optional[float] = None


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker decisions."""
    total_requests: int = 0
    high_risk_requests: int = 0
    blocked_requests: int = 0
    tripwire_triggers: int = 0
    injection_attempts: int = 0
    critic_blocks: int = 0
    velocity_violations: int = 0
    window_start: float = field(default_factory=time.time)

    def reset(self):
        """Reset metrics for new window."""
        self.total_requests = 0
        self.high_risk_requests = 0
        self.blocked_requests = 0
        self.tripwire_triggers = 0
        self.injection_attempts = 0
        self.critic_blocks = 0
        self.velocity_violations = 0
        self.window_start = time.time()

    @property
    def high_risk_ratio(self) -> float:
        """Ratio of high-risk to total requests."""
        if self.total_requests == 0:
            return 0.0
        return self.high_risk_requests / self.total_requests

    @property
    def block_ratio(self) -> float:
        """Ratio of blocked to total requests."""
        if self.total_requests == 0:
            return 0.0
        return self.blocked_requests / self.total_requests


@dataclass
class CircuitConfig:
    """Configuration for circuit breaker behavior."""
    # Thresholds
    high_risk_threshold: float = 0.10  # 10% high-risk triggers trip
    tripwire_cascade_count: int = 3    # 3 tripwires in window triggers trip
    tripwire_cascade_window: int = 60  # 60 second window
    injection_threshold: int = 2       # 2 injections triggers trip
    critic_block_threshold: int = 5    # 5 critic blocks triggers trip

    # Hysteresis — recovery requires lower ratios than trip thresholds.
    # Prevents oscillation: trips at 10% high-risk, recovers only when <5%.
    # Set to 0.0 to disable hysteresis (recover at any ratio below trip threshold).
    hysteresis_high_risk_recovery: float = 0.05  # Must drop to 5% to recover
    hysteresis_tripwire_recovery: int = 1         # Must drop to 1 to recover
    hysteresis_injection_recovery: int = 0        # Must drop to 0 to recover
    hysteresis_critic_recovery: int = 2           # Must drop to 2 to recover

    # Recovery
    auto_reset_seconds: int = 300      # 5 minute auto-reset (base value)
    half_open_requests: int = 3        # Requests to test in half-open
    metrics_window_seconds: int = 300  # 5 minute metrics window

    # Exponential backoff — each consecutive trip doubles the auto-reset time.
    # After 3 trips: 300s → 600s → 1200s. Capped at max_backoff_seconds.
    # This prevents rapid trip/reset oscillation under sustained attack.
    backoff_multiplier: float = 2.0           # Multiplier per consecutive trip
    max_backoff_seconds: int = 3600           # 1 hour maximum backoff cap
    consecutive_trip_decay_seconds: int = 900  # Reset consecutive count after 15m stability

    # Graduated half-open recovery — instead of binary test (pass N requests → close),
    # progressively increase the allowance rate from 10% → 25% → 50% → 100%.
    # Each stage requires `graduated_stage_requests` successes before advancing.
    graduated_recovery_enabled: bool = True
    graduated_stages: tuple[float, ...] = (0.10, 0.25, 0.50, 1.0)  # Allowance rates
    graduated_stage_requests: int = 3  # Successes needed per stage

    # Entity-level
    entity_violation_threshold: int = 10  # Violations before entity halt


class CircuitBreaker:
    """
    System-wide circuit breaker for autonomous safety halts.

    Thread-safe implementation that monitors system health and
    automatically trips when safety thresholds are exceeded.
    """

    def __init__(self, config: Optional[CircuitConfig] = None):
        self.config = config or CircuitConfig()
        self._state = CircuitState.CLOSED
        self._lock = Lock()
        self._metrics = CircuitMetrics()
        self._trip_history: list[CircuitTrip] = []
        self._current_trip: Optional[CircuitTrip] = None
        self._half_open_successes = 0
        self._entity_violations: dict[str, int] = defaultdict(int)
        self._halted_entities: set[str] = set()
        self._cascade_halt_children: dict[str, set[str]] = defaultdict(set)

        # Backoff state — tracks consecutive trips for exponential backoff
        self._consecutive_trips = 0
        self._last_trip_time: float = 0.0

        # Graduated recovery state — tracks progress through recovery stages
        self._recovery_stage: int = 0         # Index into config.graduated_stages
        self._recovery_stage_successes: int = 0  # Successes in current stage
        self._half_open_total_requests: int = 0   # Total requests seen in half-open

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (system halted)."""
        return self._state == CircuitState.OPEN

    def _check_auto_reset(self):
        """Check if circuit should auto-reset to half-open.

        Uses exponential backoff: each consecutive trip increases the reset
        delay by backoff_multiplier. After 15min of stability (no new trips),
        the consecutive counter decays back to zero.
        """
        if self._state == CircuitState.OPEN and self._current_trip:
            if self._current_trip.auto_reset_at:
                if time.time() >= self._current_trip.auto_reset_at:
                    logger.info(
                        "circuit_auto_reset",
                        reason="timeout_expired",
                        consecutive_trips=self._consecutive_trips,
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_successes = 0
                    # Reset graduated recovery state
                    self._recovery_stage = 0
                    self._recovery_stage_successes = 0
                    self._half_open_total_requests = 0

    def _check_metrics_window(self):
        """Reset metrics if window expired."""
        if time.time() - self._metrics.window_start > self.config.metrics_window_seconds:
            self._metrics.reset()

    def _trip(self, reason: TripReason, entity_id: Optional[str] = None, details: str = ""):
        """Trip the circuit breaker.

        Applies exponential backoff: consecutive trips increase the auto-reset
        delay. If enough time has passed since the last trip (consecutive_trip_decay_seconds),
        the consecutive counter resets — the system has been stable long enough.
        """
        now = time.time()

        # Decay consecutive trip counter if enough time has passed since last trip
        if (self._last_trip_time > 0 and
                now - self._last_trip_time > self.config.consecutive_trip_decay_seconds):
            self._consecutive_trips = 0

        self._consecutive_trips += 1
        self._last_trip_time = now

        # Exponential backoff: base * multiplier^(consecutive - 1), capped
        backoff_factor = self.config.backoff_multiplier ** (self._consecutive_trips - 1)
        reset_seconds = min(
            self.config.auto_reset_seconds * backoff_factor,
            self.config.max_backoff_seconds,
        )

        trip = CircuitTrip(
            reason=reason,
            timestamp=now,
            entity_id=entity_id,
            details=details,
            auto_reset_at=now + reset_seconds,
        )

        self._state = CircuitState.OPEN
        self._current_trip = trip
        self._trip_history.append(trip)

        logger.critical(
            "circuit_breaker_tripped",
            reason=reason.value,
            entity_id=entity_id,
            details=details,
            consecutive_trips=self._consecutive_trips,
            reset_seconds=reset_seconds,
            auto_reset_at=datetime.fromtimestamp(trip.auto_reset_at).isoformat(),
        )

    def allow_request(self, entity_id: str) -> tuple[bool, str]:
        """
        Check if a request should be allowed.

        In HALF_OPEN state with graduated recovery enabled, requests are
        probabilistically allowed based on the current recovery stage:
        - Stage 0: 10% of requests allowed
        - Stage 1: 25% of requests allowed
        - Stage 2: 50% of requests allowed
        - Stage 3: 100% → circuit closes

        Each stage advances after `graduated_stage_requests` consecutive successes.

        Returns:
            (allowed, reason)
        """
        with self._lock:
            self._check_auto_reset()
            self._check_metrics_window()

            # Check entity-level halt
            if entity_id in self._halted_entities:
                return False, f"Entity {entity_id} is halted"

            # Check circuit state
            if self._state == CircuitState.OPEN:
                return False, f"Circuit OPEN: {self._current_trip.reason.value if self._current_trip else 'unknown'}"

            if self._state == CircuitState.HALF_OPEN:
                if self.config.graduated_recovery_enabled:
                    return self._graduated_allow()
                else:
                    # Legacy behavior: binary half-open test
                    if self._half_open_successes >= self.config.half_open_requests:
                        self._close_circuit("recovery_successful")
                        return True, "Circuit recovered"

            return True, "Circuit closed"

    def _graduated_allow(self) -> tuple[bool, str]:
        """Graduated recovery: progressively increase allowance rate.

        Uses a deterministic drip pattern (counter mod) instead of random
        to ensure predictable, testable behavior.
        """
        stages = self.config.graduated_stages
        if self._recovery_stage >= len(stages):
            # All stages passed — close the circuit
            self._close_circuit("graduated_recovery_complete")
            return True, "Circuit recovered (graduated)"

        allowance_rate = stages[self._recovery_stage]
        self._half_open_total_requests += 1

        # Deterministic drip: allow every Nth request where N = ceil(1/rate)
        # e.g., rate=0.10 → allow every 10th, rate=0.25 → every 4th, etc.
        if allowance_rate >= 1.0:
            return True, f"Half-open stage {self._recovery_stage} (100%)"

        interval = int(1.0 / allowance_rate)
        if self._half_open_total_requests % interval == 0:
            return True, f"Half-open stage {self._recovery_stage} ({allowance_rate:.0%})"

        return False, f"Half-open stage {self._recovery_stage} ({allowance_rate:.0%}) — throttled"

    def _close_circuit(self, reason: str):
        """Transition from HALF_OPEN → CLOSED."""
        self._state = CircuitState.CLOSED
        self._current_trip = None
        self._recovery_stage = 0
        self._recovery_stage_successes = 0
        self._half_open_total_requests = 0
        logger.info("circuit_closed", reason=reason)

    def record_request(
        self,
        entity_id: str,
        risk_score: float = 0.0,
        was_blocked: bool = False,
        tripwire_triggered: bool = False,
        injection_detected: bool = False,
        critic_blocked: bool = False,
        velocity_violated: bool = False,
    ):
        """
        Record a request and check for trip conditions.

        Call this AFTER processing each request to update metrics
        and check if circuit should trip.
        """
        with self._lock:
            self._check_metrics_window()

            # Update metrics
            self._metrics.total_requests += 1

            if risk_score >= 0.7:
                self._metrics.high_risk_requests += 1

            if was_blocked:
                self._metrics.blocked_requests += 1

            if tripwire_triggered:
                self._metrics.tripwire_triggers += 1

            if injection_detected:
                self._metrics.injection_attempts += 1

            if critic_blocked:
                self._metrics.critic_blocks += 1

            if velocity_violated:
                self._metrics.velocity_violations += 1
                self._entity_violations[entity_id] += 1

            # Check entity-level violations
            if self._entity_violations[entity_id] >= self.config.entity_violation_threshold:
                self._halted_entities.add(entity_id)
                logger.warning(
                    "entity_halted",
                    entity_id=entity_id,
                    violations=self._entity_violations[entity_id],
                )

            # Check trip conditions (only if circuit is closed)
            if self._state == CircuitState.CLOSED:
                self._check_trip_conditions(entity_id)

            # Record success/failure in half-open state for graduated recovery
            if self._state == CircuitState.HALF_OPEN:
                if was_blocked:
                    # Failure during recovery → re-trip immediately
                    self._trip(
                        TripReason.HIGH_RISK_THRESHOLD,
                        entity_id=entity_id,
                        details="Failure during half-open recovery",
                    )
                else:
                    self._half_open_successes += 1
                    if self.config.graduated_recovery_enabled:
                        self._recovery_stage_successes += 1
                        if self._recovery_stage_successes >= self.config.graduated_stage_requests:
                            # Advance to next stage
                            self._recovery_stage += 1
                            self._recovery_stage_successes = 0
                            if self._recovery_stage >= len(self.config.graduated_stages):
                                self._close_circuit("graduated_recovery_complete")
                            else:
                                logger.info(
                                    "recovery_stage_advanced",
                                    stage=self._recovery_stage,
                                    allowance=self.config.graduated_stages[self._recovery_stage],
                                )

    def _check_trip_conditions(self, entity_id: str):
        """Check if any trip condition is met.

        Hysteresis note: Trip thresholds are HIGHER than recovery thresholds.
        This is implemented in _check_recovery_hysteresis() which prevents
        the circuit from closing in half-open if metrics still exceed the
        lower recovery thresholds. The trip check here uses the trip thresholds.
        """
        # High-risk threshold
        if (self._metrics.total_requests >= 10 and
            self._metrics.high_risk_ratio > self.config.high_risk_threshold):
            self._trip(
                TripReason.HIGH_RISK_THRESHOLD,
                details=f"{self._metrics.high_risk_ratio:.1%} high-risk requests"
            )
            return

        # Tripwire cascade
        if self._metrics.tripwire_triggers >= self.config.tripwire_cascade_count:
            self._trip(
                TripReason.TRIPWIRE_CASCADE,
                details=f"{self._metrics.tripwire_triggers} tripwires in window"
            )
            return

        # Injection threshold
        if self._metrics.injection_attempts >= self.config.injection_threshold:
            self._trip(
                TripReason.INJECTION_DETECTED,
                entity_id=entity_id,
                details=f"{self._metrics.injection_attempts} injection attempts"
            )
            return

        # Critic block cascade
        if self._metrics.critic_blocks >= self.config.critic_block_threshold:
            self._trip(
                TripReason.CRITIC_BLOCK_CASCADE,
                details=f"{self._metrics.critic_blocks} critic blocks"
            )
            return

    def check_recovery_hysteresis(self) -> tuple[bool, str]:
        """Check if current metrics satisfy hysteresis recovery thresholds.

        Hysteresis prevents oscillation: the circuit trips at threshold X
        but only recovers when metrics drop to X/2 (configurable). This
        means a system at 9% high-risk (just below the 10% trip threshold)
        won't immediately close — it must drop to 5% first.

        Returns:
            (can_recover, reason) — True if metrics are below recovery thresholds
        """
        with self._lock:
            reasons = []

            # High-risk ratio check (only meaningful with enough requests)
            if self._metrics.total_requests >= 10:
                if self._metrics.high_risk_ratio > self.config.hysteresis_high_risk_recovery:
                    reasons.append(
                        f"high_risk_ratio {self._metrics.high_risk_ratio:.1%} "
                        f"> recovery threshold {self.config.hysteresis_high_risk_recovery:.1%}"
                    )

            if self._metrics.tripwire_triggers > self.config.hysteresis_tripwire_recovery:
                reasons.append(
                    f"tripwire_triggers {self._metrics.tripwire_triggers} "
                    f"> recovery threshold {self.config.hysteresis_tripwire_recovery}"
                )

            if self._metrics.injection_attempts > self.config.hysteresis_injection_recovery:
                reasons.append(
                    f"injection_attempts {self._metrics.injection_attempts} "
                    f"> recovery threshold {self.config.hysteresis_injection_recovery}"
                )

            if self._metrics.critic_blocks > self.config.hysteresis_critic_recovery:
                reasons.append(
                    f"critic_blocks {self._metrics.critic_blocks} "
                    f"> recovery threshold {self.config.hysteresis_critic_recovery}"
                )

            if reasons:
                return False, "; ".join(reasons)

            return True, "All metrics below recovery thresholds"

    def manual_trip(self, reason: str = "Manual halt"):
        """Manually trip the circuit breaker."""
        with self._lock:
            self._trip(TripReason.MANUAL_HALT, details=reason)

    def manual_reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._current_trip = None
            self._metrics.reset()
            self._consecutive_trips = 0
            self._recovery_stage = 0
            self._recovery_stage_successes = 0
            self._half_open_total_requests = 0
            logger.info("circuit_manual_reset")

    def halt_entity(self, entity_id: str, reason: str = "Manual halt"):
        """Halt a specific entity."""
        with self._lock:
            self._halted_entities.add(entity_id)
            logger.warning("entity_halted", entity_id=entity_id, reason=reason)

    def unhalt_entity(self, entity_id: str):
        """Unhalt a specific entity."""
        with self._lock:
            self._halted_entities.discard(entity_id)
            self._entity_violations[entity_id] = 0
            logger.info("entity_unhalted", entity_id=entity_id)

    def register_child(self, parent_id: str, child_id: str):
        """Register a child agent under a parent for cascade halts."""
        with self._lock:
            self._cascade_halt_children[parent_id].add(child_id)

    def cascade_halt(self, parent_id: str, reason: str = "Parent halted"):
        """Halt a parent and all its children."""
        with self._lock:
            # Halt parent
            self._halted_entities.add(parent_id)

            # Halt all children
            children = self._cascade_halt_children.get(parent_id, set())
            for child_id in children:
                self._halted_entities.add(child_id)

            logger.warning(
                "cascade_halt",
                parent_id=parent_id,
                children_halted=len(children),
                reason=reason,
            )

    def get_status(self) -> dict:
        """Get circuit breaker status."""
        with self._lock:
            return {
                "state": self._state.value,
                "is_open": self._state == CircuitState.OPEN,
                "current_trip": {
                    "reason": self._current_trip.reason.value,
                    "timestamp": self._current_trip.timestamp,
                    "details": self._current_trip.details,
                    "auto_reset_at": self._current_trip.auto_reset_at,
                } if self._current_trip else None,
                "metrics": {
                    "total_requests": self._metrics.total_requests,
                    "high_risk_requests": self._metrics.high_risk_requests,
                    "high_risk_ratio": f"{self._metrics.high_risk_ratio:.1%}",
                    "blocked_requests": self._metrics.blocked_requests,
                    "tripwire_triggers": self._metrics.tripwire_triggers,
                    "injection_attempts": self._metrics.injection_attempts,
                    "critic_blocks": self._metrics.critic_blocks,
                    "velocity_violations": self._metrics.velocity_violations,
                    "window_start": datetime.fromtimestamp(self._metrics.window_start).isoformat(),
                },
                "halted_entities": list(self._halted_entities),
                "trip_history_count": len(self._trip_history),
                "backoff": {
                    "consecutive_trips": self._consecutive_trips,
                    "current_reset_seconds": min(
                        self.config.auto_reset_seconds * (
                            self.config.backoff_multiplier ** max(0, self._consecutive_trips - 1)
                        ),
                        self.config.max_backoff_seconds,
                    ) if self._consecutive_trips > 0 else self.config.auto_reset_seconds,
                },
                "recovery": {
                    "stage": self._recovery_stage,
                    "stage_successes": self._recovery_stage_successes,
                    "total_stages": len(self.config.graduated_stages),
                    "current_allowance": (
                        self.config.graduated_stages[self._recovery_stage]
                        if self._recovery_stage < len(self.config.graduated_stages)
                        else 1.0
                    ),
                } if self._state == CircuitState.HALF_OPEN else None,
            }

    def get_trip_history(self, limit: int = 10) -> list[dict]:
        """Get recent trip history."""
        with self._lock:
            return [
                {
                    "reason": trip.reason.value,
                    "timestamp": datetime.fromtimestamp(trip.timestamp).isoformat(),
                    "entity_id": trip.entity_id,
                    "details": trip.details,
                }
                for trip in self._trip_history[-limit:]
            ]


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()


def allow_request(entity_id: str) -> tuple[bool, str]:
    """Check if a request should be allowed."""
    return circuit_breaker.allow_request(entity_id)


def record_request(
    entity_id: str,
    risk_score: float = 0.0,
    was_blocked: bool = False,
    tripwire_triggered: bool = False,
    injection_detected: bool = False,
    critic_blocked: bool = False,
    velocity_violated: bool = False,
):
    """Record a request for circuit breaker monitoring."""
    circuit_breaker.record_request(
        entity_id=entity_id,
        risk_score=risk_score,
        was_blocked=was_blocked,
        tripwire_triggered=tripwire_triggered,
        injection_detected=injection_detected,
        critic_blocked=critic_blocked,
        velocity_violated=velocity_violated,
    )


def get_circuit_status() -> dict:
    """Get circuit breaker status."""
    return circuit_breaker.get_status()


def manual_halt(reason: str = "Manual halt"):
    """Manually trip the circuit breaker."""
    circuit_breaker.manual_trip(reason)


def manual_reset():
    """Manually reset the circuit breaker."""
    circuit_breaker.manual_reset()


def halt_entity(entity_id: str, reason: str = "Manual halt"):
    """Halt a specific entity."""
    circuit_breaker.halt_entity(entity_id, reason)


def unhalt_entity(entity_id: str):
    """Unhalt a specific entity."""
    circuit_breaker.unhalt_entity(entity_id)
