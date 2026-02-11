"""
Tests for intent processing - goal normalization and risk analysis.

Tests tripwire integration, paranoia mode (euphemism detection),
risk scoring, tool detection, data classification, and critic integration.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.routers.intent import analyze_intent
from app.core.policy_engine import policy_engine


@pytest_asyncio.fixture
async def client():
    if not policy_engine.list_policies():
        policy_engine.load_default_policies()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAnalyzeIntent:
    """Test the analyze_intent function directly."""

    def test_safe_goal_low_risk(self):
        plan = analyze_intent("Read the README file", {})
        assert plan.risk_score <= 0.3
        assert "BLOCKED" not in plan.tools_required

    def test_shell_keyword_detected(self):
        plan = analyze_intent("Run a shell command to list files", {})
        assert "shell" in plan.tools_required
        assert plan.risk_score >= 0.7  # dangerous tools

    def test_delete_keyword_high_risk(self):
        plan = analyze_intent("Delete all user records from database", {})
        assert plan.risk_score >= 0.3

    def test_multiple_high_risk_keywords(self):
        plan = analyze_intent("sudo rm -rf and hack into admin", {})
        assert plan.risk_score >= 0.6

    def test_euphemism_plus_system_path_critical(self):
        """Paranoia mode: euphemism + system path = 0.95 risk."""
        plan = analyze_intent("clean up the /etc directory", {})
        assert plan.risk_score >= 0.9
        assert "euphemism_attack" in plan.risk_indicators

    def test_euphemism_alone_moderate_risk(self):
        plan = analyze_intent("Clean up the temp folder", {})
        assert plan.risk_score >= 0.5
        assert "suspicious_euphemism" in plan.risk_indicators

    def test_system_path_alone_high_risk(self):
        plan = analyze_intent("Access the /etc directory", {})
        assert plan.risk_score >= 0.7
        assert "system_path_access" in plan.risk_indicators

    def test_email_detected_as_pii(self):
        plan = analyze_intent("Send email to user@example.com", {})
        assert "pii_email" in plan.data_classifications

    def test_password_detected_as_credentials(self):
        plan = analyze_intent("Get the user password from config", {})
        assert "credentials" in plan.data_classifications

    def test_ssn_detected(self):
        plan = analyze_intent("Look up the social security number", {})
        assert "pii_ssn" in plan.data_classifications

    def test_api_endpoint_detected(self):
        plan = analyze_intent("Call the external API to get data", {})
        assert "external_api" in plan.endpoints_required
        assert "network" in plan.tools_required

    def test_medium_risk_keywords(self):
        plan = analyze_intent("Modify the configuration and update settings", {})
        assert plan.risk_score >= 0.15

    def test_file_write_tool_detected(self):
        plan = analyze_intent("Write the results to a new file", {})
        assert "file_write" in plan.tools_required

    def test_database_tool_detected(self):
        plan = analyze_intent("Run a SQL query to select user data", {})
        assert "database" in plan.tools_required

    def test_risk_score_capped_at_1(self):
        """Risk score never exceeds 1.0."""
        plan = analyze_intent(
            "sudo delete hack exploit bypass rm -rf nuke wipe the /root system32 everything",
            {}
        )
        assert plan.risk_score <= 1.0

    def test_no_tools_returns_none(self):
        plan = analyze_intent("Hello, how are you?", {})
        assert "none" in plan.tools_required

    def test_reasoning_trace_populated(self):
        plan = analyze_intent("Read a file", {})
        assert plan.reasoning_trace is not None
        assert len(plan.reasoning_trace) > 0


@pytest.mark.asyncio
class TestIntentEndpoint:
    """Test the POST /v1/intent endpoint."""

    async def test_normalize_safe_intent(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "Read the README file and summarize it",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "normalized"
        assert data["entity_id"] == "agent_001"
        assert data["plan"] is not None

    async def test_tripwire_blocks_dangerous_intent(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "rm -rf /",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "blocked"
        assert "TRIPWIRE" in data.get("error", "")
        assert data["trust_level"] == 0

    async def test_tripwire_blocks_sql_drop(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "DROP TABLE users",
        })
        data = resp.json()
        assert data["status"] == "blocked"

    async def test_known_agent_gets_correct_trust(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "Read a file",
        })
        data = resp.json()
        assert data["trust_score"] == 450
        assert data["trust_level"] == 2

    async def test_unknown_agent_gets_default_trust(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "unknown_agent",
            "goal": "Read a file",
        })
        data = resp.json()
        assert data["trust_score"] == 200
        assert data["trust_level"] == 1

    async def test_trust_level_override(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "Read a file",
            "trust_level": 5,
        })
        data = resp.json()
        assert data["trust_level"] == 5

    async def test_intent_returns_plan_with_risk(self, client):
        resp = await client.post("/v1/intent", json={
            "entity_id": "agent_001",
            "goal": "Delete old log files from the server",
        })
        data = resp.json()
        plan = data["plan"]
        assert "risk_score" in plan
        assert plan["risk_score"] > 0

    async def test_get_intent_not_found(self, client):
        resp = await client.get("/v1/intent/nonexistent")
        assert resp.status_code == 404
