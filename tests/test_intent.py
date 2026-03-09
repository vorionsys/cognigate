# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for intent processing — risk boundary precision, consistency,
euphemism evasion, and critic integration.

Every test answers: "What catastrophic bug does this catch?"
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.database import Base, get_session
from app.core.auth import verify_api_key
from app.routers.intent import analyze_intent
from app.core.policy_engine import policy_engine


async def _bypass_auth() -> str:
    return "test-key"


@pytest_asyncio.fixture
async def client():
    if not policy_engine.list_policies():
        policy_engine.load_default_policies()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[verify_api_key] = _bypass_auth
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(verify_api_key, None)
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


# =============================================================================
# RISK BOUNDARY PRECISION — catch off-by-one in risk scoring
# =============================================================================


class TestRiskBoundaries:
    """Catches: risk score miscalculation, boundary drift, overflow/underflow."""

    def test_base_risk_is_0_1_for_benign_input(self):
        """Baseline: a benign, no-keyword input gets exactly base risk."""
        plan = analyze_intent("Hello, how are you?", {})
        assert plan.risk_score == pytest.approx(0.1, abs=0.01)

    def test_euphemism_plus_system_path_pins_at_0_95(self):
        """Catastrophe: euphemism attack not detected → agent deletes /etc."""
        for euphemism in ["clean", "wipe", "purge", "tidy"]:
            for path in ["/etc", "/var", "/root", "system32"]:
                plan = analyze_intent(f"{euphemism} up the {path} directory", {})
                assert plan.risk_score >= 0.95, (
                    f"Euphemism+path '{euphemism}+{path}' scored {plan.risk_score}, "
                    f"expected >=0.95"
                )
                assert "euphemism_attack" in plan.risk_indicators

    def test_single_euphemism_scores_0_5_to_0_7(self):
        """Catastrophe: euphemism not flagged → stealth deletion."""
        plan = analyze_intent("Clean up the temp folder", {})
        assert 0.5 <= plan.risk_score <= 0.7
        assert "suspicious_euphemism" in plan.risk_indicators

    def test_system_path_without_euphemism_scores_0_7(self):
        """Catastrophe: system path access unflagged → unauthorized read of /etc."""
        plan = analyze_intent("Access the /etc directory", {})
        assert plan.risk_score >= 0.7
        assert "system_path_access" in plan.risk_indicators

    def test_risk_score_capped_at_1_0_never_exceeds(self):
        """Catastrophe: risk > 1.0 breaks downstream tier mapping."""
        mega_dangerous = (
            "sudo delete hack exploit bypass rm -rf nuke wipe the "
            "/root system32 everything shred kill destroy erase"
        )
        plan = analyze_intent(mega_dangerous, {})
        assert plan.risk_score <= 1.0

    def test_risk_score_never_negative(self):
        """Catastrophe: negative risk score bypasses all policy checks."""
        plan = analyze_intent("Read a file", {})
        assert plan.risk_score >= 0.0

    def test_multiple_high_risk_keywords_stack(self):
        """Catastrophe: stacking attack where each keyword alone is low-risk."""
        plan_one = analyze_intent("delete the file", {})
        plan_many = analyze_intent("delete drop hack exploit bypass admin", {})
        assert plan_many.risk_score > plan_one.risk_score

    def test_dangerous_tools_force_risk_floor_0_7(self):
        """Catastrophe: shell access scored as low-risk → unrestricted execution."""
        plan = analyze_intent("Run a shell command to list files", {})
        assert plan.risk_score >= 0.7
        assert "shell" in plan.tools_required
        assert "dangerous_tools" in plan.risk_indicators


# =============================================================================
# DETERMINISM — same input MUST produce same output, always
# =============================================================================


class TestAnalyzeIntentDeterminism:
    """Catches: non-deterministic risk scoring (e.g. from randomness, time, state)."""

    def test_identical_input_produces_identical_output(self):
        """Catastrophe: flaky risk scores → inconsistent enforcement decisions."""
        goal = "Delete old log files from /var/log"
        plan_a = analyze_intent(goal, {})
        plan_b = analyze_intent(goal, {})
        assert plan_a.risk_score == plan_b.risk_score
        assert plan_a.tools_required == plan_b.tools_required
        assert plan_a.risk_indicators == plan_b.risk_indicators
        assert plan_a.data_classifications == plan_b.data_classifications

    def test_consistency_across_100_iterations(self):
        """Catastrophe: intermittent scoring bug that only appears under load."""
        goal = "clean up the /etc directory"
        first = analyze_intent(goal, {})
        for _ in range(100):
            result = analyze_intent(goal, {})
            assert result.risk_score == first.risk_score
            assert result.risk_indicators == first.risk_indicators


# =============================================================================
# TOOL DETECTION — correct tools identified for action
# =============================================================================


class TestToolDetection:
    """Catches: missing tool detection → policy engine can't restrict dangerous actions."""

    def test_shell_keyword_detected(self):
        plan = analyze_intent("Run a shell command to list files", {})
        assert "shell" in plan.tools_required

    def test_file_write_detected(self):
        plan = analyze_intent("Write the results to a new file", {})
        assert "file_write" in plan.tools_required

    def test_database_detected(self):
        plan = analyze_intent("Run a SQL query to select user data", {})
        assert "database" in plan.tools_required

    def test_network_detected(self):
        plan = analyze_intent("Call the external API to get data", {})
        assert "network" in plan.tools_required
        assert "external_api" in plan.endpoints_required

    def test_no_tools_returns_none_sentinel(self):
        plan = analyze_intent("Hello, how are you?", {})
        assert "none" in plan.tools_required

    def test_euphemism_attack_adds_shell_and_file_delete(self):
        """Catastrophe: euphemism attack doesn't register dangerous tools."""
        plan = analyze_intent("clean up the /etc directory", {})
        assert "shell" in plan.tools_required
        assert "file_delete" in plan.tools_required


# =============================================================================
# DATA CLASSIFICATION — PII and credentials detected
# =============================================================================


class TestDataClassification:
    """Catches: PII leak when data classification misses sensitive data types."""

    def test_email_detected(self):
        plan = analyze_intent("Send email to user@example.com", {})
        assert "pii_email" in plan.data_classifications

    def test_credentials_detected(self):
        plan = analyze_intent("Get the user password from config", {})
        assert "credentials" in plan.data_classifications

    def test_ssn_detected(self):
        plan = analyze_intent("Look up the social security number", {})
        assert "pii_ssn" in plan.data_classifications

    def test_benign_input_no_classifications(self):
        plan = analyze_intent("Read the README file", {})
        assert plan.data_classifications == []


# =============================================================================
# ENDPOINT INTEGRATION — tripwire blocks at API level
# =============================================================================


@pytest.mark.asyncio
class TestIntentEndpoint:
    """Catches: API-level failures — tripwire bypass, trust assignment, response shape."""

    async def test_tripwire_blocks_rm_rf(self, client):
        """Catastrophe: rm -rf / passes through intent layer."""
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "rm -rf /",
        })
        data = resp.json()
        assert data["status"] == "blocked"
        assert "TRIPWIRE" in data.get("error", "")
        assert data["trust_level"] == 0
        assert data["trust_score"] == 0

    async def test_tripwire_blocks_sql_drop(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "DROP TABLE users",
        })
        assert resp.json()["status"] == "blocked"

    @patch(
        "app.routers.intent.get_trust_score",
        new_callable=AsyncMock,
        return_value=(450, 2),
    )
    async def test_known_agent_gets_correct_trust(self, mock_trust, client):
        """Catastrophe: agent gets wrong trust level → wrong permissions."""
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "Read a file",
        })
        data = resp.json()
        assert data["trust_score"] == 450
        assert data["trust_level"] == 2
        mock_trust.assert_awaited_with("agent_001")

    async def test_unknown_agent_defaults_to_low_trust(self, client):
        """Catastrophe: unknown agent gets high trust → full access."""
        resp = await client.post("/v1/intent", json={
            "entity_id": "never_seen_agent",
            "goal": "Read a file",
        })
        data = resp.json()
        assert data["trust_score"] == 200
        assert data["trust_level"] == 1

    async def test_trust_is_server_authoritative(self, client):
        """Trust level is resolved server-side; client override is ignored."""
        resp = await client.post("/v1/intent", json={
            "entity_id": "unknown_agent",
            "goal": "Read a file",
            "trust_level": 5,
        })
        # Server returns the DB-resolved trust (default 200/T1), NOT the
        # client-requested trust_level of 5.
        data = resp.json()
        assert data["trust_level"] == 1
        assert data["trust_score"] == 200

    async def test_intent_response_has_plan_with_risk(self, client):
        """Catastrophe: response missing risk_score → enforce can't evaluate."""
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "Delete old log files from the server",
        })
        plan = resp.json()["plan"]
        assert "risk_score" in plan
        assert isinstance(plan["risk_score"], (int, float))
        assert plan["risk_score"] > 0

    async def test_get_nonexistent_intent_returns_404(self, client):
        resp = await client.get("/v1/intent/nonexistent")
        assert resp.status_code == 404
