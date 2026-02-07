"""
CRITIC layer models - Adversarial AI evaluation.

The Critic Pattern: An AI agent analyzes the output of the Planner (intent analysis)
looking specifically for risks, misclassifications, and hidden dangers.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

from .common import generate_id, utc_now


class CriticVerdict(BaseModel):
    """
    The Critic's assessment of a plan.

    The Critic is adversarial - its job is to find problems, not to agree.
    A plan passes Critic review only if the Critic cannot find sufficient
    reason to escalate or block.
    """

    critic_id: str = Field(default_factory=lambda: generate_id("crit_"))
    plan_id: str = Field(..., description="ID of the plan being critiqued")

    # Critic's verdict
    judgment: Literal["safe", "suspicious", "dangerous", "block"] = Field(
        ...,
        description="Critic's overall judgment"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Critic's confidence in its judgment (0.0-1.0)"
    )

    # Risk assessment
    risk_adjustment: float = Field(
        default=0.0,
        ge=-0.5,
        le=0.5,
        description="Suggested adjustment to risk score (-0.5 to +0.5)"
    )
    hidden_risks: list[str] = Field(
        default_factory=list,
        description="Risks the Planner may have missed"
    )

    # Reasoning
    reasoning: str = Field(
        ...,
        description="Critic's detailed reasoning for its judgment"
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Specific concerns about the plan"
    )

    # Recommendations
    requires_human_review: bool = Field(
        default=False,
        description="Whether human review is recommended"
    )
    recommended_action: Literal["proceed", "escalate", "block", "modify"] = Field(
        default="proceed",
        description="Recommended enforcement action"
    )

    # Metadata
    model_used: str = Field(
        default="gpt-4o-mini",
        description="Model used for critic analysis"
    )
    created_at: datetime = Field(default_factory=utc_now)
    duration_ms: Optional[float] = Field(
        None,
        description="Time taken for critic analysis"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "critic_id": "crit_abc123",
                "plan_id": "plan_xyz789",
                "judgment": "suspicious",
                "confidence": 0.85,
                "risk_adjustment": 0.2,
                "hidden_risks": [
                    "Euphemism 'organize' may indicate deletion intent",
                    "Target path includes system directories"
                ],
                "reasoning": "While the request appears benign on the surface, "
                            "the combination of 'organize' and 'root directory' "
                            "suggests potential destructive intent.",
                "concerns": [
                    "Vague action verb 'organize' has multiple interpretations",
                    "Root directory access is rarely needed for legitimate tasks"
                ],
                "requires_human_review": True,
                "recommended_action": "escalate",
                "model_used": "gpt-4o-mini",
                "created_at": "2026-01-08T12:00:00Z",
                "duration_ms": 1250.5
            }
        }


class CriticRequest(BaseModel):
    """
    Request to run the Critic on a plan.
    """

    plan_id: str = Field(..., description="ID of the plan to critique")
    goal: str = Field(..., description="Original goal from the intent")
    planner_risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Risk score from the Planner"
    )
    planner_reasoning: str = Field(
        ...,
        description="Planner's reasoning trace"
    )
    tools_required: list[str] = Field(
        default_factory=list,
        description="Tools identified by the Planner"
    )
    context: dict = Field(
        default_factory=dict,
        description="Additional context for the Critic"
    )


class CriticConfig(BaseModel):
    """
    Configuration for the Critic's behavior.
    """

    # Sensitivity thresholds
    suspicion_threshold: float = Field(
        default=0.3,
        description="Risk score above which Critic should be extra suspicious"
    )
    escalation_threshold: float = Field(
        default=0.6,
        description="Risk score above which Critic should recommend escalation"
    )
    block_threshold: float = Field(
        default=0.9,
        description="Risk score above which Critic should recommend blocking"
    )

    # Behavioral settings
    adversarial_strength: Literal["low", "medium", "high", "paranoid"] = Field(
        default="high",
        description="How aggressively the Critic looks for problems"
    )
    require_critic_for_high_risk: bool = Field(
        default=True,
        description="Always run Critic for high-risk plans"
    )

    # Model settings
    model: str = Field(
        default="gpt-4o-mini",
        description="Model to use for Critic analysis"
    )
    temperature: float = Field(
        default=0.3,
        description="Temperature for Critic (lower = more consistent)"
    )
