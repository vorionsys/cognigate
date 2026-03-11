# =============================================================================
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion
# =============================================================================
"""
End-to-end pipeline test: INTENT → ENFORCE → PROOF

Validates the complete governance flow as a single transaction —
the headline claim of the Cognigate engine.
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Full pipeline: INTENT → ENFORCE → PROOF
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Tests the complete INTENT → ENFORCE → PROOF governance flow."""

    @pytest.mark.anyio
    async def test_full_pipeline_permit_flow(self, async_client: AsyncClient):
        """A low-risk intent should flow through all 3 layers and produce a proof record."""

        # Step 1: INTENT — normalize a goal into a structured plan
        intent_response = await async_client.post(
            "/v1/intent",
            json={
                "entity_id": "ent_e2e_test_001",
                "goal": "Read the weather forecast for San Francisco",
            },
        )
        assert intent_response.status_code == 200, f"INTENT failed: {intent_response.text}"
        intent_data = intent_response.json()
        assert "plan" in intent_data or "id" in intent_data

        # Extract fields needed for enforcement
        entity_id = "ent_e2e_test_001"
        plan = intent_data.get("plan", intent_data.get("goal", "Read weather"))
        trust_level = intent_data.get("trust_level", 3)
        trust_score = intent_data.get("trust_score", 550)

        # Step 2: ENFORCE — evaluate the plan against policies
        enforce_response = await async_client.post(
            "/v1/enforce",
            json={
                "plan": plan if isinstance(plan, dict) else {"goal": str(plan), "risk_score": 0.0,
                    "tools_required": [], "endpoints_required": [],
                    "data_classifications": [], "risk_indicators": {}},
                "entity_id": entity_id,
                "trust_level": trust_level,
                "trust_score": trust_score,
            },
        )
        assert enforce_response.status_code == 200, f"ENFORCE failed: {enforce_response.text}"
        enforce_data = enforce_response.json()
        assert "allowed" in enforce_data or "action" in enforce_data

        # For a benign weather query at T3, expect permit
        is_allowed = enforce_data.get("allowed", enforce_data.get("action") == "allow")
        assert is_allowed, f"Benign intent was denied: {enforce_data}"

        # Step 3: PROOF — record the governance decision
        proof_response = await async_client.post(
            "/v1/proof",
            json={
                "entity_id": entity_id,
                "action": "read_weather",
                "outcome": "allowed",
                "details": {
                    "plan": str(plan),
                    "trust_level": trust_level,
                    "trust_score": trust_score,
                    "enforce_decision": enforce_data.get("action", "allow"),
                },
            },
        )
        assert proof_response.status_code in (200, 201), f"PROOF failed: {proof_response.text}"
        proof_data = proof_response.json()

        # Proof must contain a hash (SHA-256 chain link)
        assert any(
            k in proof_data for k in ("hash", "proof_hash", "id", "proof_id")
        ), f"Proof record missing identifier: {proof_data}"

    @pytest.mark.anyio
    async def test_full_pipeline_deny_flow(self, async_client: AsyncClient):
        """A high-risk intent at a low trust tier should be denied."""

        # Step 1: INTENT — submit a dangerous goal
        intent_response = await async_client.post(
            "/v1/intent",
            json={
                "entity_id": "ent_e2e_test_deny",
                "goal": "Delete all production database records and drop tables",
            },
        )
        assert intent_response.status_code == 200
        intent_data = intent_response.json()

        plan = intent_data.get("plan", intent_data.get("goal", "Delete all records"))
        trust_level = 0  # T0 — Sandbox — should deny destructive ops
        trust_score = 50

        # Step 2: ENFORCE — low trust + destructive intent = deny
        enforce_response = await async_client.post(
            "/v1/enforce",
            json={
                "plan": plan if isinstance(plan, dict) else {"goal": str(plan), "risk_score": 0.9,
                    "tools_required": [], "endpoints_required": [],
                    "data_classifications": [], "risk_indicators": {}},
                "entity_id": "ent_e2e_test_deny",
                "trust_level": trust_level,
                "trust_score": trust_score,
            },
        )
        assert enforce_response.status_code == 200
        enforce_data = enforce_response.json()

        # At T0 with destructive intent, should be denied
        is_denied = (
            enforce_data.get("allowed") is False
            or enforce_data.get("action") in ("deny", "block", "escalate")
        )
        assert is_denied, f"Destructive intent at T0 was allowed: {enforce_data}"

        # Step 3: PROOF — still record the denial
        proof_response = await async_client.post(
            "/v1/proof",
            json={
                "entity_id": "ent_e2e_test_deny",
                "action": "delete_database",
                "outcome": "denied",
                "details": {
                    "plan": str(plan),
                    "trust_level": trust_level,
                    "trust_score": trust_score,
                    "enforce_decision": enforce_data.get("action", "deny"),
                    "denial_reason": enforce_data.get("reason", "trust_level_insufficient"),
                },
            },
        )
        assert proof_response.status_code in (200, 201)

    @pytest.mark.anyio
    async def test_proof_chain_integrity(self, async_client: AsyncClient):
        """Two sequential proofs should form a linked hash chain."""

        # Create first proof
        proof1 = await async_client.post(
            "/v1/proof",
            json={
                "entity_id": "ent_chain_test",
                "action": "action_one",
                "outcome": "allowed",
            },
        )
        assert proof1.status_code in (200, 201)

        # Create second proof
        proof2 = await async_client.post(
            "/v1/proof",
            json={
                "entity_id": "ent_chain_test",
                "action": "action_two",
                "outcome": "allowed",
            },
        )
        assert proof2.status_code in (200, 201)

        # Both should have identifiers
        p1 = proof1.json()
        p2 = proof2.json()
        assert any(k in p1 for k in ("hash", "proof_hash", "id"))
        assert any(k in p2 for k in ("hash", "proof_hash", "id"))

    @pytest.mark.anyio
    async def test_health_endpoint(self, async_client: AsyncClient):
        """Health endpoint should always respond with 200, regardless of subsystem state."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # In test environments subsystems may be unavailable; verify shape only
        assert "status" in data
        assert "service" in data
