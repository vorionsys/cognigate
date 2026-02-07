"""
CRITIC - Adversarial AI Evaluation (Planner + Critic Pattern)

Level 2 security layer. After the Planner (intent analysis) produces a plan,
the Critic reviews it with an adversarial mindset, looking for:
1. Hidden risks the Planner missed
2. Euphemisms or obfuscation
3. Unsafe tool combinations
4. Escalation triggers

Supports multiple AI providers:
- Anthropic (Claude) - Default, excellent at adversarial analysis
- OpenAI (GPT)
- Google (Gemini)
- xAI (Grok)
"""

import time
import json
import structlog
from typing import Optional, Any
from abc import ABC, abstractmethod

from app.config import get_settings
from app.models.critic import CriticVerdict, CriticRequest

logger = structlog.get_logger()
settings = get_settings()


# The Critic's system prompt - adversarial by design
CRITIC_SYSTEM_PROMPT = """You are THE CRITIC - an adversarial security reviewer for AI agent actions.

Your job is to find problems, risks, and hidden dangers that the Planner may have missed.
You are NOT here to agree or rubber-stamp plans. You are here to PROTECT the system.

RULES:
1. ASSUME BAD INTENT until proven otherwise
2. Look for euphemisms: "organize" might mean "delete", "optimize" might mean "destroy"
3. Look for scope creep: small requests that could escalate
4. Look for dangerous tool combinations (shell + network = exfiltration risk)
5. Consider: "What's the WORST interpretation of this request?"

JUDGMENT SCALE:
- "safe": No significant risks detected. Proceed normally.
- "suspicious": Something feels off. Recommend additional scrutiny.
- "dangerous": Clear risks present. Recommend escalation to human review.
- "block": Obvious malicious intent or critical system risk. BLOCK immediately.

OUTPUT FORMAT (JSON only, no other text):
{
    "judgment": "safe|suspicious|dangerous|block",
    "confidence": 0.0-1.0,
    "risk_adjustment": -0.5 to +0.5,
    "hidden_risks": ["risk1", "risk2"],
    "reasoning": "Your detailed reasoning",
    "concerns": ["concern1", "concern2"],
    "requires_human_review": true/false,
    "recommended_action": "proceed|escalate|block|modify"
}

Remember: Your paranoia protects the system. Trust nothing."""


def build_user_prompt(request: CriticRequest) -> str:
    """Build the user prompt for the Critic."""
    return f"""ANALYZE THIS PLAN:

ORIGINAL GOAL: {request.goal}

PLANNER'S ASSESSMENT:
- Risk Score: {request.planner_risk_score:.2f}
- Tools Required: {', '.join(request.tools_required) or 'none'}
- Reasoning: {request.planner_reasoning}

CONTEXT: {request.context or 'none provided'}

Your task: Find what the Planner MISSED. What are the hidden risks? Is this request hiding malicious intent behind innocent language?

Respond with JSON only, no markdown formatting."""


class CriticProvider(ABC):
    """Abstract base class for Critic AI providers."""

    @abstractmethod
    async def analyze(self, request: CriticRequest) -> dict:
        """Run the critic analysis and return parsed JSON response."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        pass


class AnthropicCritic(CriticProvider):
    """Claude-based Critic implementation."""

    def __init__(self):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.critic_model_anthropic

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze(self, request: CriticRequest) -> dict:
        response = await self.client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=CRITIC_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(request)}
            ],
        )
        content = response.content[0].text
        # Claude sometimes wraps in markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())


class OpenAICritic(CriticProvider):
    """OpenAI GPT-based Critic implementation."""

    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.critic_model_openai

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze(self, request: CriticRequest) -> dict:
        response = await self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(request)},
            ],
            temperature=settings.critic_temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)


class GoogleCritic(CriticProvider):
    """Google Gemini-based Critic implementation."""

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        self._model = settings.critic_model_google
        self.model = genai.GenerativeModel(
            self._model,
            system_instruction=CRITIC_SYSTEM_PROMPT,
        )

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze(self, request: CriticRequest) -> dict:
        # Gemini doesn't have native async, wrap in executor
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.model.generate_content(
                build_user_prompt(request),
                generation_config={"temperature": settings.critic_temperature},
            )
        )
        content = response.text
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())


class XAICritic(CriticProvider):
    """xAI Grok-based Critic implementation (OpenAI-compatible API)."""

    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=settings.xai_api_key,
            base_url="https://api.x.ai/v1",
        )
        self._model = settings.critic_model_xai

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze(self, request: CriticRequest) -> dict:
        response = await self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(request)},
            ],
            temperature=settings.critic_temperature,
        )
        content = response.choices[0].message.content
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())


def get_critic_provider() -> Optional[CriticProvider]:
    """Get the configured Critic provider, or None if not configured."""
    provider = settings.critic_provider.lower()

    if provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicCritic()
    elif provider == "openai" and settings.openai_api_key:
        return OpenAICritic()
    elif provider == "google" and settings.google_api_key:
        return GoogleCritic()
    elif provider == "xai" and settings.xai_api_key:
        return XAICritic()

    # Fallback: try any available provider
    if settings.anthropic_api_key:
        return AnthropicCritic()
    if settings.openai_api_key:
        return OpenAICritic()
    if settings.google_api_key:
        return GoogleCritic()
    if settings.xai_api_key:
        return XAICritic()

    return None


async def run_critic(request: CriticRequest) -> Optional[CriticVerdict]:
    """
    Run the Critic on a plan.

    Args:
        request: The plan and context to critique

    Returns:
        CriticVerdict if analysis completed, None if Critic is disabled
    """
    if not settings.critic_enabled:
        logger.debug("critic_skipped", reason="disabled")
        return None

    provider = get_critic_provider()
    if provider is None:
        logger.debug("critic_skipped", reason="no_api_key")
        return None

    start_time = time.perf_counter()

    try:
        data = await provider.analyze(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        verdict = CriticVerdict(
            plan_id=request.plan_id,
            judgment=data.get("judgment", "safe"),
            confidence=data.get("confidence", 0.5),
            risk_adjustment=data.get("risk_adjustment", 0.0),
            hidden_risks=data.get("hidden_risks", []),
            reasoning=data.get("reasoning", ""),
            concerns=data.get("concerns", []),
            requires_human_review=data.get("requires_human_review", False),
            recommended_action=data.get("recommended_action", "proceed"),
            model_used=provider.model_name,
            duration_ms=duration_ms,
        )

        logger.info(
            "critic_completed",
            plan_id=request.plan_id,
            provider=settings.critic_provider,
            model=provider.model_name,
            judgment=verdict.judgment,
            confidence=verdict.confidence,
            risk_adjustment=verdict.risk_adjustment,
            duration_ms=duration_ms,
        )

        return verdict

    except Exception as e:
        logger.error(
            "critic_error",
            plan_id=request.plan_id,
            provider=settings.critic_provider,
            error=str(e),
        )
        # On error, return a cautious verdict
        return CriticVerdict(
            plan_id=request.plan_id,
            judgment="suspicious",
            confidence=0.3,
            risk_adjustment=0.1,
            hidden_risks=["Critic analysis failed - proceeding with caution"],
            reasoning=f"Critic analysis error: {str(e)}. Defaulting to suspicious.",
            concerns=["Unable to complete adversarial analysis"],
            requires_human_review=True,
            recommended_action="escalate",
            model_used=f"{settings.critic_provider} (failed)",
        )


def should_run_critic(risk_score: float, tools_required: list[str]) -> bool:
    """
    Determine if the Critic should be invoked based on risk profile.

    The Critic adds latency (~1-2s) so we only run it when needed:
    - Risk score above threshold
    - Dangerous tools involved
    """
    # Always run for moderate+ risk
    if risk_score >= 0.3:
        return True

    # Always run for dangerous tools
    dangerous_tools = {"shell", "file_delete", "database", "network"}
    if any(tool in dangerous_tools for tool in tools_required):
        return True

    return False
