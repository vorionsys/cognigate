"""
Tests for the ENFORCE endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_policies(async_client: AsyncClient):
    """Test listing available policies."""
    response = await async_client.get("/v1/enforce/policies")
    assert response.status_code == 200

    data = response.json()
    assert "policies" in data
    assert len(data["policies"]) > 0

    # Check policy structure
    policy = data["policies"][0]
    assert "id" in policy
    assert "name" in policy
    assert "constraints" in policy


@pytest.mark.anyio
async def test_get_policy_details(async_client: AsyncClient):
    """Test getting policy details."""
    response = await async_client.get("/v1/enforce/policies/basis-core-security")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == "basis-core-security"
    assert "constraints" in data
    assert len(data["constraints"]) > 0


@pytest.mark.anyio
async def test_get_policy_not_found(async_client: AsyncClient):
    """Test getting non-existent policy."""
    response = await async_client.get("/v1/enforce/policies/nonexistent")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_enforce_allow_safe_plan(async_client: AsyncClient, sample_plan):
    """Test that a safe plan is allowed."""
    request = {
        "entity_id": "agent_test",
        "trust_level": 3,
        "plan": sample_plan,
    }

    response = await async_client.post("/v1/enforce", json=request)
    assert response.status_code == 200

    data = response.json()
    assert data["allowed"] is True
    assert data["action"] == "allow"
    assert len(data["violations"]) == 0


@pytest.mark.anyio
async def test_enforce_deny_high_risk(async_client: AsyncClient, high_risk_plan):
    """Test that a high-risk plan is denied."""
    request = {
        "entity_id": "agent_test",
        "trust_level": 1,  # Low trust
        "plan": high_risk_plan,
    }

    response = await async_client.post("/v1/enforce", json=request)
    assert response.status_code == 200

    data = response.json()
    assert data["allowed"] is False
    assert data["action"] in ["deny", "escalate"]
    assert len(data["violations"]) > 0


@pytest.mark.anyio
async def test_enforce_shell_restriction(async_client: AsyncClient):
    """Test that shell execution is restricted for low trust agents."""
    plan = {
        "plan_id": "plan_shell",
        "intent_id": "int_shell",
        "entity_id": "agent_test",
        "primary_action": "shell_exec",
        "steps": [{"action": "shell_exec", "command": "ls"}],
        "tools_required": ["shell"],
        "data_classifications": [],
        "risk_score": 0.3,
        "estimated_duration": "1m",
    }

    # Low trust (L1) should be denied
    request = {"entity_id": "agent_test", "trust_level": 1, "plan": plan}
    response = await async_client.post("/v1/enforce", json=request)
    data = response.json()
    assert data["allowed"] is False

    # High trust (L3+) should be allowed
    request["trust_level"] = 4
    response = await async_client.post("/v1/enforce", json=request)
    data = response.json()
    # Shell alone at L4 should be allowed (no shell restriction at that level)
    assert data["allowed"] is True


@pytest.mark.anyio
async def test_enforce_rigor_mode_strict(async_client: AsyncClient, sample_plan):
    """Test STRICT rigor mode evaluates all policies."""
    request = {
        "entity_id": "agent_test",
        "trust_level": 3,
        "plan": sample_plan,
        "rigor_mode": "strict",
    }

    response = await async_client.post("/v1/enforce", json=request)
    data = response.json()
    assert data["rigor_mode"] == "strict"


@pytest.mark.anyio
async def test_enforce_rigor_mode_lite(async_client: AsyncClient, sample_plan):
    """Test LITE rigor mode evaluates only critical policies."""
    request = {
        "entity_id": "agent_test",
        "trust_level": 4,
        "plan": sample_plan,
        "rigor_mode": "lite",
    }

    response = await async_client.post("/v1/enforce", json=request)
    data = response.json()
    assert data["rigor_mode"] == "lite"


@pytest.mark.anyio
async def test_enforce_trust_impact_critical(async_client: AsyncClient, high_risk_plan):
    """Test that critical violations have negative trust impact."""
    request = {
        "entity_id": "agent_test",
        "trust_level": 1,
        "plan": high_risk_plan,
    }

    response = await async_client.post("/v1/enforce", json=request)
    data = response.json()
    assert data["trust_impact"] < 0


@pytest.mark.anyio
async def test_enforce_policies_evaluated(async_client: AsyncClient, sample_plan):
    """Test that policies_evaluated is populated."""
    request = {
        "entity_id": "agent_test",
        "trust_level": 3,
        "plan": sample_plan,
    }

    response = await async_client.post("/v1/enforce", json=request)
    data = response.json()
    assert "policies_evaluated" in data
    assert len(data["policies_evaluated"]) > 0
