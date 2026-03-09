# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the CRITIC adversarial evaluation module.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.critic import (
    build_user_prompt,
    should_run_critic,
    run_critic,
    get_critic_provider,
    CRITIC_SYSTEM_PROMPT,
)
from app.models.critic import CriticRequest


@pytest.fixture
def critic_request():
    return CriticRequest(
        plan_id="plan_test",
        goal="Read a config file",
        planner_risk_score=0.2,
        tools_required=["file_read"],
        planner_reasoning="Simple read operation",
        context={"environment": "test"},
    )


@pytest.fixture
def high_risk_request():
    return CriticRequest(
        plan_id="plan_risky",
        goal="Execute shell to delete temp files",
        planner_risk_score=0.8,
        tools_required=["shell", "file_delete"],
        planner_reasoning="Cleanup operation",
        context={"environment": "production"},
    )


class TestBuildUserPrompt:
    def test_contains_goal(self, critic_request):
        prompt = build_user_prompt(critic_request)
        assert "Read a config file" in prompt

    def test_contains_risk_score(self, critic_request):
        prompt = build_user_prompt(critic_request)
        assert "0.20" in prompt

    def test_contains_tools(self, critic_request):
        prompt = build_user_prompt(critic_request)
        assert "file_read" in prompt

    def test_contains_reasoning(self, critic_request):
        prompt = build_user_prompt(critic_request)
        assert "Simple read operation" in prompt

    def test_contains_context(self, critic_request):
        prompt = build_user_prompt(critic_request)
        assert "test" in prompt.lower()

    def test_empty_context(self):
        req = CriticRequest(
            plan_id="p1",
            goal="test",
            planner_risk_score=0.1,
            tools_required=[],
            planner_reasoning="test",
            context={},
        )
        prompt = build_user_prompt(req)
        # Empty dict is falsy, should show 'none provided'
        assert "CONTEXT" in prompt


class TestShouldRunCritic:
    def test_high_risk_score_triggers(self):
        assert should_run_critic(0.5, []) is True

    def test_threshold_risk_triggers(self):
        assert should_run_critic(0.3, []) is True

    def test_low_risk_no_dangerous_tools(self):
        assert should_run_critic(0.1, ["file_read"]) is False

    def test_shell_tool_triggers(self):
        assert should_run_critic(0.1, ["shell"]) is True

    def test_file_delete_triggers(self):
        assert should_run_critic(0.1, ["file_delete"]) is True

    def test_database_triggers(self):
        assert should_run_critic(0.1, ["database"]) is True

    def test_network_triggers(self):
        assert should_run_critic(0.1, ["network"]) is True

    def test_safe_tools_no_trigger(self):
        assert should_run_critic(0.1, ["file_read", "http_get"]) is False


@pytest.mark.anyio
class TestRunCritic:
    @patch("app.core.critic.settings")
    async def test_disabled_returns_none(self, mock_settings, critic_request):
        mock_settings.critic_enabled = False
        result = await run_critic(critic_request)
        assert result is None

    @patch("app.core.critic.get_critic_provider")
    @patch("app.core.critic.settings")
    async def test_no_provider_returns_none(self, mock_settings, mock_get_provider, critic_request):
        mock_settings.critic_enabled = True
        mock_get_provider.return_value = None
        result = await run_critic(critic_request)
        assert result is None

    @patch("app.core.critic.get_critic_provider")
    @patch("app.core.critic.settings")
    async def test_successful_analysis(self, mock_settings, mock_get_provider, critic_request):
        mock_settings.critic_enabled = True
        mock_settings.critic_provider = "test"
        mock_provider = MagicMock()
        mock_provider.model_name = "test-model"
        mock_provider.analyze = AsyncMock(return_value={
            "judgment": "safe",
            "confidence": 0.9,
            "risk_adjustment": 0.0,
            "hidden_risks": [],
            "reasoning": "Looks clean",
            "concerns": [],
            "requires_human_review": False,
            "recommended_action": "proceed",
        })
        mock_get_provider.return_value = mock_provider

        result = await run_critic(critic_request)
        assert result is not None
        assert result.judgment == "safe"
        assert result.confidence == 0.9
        assert result.model_used == "test-model"

    @patch("app.core.critic.get_critic_provider")
    @patch("app.core.critic.settings")
    async def test_error_returns_suspicious(self, mock_settings, mock_get_provider, critic_request):
        mock_settings.critic_enabled = True
        mock_settings.critic_provider = "test"
        mock_provider = MagicMock()
        mock_provider.model_name = "test-model"
        mock_provider.analyze = AsyncMock(side_effect=RuntimeError("API down"))
        mock_get_provider.return_value = mock_provider

        result = await run_critic(critic_request)
        assert result is not None
        assert result.judgment == "suspicious"
        assert result.requires_human_review is True
        assert result.recommended_action == "escalate"


class TestGetCriticProvider:
    @patch("app.core.critic.settings")
    def test_no_keys_returns_none(self, mock_settings):
        mock_settings.critic_provider = "anthropic"
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings.xai_api_key = None
        result = get_critic_provider()
        assert result is None


class TestCriticSystemPrompt:
    def test_prompt_contains_judgment_scale(self):
        assert "safe" in CRITIC_SYSTEM_PROMPT
        assert "suspicious" in CRITIC_SYSTEM_PROMPT
        assert "dangerous" in CRITIC_SYSTEM_PROMPT
        assert "block" in CRITIC_SYSTEM_PROMPT

    def test_prompt_contains_output_format(self):
        assert "judgment" in CRITIC_SYSTEM_PROMPT
        assert "confidence" in CRITIC_SYSTEM_PROMPT
        assert "risk_adjustment" in CRITIC_SYSTEM_PROMPT
