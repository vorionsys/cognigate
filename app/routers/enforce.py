"""
ENFORCE endpoints - Policy validation and gating.

The ENFORCE layer validates plans against BASIS policies.
It gates execution paths and mandates human approval when boundaries are tested.

Security Layers Applied:
- L0-L2: Velocity caps (rate limiting)
- L5+: Circuit breaker (system halt on threshold breach)
- Policy Engine: BASIS constraint evaluation
"""

import time
import structlog
from fastapi import APIRouter, HTTPException

from app.models.enforce import EnforceRequest, EnforceResponse, PolicyViolation, RigorMode
from app.core.velocity import check_velocity, record_action
from app.core.circuit_breaker import circuit_breaker, CircuitState
from app.core.cache import cache_manager
from app.core.async_logger import async_log_queue
from app.core.policy_engine import policy_engine, EvaluationContext

logger = structlog.get_logger()
router = APIRouter()


# Rigor mode mapping by trust level — canonical 8-tier model (T0-T7)
# T0-T2: STRICT (low trust needs maximum scrutiny)
# T3-T4: STANDARD (medium trust gets standard enforcement)
# T5-T7: LITE (high trust can skip non-critical checks)
DEFAULT_RIGOR_BY_TRUST = {
    0: RigorMode.STRICT,    # T0: Sandbox
    1: RigorMode.STRICT,    # T1: Observed
    2: RigorMode.STRICT,    # T2: Provisional
    3: RigorMode.STANDARD,  # T3: Monitored
    4: RigorMode.STANDARD,  # T4: Standard
    5: RigorMode.LITE,      # T5: Trusted
    6: RigorMode.LITE,      # T6: Certified
    7: RigorMode.LITE,      # T7: Autonomous
}


def determine_rigor_mode(trust_level: int, requested_mode: RigorMode | None) -> RigorMode:
    """
    Determine enforcement rigor mode.

    Args:
        trust_level: Entity's trust level (0-7)
        requested_mode: Explicitly requested mode (optional)

    Returns:
        RigorMode to use for enforcement
    """
    if requested_mode:
        return requested_mode

    # Auto-select based on trust level
    return DEFAULT_RIGOR_BY_TRUST.get(trust_level, RigorMode.STANDARD)


# Policy severity classification for rigor filtering
CRITICAL_POLICIES = {
    "basis-core-security",      # Security violations
    "basis-risk-thresholds",    # Risk limits
}

STANDARD_POLICIES = {
    "basis-core-security",
    "basis-data-protection",
    "basis-risk-thresholds",
}


def filter_policies_by_rigor(
    policies: list[str],
    rigor: RigorMode
) -> list[str]:
    """
    Filter policy list based on rigor mode.

    Args:
        policies: Full list of policies to check
        rigor: Rigor mode

    Returns:
        Filtered list of policies to evaluate
    """
    if rigor == RigorMode.STRICT:
        return policies

    if rigor == RigorMode.STANDARD:
        return [p for p in policies if p in STANDARD_POLICIES]

    if rigor == RigorMode.LITE:
        return [p for p in policies if p in CRITICAL_POLICIES]

    return policies


@router.post("/enforce", response_model=EnforceResponse)
async def enforce_policies(request: EnforceRequest) -> EnforceResponse:
    """
    Validate a plan against BASIS policies.

    This endpoint:
    1. CIRCUIT BREAKER - Check if system is halted
    2. VELOCITY CAPS - Check rate limits (L0-L2)
    3. Receives a structured plan from INTENT
    4. Evaluates it against applicable BASIS policies
    5. Returns a verdict (allow/deny/escalate/modify)
    6. Records metrics for circuit breaker monitoring
    7. Logs the decision for PROOF

    If violations are found:
    - Critical: Plan is DENIED
    - High: Plan requires human approval (ESCALATE)
    - Medium/Low: Plan may proceed with audit logging
    """
    start_time = time.perf_counter()

    await async_log_queue.info(
        "enforce_request",
        entity_id=request.entity_id,
        plan_id=request.plan.plan_id,
        trust_level=request.trust_level,
    )

    # ========================================================================
    # LAYER 1: CIRCUIT BREAKER CHECK (System-level halt)
    # ========================================================================
    circuit_allowed, circuit_reason = circuit_breaker.allow_request(request.entity_id)
    if not circuit_allowed:
        logger.warning(
            "enforce_circuit_blocked",
            entity_id=request.entity_id,
            reason=circuit_reason,
        )
        duration_ms = (time.perf_counter() - start_time) * 1000
        return EnforceResponse(
            intent_id=f"int_{request.plan.plan_id[5:]}",
            plan_id=request.plan.plan_id,
            allowed=False,
            action="deny",
            violations=[
                PolicyViolation(
                    policy_id="system-circuit-breaker",
                    constraint_id="system-halt",
                    severity="critical",
                    message=f"CIRCUIT BREAKER: {circuit_reason}",
                    blocked=True,
                )
            ],
            policies_evaluated=["system-circuit-breaker"],
            constraints_evaluated=1,
            trust_impact=-100,
            requires_approval=False,
            rigor_mode=RigorMode.STRICT,
            duration_ms=duration_ms,
        )

    # ========================================================================
    # LAYER 2: VELOCITY CAP CHECK (L0-L2 Rate Limiting)
    # ========================================================================
    velocity_result = await check_velocity(request.entity_id, request.trust_level)
    if not velocity_result.allowed:
        logger.warning(
            "enforce_velocity_blocked",
            entity_id=request.entity_id,
            tier=velocity_result.tier_violated.value if velocity_result.tier_violated else None,
            message=velocity_result.message,
        )

        circuit_breaker.record_request(
            entity_id=request.entity_id,
            velocity_violated=True,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        return EnforceResponse(
            intent_id=f"int_{request.plan.plan_id[5:]}",
            plan_id=request.plan.plan_id,
            allowed=False,
            action="deny",
            violations=[
                PolicyViolation(
                    policy_id="system-velocity-caps",
                    constraint_id=velocity_result.tier_violated.value if velocity_result.tier_violated else "unknown",
                    severity="high",
                    message=velocity_result.message,
                    blocked=True,
                    remediation=f"Retry after {velocity_result.retry_after_seconds:.1f} seconds" if velocity_result.retry_after_seconds else None,
                )
            ],
            policies_evaluated=["system-velocity-caps"],
            constraints_evaluated=1,
            trust_impact=-5,
            requires_approval=False,
            rigor_mode=RigorMode.STRICT,
            duration_ms=duration_ms,
        )

    # ========================================================================
    # DETERMINE RIGOR MODE (Proportional enforcement based on trust)
    # ========================================================================
    rigor_mode = determine_rigor_mode(request.trust_level, request.rigor_mode)

    await async_log_queue.info(
        "enforce_rigor_mode",
        entity_id=request.entity_id,
        trust_level=request.trust_level,
        rigor_mode=rigor_mode.value,
    )

    # ========================================================================
    # CACHE CHECK: Try to get cached policy result
    # ========================================================================
    available_policies = [p.id for p in policy_engine.list_policies()]
    policies_to_check = request.policy_ids or available_policies
    policies_to_check = filter_policies_by_rigor(policies_to_check, rigor_mode)

    cache_key_suffix = f"{request.plan.plan_id}_{rigor_mode.value}"
    cached_result = await cache_manager.get_policy_result(
        plan_id=cache_key_suffix,
        entity_id=request.entity_id,
    )

    if cached_result:
        await async_log_queue.info(
            "enforce_cache_hit",
            entity_id=request.entity_id,
            plan_id=request.plan.plan_id,
        )
        await record_action(request.entity_id)

        cached_result["duration_ms"] = (time.perf_counter() - start_time) * 1000
        cached_result["rigor_mode"] = rigor_mode
        return EnforceResponse(**cached_result)

    # ========================================================================
    # LAYER 3: POLICY EVALUATION (Cache miss - evaluate policies)
    # ========================================================================

    # Build evaluation context from plan
    context = EvaluationContext(
        trust_level=request.trust_level,
        risk_score=request.plan.risk_score,
        tools_required=request.plan.tools_required,
        data_classifications=request.plan.data_classifications,
        estimated_duration=request.plan.estimated_duration,
        metadata={
            "plan_id": request.plan.plan_id,
            "entity_id": request.entity_id,
        },
    )

    # Evaluate policies using the policy engine
    engine_violations, constraints_evaluated = policy_engine.evaluate(
        context=context,
        policy_ids=policies_to_check,
    )

    # Convert engine violations to response violations
    violations: list[PolicyViolation] = []
    requires_approval = False

    for v in engine_violations:
        violations.append(PolicyViolation(
            policy_id=v.policy_id,
            constraint_id=v.constraint_id,
            severity=v.severity.value,
            message=v.message,
            blocked=v.blocked,
            remediation=v.remediation,
        ))
        if v.requires_approval:
            requires_approval = True

    policies_evaluated = list(set(v.policy_id for v in engine_violations)) or policies_to_check

    # Determine verdict
    critical_violations = [v for v in violations if v.severity == "critical"]
    high_violations = [v for v in violations if v.severity == "high"]

    if critical_violations:
        action = "deny"
        allowed = False
    elif high_violations or requires_approval:
        action = "escalate"
        allowed = False
    elif violations:
        action = "allow"
        allowed = True
    else:
        action = "allow"
        allowed = True

    # Calculate trust impact
    trust_impact = 0
    if critical_violations:
        trust_impact = -50
    elif high_violations:
        trust_impact = -10

    duration_ms = (time.perf_counter() - start_time) * 1000

    # ========================================================================
    # LAYER 4: RECORD METRICS & VELOCITY
    # ========================================================================
    await record_action(request.entity_id)

    circuit_breaker.record_request(
        entity_id=request.entity_id,
        risk_score=request.plan.risk_score,
        was_blocked=not allowed,
    )

    await async_log_queue.info(
        "enforce_verdict",
        entity_id=request.entity_id,
        plan_id=request.plan.plan_id,
        action=action,
        allowed=allowed,
        violations_count=len(violations),
        duration_ms=duration_ms,
    )

    response = EnforceResponse(
        intent_id=f"int_{request.plan.plan_id[5:]}",
        plan_id=request.plan.plan_id,
        allowed=allowed,
        action=action,
        violations=violations,
        policies_evaluated=policies_evaluated,
        constraints_evaluated=constraints_evaluated,
        trust_impact=trust_impact,
        requires_approval=requires_approval,
        approval_timeout="4h" if requires_approval else None,
        rigor_mode=rigor_mode,
        duration_ms=duration_ms,
    )

    await cache_manager.set_policy_result(
        plan_id=cache_key_suffix,
        result=response.model_dump(mode='json', exclude={'verdict_id', 'duration_ms', 'decided_at'}),
        entity_id=request.entity_id,
    )

    return response


@router.get("/enforce/policies")
async def list_policies() -> dict:
    """
    List available BASIS policies.
    """
    policies = policy_engine.list_policies()
    return {
        "policies": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "constraints": len(p.constraints),
                "enabled": p.enabled,
            }
            for p in policies
        ]
    }


@router.get("/enforce/policies/{policy_id}")
async def get_policy(policy_id: str) -> dict:
    """
    Get details of a specific policy.
    """
    policy = policy_engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "enabled": policy.enabled,
        "constraints": [
            {
                "id": c.id,
                "type": c.type,
                "condition": c.condition,
                "severity": c.severity.value,
                "message": c.message,
                "requires_approval": c.requires_approval,
            }
            for c in policy.constraints
        ],
    }
