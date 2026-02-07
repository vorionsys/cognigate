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
from typing import Optional, Callable
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

    # Recovery
    auto_reset_seconds: int = 300      # 5 minute auto-reset
    half_open_requests: int = 3        # Requests to test in half-open
    metrics_window_seconds: int = 300  # 5 minute metrics window

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

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (system halted)."""
        return self._state == CircuitState.OPEN

    def _check_auto_reset(self):
        """Check if circuit should auto-reset."""
        if self._state == CircuitState.OPEN and self._current_trip:
            if self._current_trip.auto_reset_at:
                if time.time() >= self._current_trip.auto_reset_at:
                    logger.info("circuit_auto_reset", reason="timeout_expired")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_successes = 0

    def _check_metrics_window(self):
        """Reset metrics if window expired."""
        if time.time() - self._metrics.window_start > self.config.metrics_window_seconds:
            self._metrics.reset()

    def _trip(self, reason: TripReason, entity_id: Optional[str] = None, details: str = ""):
        """Trip the circuit breaker."""
        now = time.time()
        trip = CircuitTrip(
            reason=reason,
            timestamp=now,
            entity_id=entity_id,
            details=details,
            auto_reset_at=now + self.config.auto_reset_seconds,
        )

        self._state = CircuitState.OPEN
        self._current_trip = trip
        self._trip_history.append(trip)

        logger.critical(
            "circuit_breaker_tripped",
            reason=reason.value,
            entity_id=entity_id,
            details=details,
            auto_reset_at=datetime.fromtimestamp(trip.auto_reset_at).isoformat(),
        )

    def allow_request(self, entity_id: str) -> tuple[bool, str]:
        """
        Check if a request should be allowed.

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
                # Allow limited requests for testing
                if self._half_open_successes >= self.config.half_open_requests:
                    # Enough successes, close the circuit
                    self._state = CircuitState.CLOSED
                    self._current_trip = None
                    logger.info("circuit_closed", reason="recovery_successful")
                    return True, "Circuit recovered"

            return True, "Circuit closed"

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

            # Record success in half-open state
            if self._state == CircuitState.HALF_OPEN and not was_blocked:
                self._half_open_successes += 1

    def _check_trip_conditions(self, entity_id: str):
        """Check if any trip condition is met."""
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
