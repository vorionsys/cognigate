# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the ENFORCE endpoint — policy bypass attempts, rigor mode
consistency, cross-layer invariants.

Every test answers: "What catastrophic bug does this catch?"
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# POLICY ENFORCEMENT — deny when it MUST deny
# =============================================================================


@pytest.mark.anyio
class TestPolicyEnforcement:
    """Catches: policy engine silently allowing dangerous plans."""

    async def test_low_trust_denied_shell_access(self, async_client: AsyncClient):
        """Catastrophe: T1 agent gets shell access → arbitrary code execution."""
        plan = {
            "plan_id": "plan_shell_lowT",
            "goal": "Execute shell command",
            "tools_required": ["shell"],
            "data_classifications": [],
            "risk_score": 0.3,
            "reasoning_trace": "Shell command at low trust",
        }
        request = {"entity_id": "agent_test", "trust_level": 1, "trust_score": 200, "plan": plan}
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["allowed"] is False

    async def test_high_trust_allowed_shell_access(self, async_client: AsyncClient):
        """Catastrophe: T4 agent can't use shell → functionality broken."""
        plan = {
            "plan_id": "plan_shell_highT",
            "goal": "Execute shell command",
            "tools_required": ["shell"],
            "data_classifications": [],
            "risk_score": 0.3,
            "reasoning_trace": "Shell command at high trust",
        }
        request = {"entity_id": "agent_test", "trust_level": 4, "trust_score": 650, "plan": plan}
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["allowed"] is True

    async def test_high_risk_low_trust_always_denied(self, async_client: AsyncClient, high_risk_plan):
        """Catastrophe: high-risk plan sneaks through low-trust enforcement."""
        request = {
            "entity_id": "agent_test",
            "trust_level": 1,
            "trust_score": 200,
            "plan": high_risk_plan,
        }
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["allowed"] is False
        assert data["action"] in ["deny", "escalate"]
        assert len(data["violations"]) > 0

    async def test_safe_plan_high_trust_allowed(self, async_client: AsyncClient, sample_plan):
        """Catastrophe: safe plan incorrectly denied → system unusable."""
        request = {
            "entity_id": "agent_test",
            "trust_level": 3,
            "trust_score": 500,
            "plan": sample_plan,
        }
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["allowed"] is True
        assert data["action"] == "allow"
        assert len(data["violations"]) == 0


# =============================================================================
# POLICY BYPASS ATTEMPTS — empty/null/extreme inputs
# =============================================================================


@pytest.mark.anyio
class TestPolicyBypassAttempts:
    """Catches: enforcement bypass via malformed or edge-case inputs."""

    async def test_empty_tools_list_still_evaluated(self, async_client: AsyncClient):
        """Catastrophe: empty tools bypass tool-based policies."""
        plan = {
            "plan_id": "plan_empty_tools",
            "goal": "Do something",
            "tools_required": [],
            "data_classifications": [],
            "risk_score": 0.5,
            "reasoning_trace": "Plan with no tools declared",
        }
        request = {"entity_id": "agent_test", "trust_level": 1, "trust_score": 200, "plan": plan}
        response = await async_client.post("/v1/enforce", json=request)
        assert response.status_code == 200
        data = response.json()
        assert "action" in data
        assert "policies_evaluated" in data

    async def test_zero_risk_score_still_enforced(self, async_client: AsyncClient):
        """Catastrophe: risk_score=0 bypasses all checks."""
        plan = {
            "plan_id": "plan_zero_risk",
            "goal": "Zero risk plan",
            "tools_required": ["shell"],
            "data_classifications": [],
            "risk_score": 0.0,
            "reasoning_trace": "Claimed zero risk but wants shell",
        }
        request = {"entity_id": "agent_test", "trust_level": 1, "trust_score": 200, "plan": plan}
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        # Shell access for T1 should still be denied regardless of risk_score
        assert data["allowed"] is False

    async def test_max_risk_score_denied(self, async_client: AsyncClient):
        """Catastrophe: risk_score=1.0 somehow allowed."""
        plan = {
            "plan_id": "plan_max_risk",
            "goal": "Maximum risk operation",
            "tools_required": ["shell", "file_delete"],
            "data_classifications": ["credentials"],
            "risk_score": 1.0,
            "reasoning_trace": "Everything about this is dangerous",
        }
        request = {"entity_id": "agent_test", "trust_level": 1, "trust_score": 200, "plan": plan}
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["allowed"] is False


# =============================================================================
# RIGOR MODE — strict vs. lite consistency
# =============================================================================


@pytest.mark.anyio
class TestRigorMode:
    """Catches: rigor mode downgrade attack, inconsistent policy evaluation."""

    async def test_strict_mode_evaluates_all_policies(self, async_client: AsyncClient, sample_plan):
        """Catastrophe: STRICT mode skips policies → security gaps."""
        # T1 (Observed) → server selects STRICT automatically
        request = {
            "entity_id": "agent_test",
            "trust_level": 1,
            "trust_score": 200,
            "plan": sample_plan,
        }
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["rigor_mode"] == "strict"
        assert "policies_evaluated" in data
        assert len(data["policies_evaluated"]) > 0

    async def test_lite_mode_returns_correct_label(self, async_client: AsyncClient, sample_plan):
        # T5 (Trusted) → server selects LITE automatically
        request = {
            "entity_id": "agent_test",
            "trust_level": 5,
            "trust_score": 650,
            "plan": sample_plan,
        }
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["rigor_mode"] == "lite"

    async def test_denial_has_negative_trust_impact(self, async_client: AsyncClient, high_risk_plan):
        """Catastrophe: violations don't penalize trust → no disincentive."""
        request = {
            "entity_id": "agent_test",
            "trust_level": 1,
            "trust_score": 200,
            "plan": high_risk_plan,
        }
        response = await async_client.post("/v1/enforce", json=request)
        data = response.json()
        assert data["trust_impact"] < 0


# =============================================================================
# POLICY LISTING — policies exist and are well-formed
# =============================================================================


@pytest.mark.anyio
class TestPolicyListing:
    """Catches: missing policies → no enforcement → anarchy."""

    async def test_list_policies_returns_nonempty(self, async_client: AsyncClient):
        response = await async_client.get("/v1/enforce/policies")
        assert response.status_code == 200
        data = response.json()
        assert len(data["policies"]) > 0

    async def test_policy_has_required_fields(self, async_client: AsyncClient):
        response = await async_client.get("/v1/enforce/policies")
        for policy in response.json()["policies"]:
            assert "id" in policy
            assert "name" in policy
            assert "constraints" in policy

    async def test_get_specific_policy(self, async_client: AsyncClient):
        response = await async_client.get("/v1/enforce/policies/basis-core-security")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "basis-core-security"
        assert len(data["constraints"]) > 0

    async def test_nonexistent_policy_returns_404(self, async_client: AsyncClient):
        response = await async_client.get("/v1/enforce/policies/nonexistent")
        assert response.status_code == 404
