# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
INTENT layer models - Goal processing and normalization.
"""

from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

from .common import generate_id, utc_now, TrustLevel, EntityId


class IntentRequest(BaseModel):
    """
    Request to normalize an intent from a user or agent.
    """

    entity_id: EntityId = Field(..., description="ID of the requesting entity")
    goal: str = Field(..., min_length=1, max_length=4096, description="The goal or prompt to process")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context for intent processing")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Request metadata")
    trust_level: Optional[TrustLevel] = Field(None, description="Override trust level (if authorized)")


class StructuredPlan(BaseModel):
    """
    A normalized, structured plan derived from an intent.
    This represents WHAT the agent wants to do, not whether it's allowed.
    """

    plan_id: str = Field(default_factory=lambda: generate_id("plan_"))
    goal: str = Field(..., description="The interpreted goal")
    tools_required: list[str] = Field(default_factory=list, description="Tools/APIs needed")
    endpoints_required: list[str] = Field(default_factory=list, description="External endpoints to access")
    data_classifications: list[str] = Field(default_factory=list, description="Data types involved")
    risk_indicators: dict[str, float] = Field(default_factory=dict, description="Risk scores by category")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall risk score (0.0-1.0)")
    reasoning_trace: str = Field(..., description="Explanation of the interpretation")


class IntentResponse(BaseModel):
    """
    Response from the INTENT endpoint.
    """

    intent_id: str = Field(default_factory=lambda: generate_id("int_"))
    entity_id: EntityId
    status: str = Field(..., description="Processing status")
    plan: Optional[StructuredPlan] = None
    trust_level: TrustLevel = Field(..., description="Entity's trust level at time of request")
    trust_score: int = Field(..., description="Entity's trust score (0-1000)")
    created_at: datetime = Field(default_factory=utc_now)
    error: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "intent_id": "int_abc123def456",
            "entity_id": "agent_001",
            "status": "normalized",
            "plan": {
                "plan_id": "plan_xyz789",
                "goal": "Send email to user@example.com",
                "tools_required": ["email_send"],
                "endpoints_required": ["smtp.example.com"],
                "data_classifications": ["pii_email"],
                "risk_indicators": {"data_exposure": 0.3},
                "risk_score": 0.3,
                "reasoning_trace": "Simple email send operation with PII handling"
            },
            "trust_level": 2,
            "trust_score": 450,
            "created_at": "2026-01-08T12:00:00Z"
        }
    })
