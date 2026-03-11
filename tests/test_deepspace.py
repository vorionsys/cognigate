# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Integration tests for Deep Space router endpoints.

Tests the /v1/deepspace/* API surface using async_client fixture.
"""

import pytest
import pytest_asyncio


# =============================================================================
# TMR Consensus Endpoint
# =============================================================================

class TestConsensusEndpoint:
    @pytest.mark.asyncio
    async def test_identical_replicas(self, async_client):
        resp = await async_client.post("/v1/deepspace/consensus", json={
            "replicas": [
                {"replicaId": "r0", "trustScore": 950},
                {"replicaId": "r1", "trustScore": 950},
                {"replicaId": "r2", "trustScore": 950},
            ],
            "riskScore": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["compositeScore"] == 950
        assert data["consensusFactor"] == 1.0
        assert data["degradationLevel"] == "FULL"
        assert data["blocked"] is False

    @pytest.mark.asyncio
    async def test_divergent_replicas(self, async_client):
        resp = await async_client.post("/v1/deepspace/consensus", json={
            "replicas": [
                {"replicaId": "r0", "trustScore": 1000},
                {"replicaId": "r1", "trustScore": 500},
                {"replicaId": "r2", "trustScore": 1000},
            ],
            "riskScore": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["compositeScore"] < 500
        assert data["blocked"] is True

    @pytest.mark.asyncio
    async def test_low_risk_bypass(self, async_client):
        resp = await async_client.post("/v1/deepspace/consensus", json={
            "replicas": [
                {"replicaId": "r0", "trustScore": 1000},
                {"replicaId": "r1", "trustScore": 500},
                {"replicaId": "r2", "trustScore": 1000},
            ],
            "riskScore": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["compositeScore"] == 500
        assert data["consensusFactor"] == 1.0

    @pytest.mark.asyncio
    async def test_too_few_replicas(self, async_client):
        resp = await async_client.post("/v1/deepspace/consensus", json={
            "replicas": [
                {"replicaId": "r0", "trustScore": 950},
                {"replicaId": "r1", "trustScore": 950},
            ],
            "riskScore": 90,
        })
        assert resp.status_code == 422  # Validation error (min_length=3)


# =============================================================================
# Monte Carlo Forecast Endpoint
# =============================================================================

class TestForecastEndpoint:
    @pytest.mark.asyncio
    async def test_default_forecast(self, async_client):
        resp = await async_client.post("/v1/deepspace/forecast", json={
            "trustScore": 900,
            "epsilon": 0.05,
            "horizonHours": 24,
            "riskScore": 80,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["rawScore"] == 900
        assert data["deratedScore"] <= 900
        assert data["band"] in ["GREEN", "YELLOW", "ORANGE", "RED"]
        assert data["requiresAction"] in [True, False]

    @pytest.mark.asyncio
    async def test_low_risk_bypass(self, async_client):
        resp = await async_client.post("/v1/deepspace/forecast", json={
            "trustScore": 900,
            "epsilon": 0.50,
            "horizonHours": 72,
            "riskScore": 30,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["deratedScore"] == 900
        assert data["band"] == "GREEN"

    @pytest.mark.asyncio
    async def test_high_epsilon_derates(self, async_client):
        resp = await async_client.post("/v1/deepspace/forecast", json={
            "trustScore": 900,
            "epsilon": 0.20,
            "horizonHours": 48,
            "riskScore": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["deratedScore"] < 900
        assert data["requiresAction"] is True


class TestChainForecastEndpoint:
    @pytest.mark.asyncio
    async def test_chain_forecast(self, async_client):
        resp = await async_client.post("/v1/deepspace/forecast/chain", json={
            "trustScore": 900,
            "epsilons": [0.05, 0.10, 0.03],
            "riskScore": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["steps"] == 3
        assert data["chainError"] > 0

    @pytest.mark.asyncio
    async def test_chain_high_epsilon(self, async_client):
        resp = await async_client.post("/v1/deepspace/forecast/chain", json={
            "trustScore": 900,
            "epsilons": [0.10] * 20,
            "riskScore": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["deratedScore"] < 900


# =============================================================================
# Evolutionary Self-Healing Endpoint
# =============================================================================

class TestEvolveEndpoint:
    @pytest.mark.asyncio
    async def test_default_evolve(self, async_client):
        resp = await async_client.post("/v1/deepspace/evolve", json={
            "rG": 0.05,
            "rL": 0.15,
            "targetRatio": 10.0,
            "generations": 10,
            "populationSize": 10,
            "seed": 42,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["bestFitness"] > 0
        assert data["blendLevel"] in ["FULL", "PARTIAL", "MINIMAL", "REJECTED"]
        assert data["targetRatio"] == 10.0
        assert len(data["fitnessHistory"]) > 0

    @pytest.mark.asyncio
    async def test_evolve_converges(self, async_client):
        resp = await async_client.post("/v1/deepspace/evolve", json={
            "rG": 0.05,
            "rL": 0.15,
            "targetRatio": 10.0,
            "generations": 50,
            "populationSize": 30,
            "seed": 123,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["achievedRatio"] > 3.0  # Better than start (3:1)
        assert data["validationPassed"] in [True, False]

    @pytest.mark.asyncio
    async def test_evolve_human_veto(self, async_client):
        resp = await async_client.post("/v1/deepspace/evolve", json={
            "rG": 0.05,
            "rL": 0.15,
            "requiresHumanVeto": True,
            "generations": 5,
            "seed": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["requiresHumanVeto"] is True


# =============================================================================
# Status Endpoint
# =============================================================================

class TestDeepSpaceStatus:
    @pytest.mark.asyncio
    async def test_status(self, async_client):
        resp = await async_client.get("/v1/deepspace/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data
        assert "tmr_consensus" in data["modules"]
        assert "monte_carlo" in data["modules"]
        assert "self_healing" in data["modules"]
        assert data["codename"] == "Deep Space Trajectory"

    @pytest.mark.asyncio
    async def test_status_module_details(self, async_client):
        resp = await async_client.get("/v1/deepspace/status")
        data = resp.json()
        tmr = data["modules"]["tmr_consensus"]
        assert tmr["enabled"] is True
        assert tmr["minReplicas"] == 3
        mc = data["modules"]["monte_carlo"]
        assert mc["defaultEpsilon"] == 0.05
        sh = data["modules"]["self_healing"]
        assert sh["defaultTargetRatio"] == 10.0
