"""
ENFORCE layer models - Policy validation and gating.
"""

from typing import Optional, Literal, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

from .common import generate_id, utc_now, TrustLevel
from .intent import StructuredPlan


class RigorMode(str, Enum):
    """
    Proportional enforcement rigor levels.

    - LITE: Check only critical policies (~50% faster)
      - Best for: High-trust agents (L4-L5), low-risk operations
      - Policies: Security violations, hard constraints only

    - STANDARD: Check all policies (current behavior)
      - Best for: Medium-trust agents (L2-L3)
      - Policies: All BASIS policies

    - STRICT: All policies + AI critic validation (slower, thorough)
      - Best for: Low-trust agents (L0-L1), high-risk operations
      - Policies: All BASIS + AI review + enhanced auditing
    """
    LITE = "lite"
    STANDARD = "standard"
    STRICT = "strict"


class PolicyViolation(BaseModel):
    """
    A specific policy violation detected during enforcement.
    """

    policy_id: str = Field(..., description="ID of the violated policy")
    constraint_id: Optional[str] = Field(None, description="Specific constraint that was violated")
    severity: Literal["critical", "high", "medium", "low"] = Field(..., description="Violation severity")
    message: str = Field(..., description="Human-readable violation description")
    blocked: bool = Field(..., description="Whether this violation blocks execution")
    remediation: Optional[str] = Field(None, description="Suggested remediation")


class EnforceRequest(BaseModel):
    """
    Request to enforce BASIS policies against a structured plan.
    """

    plan: StructuredPlan = Field(..., description="The plan to validate")
    policy_ids: list[str] = Field(default_factory=list, description="Specific policies to check (empty = all applicable)")
    entity_id: str = Field(..., description="ID of the requesting entity")
    trust_level: TrustLevel = Field(..., description="Entity's current trust level")
    trust_score: int = Field(..., ge=0, le=1000, description="Entity's current trust score")
    rigor_mode: Optional[RigorMode] = Field(None, description="Enforcement rigor (auto-selected from trust level if not provided)")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context for enforcement")


class EnforceResponse(BaseModel):
    """
    Response from the ENFORCE endpoint - the verdict.
    """

    verdict_id: str = Field(default_factory=lambda: generate_id("vrd_"))
    intent_id: str = Field(..., description="ID of the intent being enforced")
    plan_id: str = Field(..., description="ID of the plan being enforced")

    # The verdict
    allowed: bool = Field(..., description="Whether execution is permitted")
    action: Literal["allow", "deny", "escalate", "modify"] = Field(..., description="Enforcement action")

    # Details
    violations: list[PolicyViolation] = Field(default_factory=list, description="Policy violations found")
    policies_evaluated: list[str] = Field(default_factory=list, description="Policies that were checked")
    constraints_evaluated: int = Field(..., description="Number of constraints evaluated")

    # Trust impact
    trust_impact: int = Field(0, description="Impact on entity's trust score")
    requires_approval: bool = Field(False, description="Whether human approval is required")
    approval_timeout: Optional[str] = Field(None, description="Timeout for approval (e.g., '4h')")

    # Modifications (if action == 'modify')
    modifications: Optional[dict[str, Any]] = Field(None, description="Required modifications to the plan")

    # Metadata
    rigor_mode: RigorMode = Field(..., description="Enforcement rigor level used")
    decided_at: datetime = Field(default_factory=utc_now)
    duration_ms: float = Field(..., description="Processing time in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "verdict_id": "vrd_abc123",
                "intent_id": "int_xyz789",
                "plan_id": "plan_def456",
                "allowed": False,
                "action": "escalate",
                "violations": [
                    {
                        "policy_id": "corp-finance-limited",
                        "constraint_id": "high-value-approval",
                        "severity": "high",
                        "message": "Transaction exceeds $10,000 threshold",
                        "blocked": False,
                        "remediation": "Request manager approval"
                    }
                ],
                "policies_evaluated": ["corp-finance-limited"],
                "constraints_evaluated": 12,
                "trust_impact": 0,
                "requires_approval": True,
                "approval_timeout": "4h",
                "decided_at": "2026-01-08T12:00:00Z",
                "duration_ms": 45.2
            }
        }
