"""
INTENT endpoints - Goal processing and normalization.

The INTENT layer interprets and normalizes goals into structured plans.
It surfaces risk and constraint pressure WITHOUT executing actions.

Security Layers:
1. TRIPWIRES - Deterministic regex patterns for obviously dangerous commands
2. PARANOIA MODE - Euphemism detection and system path analysis
3. CRITIC (optional) - Adversarial AI evaluation
"""

import time
import structlog
from fastapi import APIRouter, HTTPException

from app.models.intent import IntentRequest, IntentResponse, StructuredPlan
from app.models.common import TrustLevel
from app.models.critic import CriticRequest
from app.core.tripwires import check_tripwires
from app.core.critic import run_critic, should_run_critic

logger = structlog.get_logger()
router = APIRouter()


# Mock trust database (replace with real service)
MOCK_TRUST_SCORES: dict[str, tuple[int, TrustLevel]] = {
    "agent_001": (450, 2),
    "agent_002": (250, 1),
    "agent_003": (750, 3),
}

# Risk keywords for mock analysis - PARANOIA MODE
# Euphemisms that mean "delete" in disguise
EUPHEMISM_KEYWORDS = [
    "clear", "clean", "wipe", "purge", "organize", "tidy", "archive",
    "free up", "reclaim", "empty", "reset", "format", "nuke", "sanitize"
]
# Explicit destructive keywords
HIGH_RISK_KEYWORDS = [
    "delete", "drop", "hack", "exploit", "bypass", "admin", "root", "sudo",
    "rm -rf", "rmdir", "truncate", "destroy", "erase", "shred", "kill"
]
# System-critical paths - if mentioned with any action, escalate
SYSTEM_PATHS = [
    "root", "/root", "/etc", "/var", "/usr", "/bin", "/sys", "/boot",
    "system32", "windows", "c:\\", "home directory", "all files",
    "everything", "entire", "whole system"
]
MEDIUM_RISK_KEYWORDS = ["modify", "update", "change", "write", "send", "transfer"]
TOOL_KEYWORDS = {
    "shell": ["shell", "bash", "cmd", "exec", "run", "terminal", "command"],
    "file_write": ["write", "save", "create file", "modify file"],
    "file_delete": ["delete", "remove", "rm", "unlink", "clear", "wipe", "clean", "purge"],
    "network": ["http", "api", "fetch", "request", "curl"],
    "database": ["sql", "query", "select", "insert", "update", "delete from"],
    "email": ["email", "mail", "send message", "notify"],
}


def analyze_intent(goal: str, context: dict) -> StructuredPlan:
    """
    Mock intent analysis - PARANOIA MODE enabled.
    In production, this would use an LLM with hardened system prompts.
    """
    goal_lower = goal.lower()

    # Detect tools required
    tools_required = []
    for tool, keywords in TOOL_KEYWORDS.items():
        if any(kw in goal_lower for kw in keywords):
            tools_required.append(tool)

    # Calculate risk score
    risk_indicators = {}
    risk_score = 0.1  # Base risk

    # PARANOIA CHECK 1: Euphemism + System Path = CRITICAL
    has_euphemism = any(kw in goal_lower for kw in EUPHEMISM_KEYWORDS)
    has_system_path = any(path in goal_lower for path in SYSTEM_PATHS)

    if has_euphemism and has_system_path:
        risk_indicators["euphemism_attack"] = 0.95
        risk_indicators["system_path_target"] = 0.9
        risk_score = 0.95
        tools_required.append("file_delete")
        tools_required.append("shell")

    # PARANOIA CHECK 2: Euphemisms alone are suspicious
    euphemism_count = sum(1 for kw in EUPHEMISM_KEYWORDS if kw in goal_lower)
    if euphemism_count > 0 and not has_system_path:
        risk_indicators["suspicious_euphemism"] = min(0.5 + (0.1 * euphemism_count), 0.7)
        risk_score = max(risk_score, risk_indicators["suspicious_euphemism"])

    # High risk indicators (explicit destructive keywords)
    high_risk_count = sum(1 for kw in HIGH_RISK_KEYWORDS if kw in goal_lower)
    if high_risk_count > 0:
        risk_indicators["destructive_intent"] = min(0.3 * high_risk_count, 0.9)
        risk_score = max(risk_score, risk_indicators["destructive_intent"])

    # System path without euphemism still dangerous
    if has_system_path and not has_euphemism:
        risk_indicators["system_path_access"] = 0.7
        risk_score = max(risk_score, 0.7)

    # Medium risk indicators
    medium_risk_count = sum(1 for kw in MEDIUM_RISK_KEYWORDS if kw in goal_lower)
    if medium_risk_count > 0:
        risk_indicators["modification_intent"] = min(0.15 * medium_risk_count, 0.5)
        risk_score = max(risk_score, risk_indicators["modification_intent"])

    # Tool-based risk
    if "shell" in tools_required or "file_delete" in tools_required:
        risk_indicators["dangerous_tools"] = 0.7
        risk_score = max(risk_score, 0.7)

    # Data classification (mock)
    data_classifications = []
    if "email" in goal_lower or "@" in goal:
        data_classifications.append("pii_email")
    if "password" in goal_lower or "credential" in goal_lower:
        data_classifications.append("credentials")
    if "ssn" in goal_lower or "social security" in goal_lower:
        data_classifications.append("pii_ssn")

    # Endpoints (mock - extract URLs or domains)
    endpoints_required = []
    if "api" in goal_lower:
        endpoints_required.append("external_api")

    return StructuredPlan(
        goal=goal,
        tools_required=tools_required or ["none"],
        endpoints_required=endpoints_required,
        data_classifications=data_classifications,
        risk_indicators=risk_indicators,
        risk_score=min(risk_score, 1.0),
        reasoning_trace=f"Analyzed intent with {len(tools_required)} tools detected, "
        f"{len(data_classifications)} data types identified, "
        f"risk score: {risk_score:.2f}",
    )


@router.post("/intent", response_model=IntentResponse)
async def normalize_intent(request: IntentRequest) -> IntentResponse:
    """
    Normalize an intent into a structured plan.

    This endpoint:
    1. TRIPWIRES - Check for obviously dangerous patterns (deterministic)
    2. Receives a raw goal/prompt from an entity
    3. Analyzes and normalizes it into a structured plan
    4. Identifies tools, endpoints, and data types involved
    5. Calculates risk indicators

    The plan is NOT executed - it's passed to ENFORCE for policy validation.
    """
    start_time = time.perf_counter()

    logger.info(
        "intent_received",
        entity_id=request.entity_id,
        goal_length=len(request.goal),
    )

    # ========================================================================
    # LEVEL 1: TRIPWIRE CHECK (Deterministic, runs BEFORE any LLM analysis)
    # ========================================================================
    tripwire_result = check_tripwires(request.goal)
    if tripwire_result.triggered:
        logger.warning(
            "tripwire_triggered",
            entity_id=request.entity_id,
            pattern=tripwire_result.pattern_name,
            severity=tripwire_result.severity,
            matched=tripwire_result.matched_text,
        )

        # Return immediately with a blocked plan - no further processing
        return IntentResponse(
            entity_id=request.entity_id,
            status="blocked",
            plan=StructuredPlan(
                goal=request.goal,
                tools_required=["BLOCKED"],
                endpoints_required=[],
                data_classifications=[],
                risk_indicators={
                    "tripwire_triggered": 1.0,
                    tripwire_result.pattern_name or "unknown": 1.0,
                },
                risk_score=1.0,
                reasoning_trace=f"TRIPWIRE TRIGGERED: {tripwire_result.message}. "
                f"Pattern: {tripwire_result.pattern_name}. "
                f"This request has been automatically blocked.",
            ),
            trust_level=0,  # Force untrusted
            trust_score=0,
            error=f"TRIPWIRE: {tripwire_result.message}",
        )

    # ========================================================================
    # LEVEL 2: STANDARD PROCESSING
    # ========================================================================

    # Get entity trust (mock)
    trust_score, trust_level = MOCK_TRUST_SCORES.get(
        request.entity_id, (200, 1)  # Default to Provisional
    )

    # Override trust if authorized and provided
    if request.trust_level is not None:
        # In production, verify authorization to override
        trust_level = request.trust_level

    try:
        # Analyze the intent (includes PARANOIA MODE checks)
        plan = analyze_intent(request.goal, request.context)

        # ====================================================================
        # LEVEL 3: CRITIC ANALYSIS (AI vs AI - runs for risky plans)
        # ====================================================================
        critic_verdict = None
        if should_run_critic(plan.risk_score, plan.tools_required):
            critic_request = CriticRequest(
                plan_id=plan.plan_id,
                goal=request.goal,
                planner_risk_score=plan.risk_score,
                planner_reasoning=plan.reasoning_trace,
                tools_required=plan.tools_required,
                context=request.context,
            )
            critic_verdict = await run_critic(critic_request)

            if critic_verdict:
                # Apply risk adjustment from Critic
                adjusted_risk = min(1.0, max(0.0,
                    plan.risk_score + critic_verdict.risk_adjustment
                ))

                # Update plan with Critic's findings
                if critic_verdict.hidden_risks:
                    for risk in critic_verdict.hidden_risks:
                        plan.risk_indicators[f"critic_{risk[:20]}"] = critic_verdict.confidence

                # Update reasoning trace
                plan.reasoning_trace += f" | CRITIC [{critic_verdict.judgment}]: {critic_verdict.reasoning[:100]}"

                # Apply risk adjustment
                original_risk = plan.risk_score
                plan.risk_score = adjusted_risk

                logger.info(
                    "critic_applied",
                    plan_id=plan.plan_id,
                    judgment=critic_verdict.judgment,
                    original_risk=original_risk,
                    adjusted_risk=adjusted_risk,
                    hidden_risks=len(critic_verdict.hidden_risks),
                )

                # If Critic says block, override the status
                if critic_verdict.judgment == "block":
                    return IntentResponse(
                        entity_id=request.entity_id,
                        status="blocked",
                        plan=plan,
                        trust_level=0,
                        trust_score=0,
                        error=f"CRITIC BLOCK: {critic_verdict.reasoning[:200]}",
                    )

        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "intent_normalized",
            entity_id=request.entity_id,
            plan_id=plan.plan_id,
            risk_score=plan.risk_score,
            tools=plan.tools_required,
            critic_ran=critic_verdict is not None,
            duration_ms=duration_ms,
        )

        return IntentResponse(
            entity_id=request.entity_id,
            status="normalized",
            plan=plan,
            trust_level=trust_level,
            trust_score=trust_score,
        )

    except Exception as e:
        logger.error(
            "intent_error",
            entity_id=request.entity_id,
            error=str(e),
        )
        return IntentResponse(
            entity_id=request.entity_id,
            status="error",
            trust_level=trust_level,
            trust_score=trust_score,
            error=str(e),
        )


@router.get("/intent/{intent_id}")
async def get_intent(intent_id: str) -> dict:
    """
    Retrieve a previously processed intent by ID.

    In production, this would fetch from a database.
    """
    # Mock - would fetch from database
    raise HTTPException(status_code=404, detail=f"Intent {intent_id} not found")
