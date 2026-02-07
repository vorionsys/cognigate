"""
Core security modules for Cognigate Engine.

Security Layers:
- L0-L2: velocity - Rate limiting per entity (burst/sustained/quota)
- L3: tripwires - Deterministic regex-based pattern matching
- L4: critic - AI vs AI adversarial evaluation
- L5+: circuit_breaker - System-wide safety halts

Infrastructure:
- cache - Redis caching for policy results and trust scores
- async_logger - Non-blocking async logging queue
- signatures - Ed25519 cryptographic signatures for proof records
"""

from .tripwires import check_tripwires, TripwireResult
from .critic import run_critic, should_run_critic
from .velocity import (
    check_velocity,
    record_action,
    throttle_entity,
    get_velocity_stats,
    VelocityCheckResult,
)
from .circuit_breaker import (
    allow_request as circuit_allow_request,
    record_request as circuit_record_request,
    get_circuit_status,
    manual_halt,
    manual_reset,
    halt_entity,
    unhalt_entity,
)
from .cache import cache_manager
from .async_logger import async_log_queue
from .signatures import (
    signature_manager,
    sign_proof_record,
    verify_proof_signature,
)
from .auth import (
    verify_admin_key,
    optional_admin_key,
    generate_api_key,
    AuthError,
    ForbiddenError,
)
from .policy_engine import (
    policy_engine,
    PolicyEngine,
    Policy,
    Constraint,
    EvaluationContext,
    Severity,
)

__all__ = [
    # Tripwires
    "check_tripwires",
    "TripwireResult",
    # Critic
    "run_critic",
    "should_run_critic",
    # Velocity
    "check_velocity",
    "record_action",
    "throttle_entity",
    "get_velocity_stats",
    "VelocityCheckResult",
    # Circuit Breaker
    "circuit_allow_request",
    "circuit_record_request",
    "get_circuit_status",
    "manual_halt",
    "manual_reset",
    "halt_entity",
    "unhalt_entity",
    # Infrastructure
    "cache_manager",
    "async_log_queue",
    # Signatures
    "signature_manager",
    "sign_proof_record",
    "verify_proof_signature",
    # Authentication
    "verify_admin_key",
    "optional_admin_key",
    "generate_api_key",
    "AuthError",
    "ForbiddenError",
    # Policy Engine
    "policy_engine",
    "PolicyEngine",
    "Policy",
    "Constraint",
    "EvaluationContext",
    "Severity",
]