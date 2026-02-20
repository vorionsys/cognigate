"""
Tests for compliance monitoring endpoints and ControlHealthEngine.

Covers:
- GET /v1/compliance/health — all frameworks
- GET /v1/compliance/health/{framework} — single framework
- GET /v1/compliance/health/{framework}/{control_id} — single control
- GET /v1/compliance/snapshot — full snapshot
- GET /v1/compliance/snapshot/{framework}
- GET /v1/compliance/evidence/{control_id}
- GET /v1/compliance/evidence/export/{framework}
- POST /v1/compliance/monitor/trigger — admin-only
- GET /v1/compliance/dashboard — aggregated dashboard
- ControlHealthEngine internals (degraded / compliant scenarios)
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from app.main import app
from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitConfig
from app.core.control_health import (
    ALL_FRAMEWORK_CONTROLS,
    ControlHealthEngine,
    SUPPORTED_FRAMEWORKS,
)
from app.core.policy_engine import PolicyEngine
from app.core.signatures import SignatureManager
from app.core.velocity import VelocityTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def healthy_engine() -> ControlHealthEngine:
    """Engine with all subsystems in healthy state."""
    cb = CircuitBreaker()
    vt = VelocityTracker()
    pe = PolicyEngine()
    pe.load_default_policies()

    sm = MagicMock(spec=SignatureManager)
    sm.is_initialized = True
    sm._private_key = True  # Truthy, signals keys loaded

    return ControlHealthEngine(
        circuit_breaker=cb,
        velocity_tracker=vt,
        policy_engine=pe,
        signature_manager=sm,
    )


@pytest.fixture
def degraded_engine() -> ControlHealthEngine:
    """Engine with circuit breaker open and signatures unavailable."""
    cb = CircuitBreaker()
    cb.manual_trip("test_degradation")  # Opens the circuit

    vt = VelocityTracker()

    pe = PolicyEngine()
    # No policies loaded — degrades AC-3, AC-6, RA-3, etc.

    sm = MagicMock(spec=SignatureManager)
    sm.is_initialized = False
    sm._private_key = None

    return ControlHealthEngine(
        circuit_breaker=cb,
        velocity_tracker=vt,
        policy_engine=pe,
        signature_manager=sm,
    )


# =========================================================================
# Endpoint tests (HTTP)
# =========================================================================


@pytest.mark.asyncio
class TestComplianceHealthEndpoint:
    """Tests for GET /v1/compliance/health."""

    async def test_returns_200(self, client):
        resp = await client.get("/v1/compliance/health")
        assert resp.status_code == 200

    async def test_response_has_required_fields(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        assert "timestamp" in data
        assert "overall_status" in data
        assert "frameworks" in data
        assert "alerts" in data

    async def test_overall_status_is_valid(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        assert data["overall_status"] in ("compliant", "degraded", "non_compliant")

    async def test_all_frameworks_present(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        for fw in ALL_FRAMEWORK_CONTROLS:
            assert fw in data["frameworks"], f"Missing framework: {fw}"

    async def test_framework_has_controls(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        nist = data["frameworks"]["NIST-800-53"]
        assert "status" in nist
        assert "controls" in nist
        assert "summary" in nist
        assert len(nist["controls"]) > 0

    async def test_framework_summary_counts(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        for fw_name, fw_data in data["frameworks"].items():
            summary = fw_data["summary"]
            total = (
                summary["compliant"]
                + summary["degraded"]
                + summary["non_compliant"]
                + summary["unknown"]
            )
            assert total == len(fw_data["controls"]), (
                f"Summary count mismatch in {fw_name}: "
                f"summary total={total}, controls={len(fw_data['controls'])}"
            )

    async def test_control_has_required_fields(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        control = next(
            iter(data["frameworks"]["NIST-800-53"]["controls"].values())
        )
        assert "control_id" in control
        assert "status" in control
        assert "issues" in control

    async def test_alerts_are_list(self, client):
        data = (await client.get("/v1/compliance/health")).json()
        assert isinstance(data["alerts"], list)


@pytest.mark.asyncio
class TestFrameworkHealthEndpoint:
    """Tests for GET /v1/compliance/health/{framework}."""

    async def test_known_framework_returns_200(self, client):
        resp = await client.get("/v1/compliance/health/NIST-800-53")
        assert resp.status_code == 200

    async def test_unknown_framework_returns_404(self, client):
        resp = await client.get("/v1/compliance/health/UNKNOWN-FW")
        assert resp.status_code == 404

    async def test_response_has_framework_field(self, client):
        data = (await client.get("/v1/compliance/health/EU-AI-ACT")).json()
        assert "framework" in data
        assert data["framework"]["framework"] == "EU-AI-ACT"

    async def test_eu_ai_act_has_articles(self, client):
        data = (await client.get("/v1/compliance/health/EU-AI-ACT")).json()
        controls = data["framework"]["controls"]
        assert "Article-9" in controls
        assert "Article-14" in controls


@pytest.mark.asyncio
class TestControlHealthEndpoint:
    """Tests for GET /v1/compliance/health/{framework}/{control_id}."""

    async def test_known_control_returns_200(self, client):
        resp = await client.get("/v1/compliance/health/NIST-800-53/AC-2")
        assert resp.status_code == 200

    async def test_unknown_control_returns_404(self, client):
        resp = await client.get("/v1/compliance/health/NIST-800-53/FAKE-99")
        assert resp.status_code == 404

    async def test_unknown_framework_returns_404(self, client):
        resp = await client.get("/v1/compliance/health/FAKE-FW/AC-2")
        assert resp.status_code == 404

    async def test_response_has_control_and_evidence(self, client):
        data = (await client.get("/v1/compliance/health/NIST-800-53/AU-10")).json()
        assert "control" in data
        assert "framework" in data
        assert "evidence_summary" in data
        assert data["control"]["control_id"] == "AU-10"


@pytest.mark.asyncio
class TestSnapshotEndpoints:
    """Tests for GET /v1/compliance/snapshot and /snapshot/{framework}."""

    async def test_full_snapshot_returns_200(self, client):
        resp = await client.get("/v1/compliance/snapshot")
        assert resp.status_code == 200

    async def test_full_snapshot_has_id(self, client):
        data = (await client.get("/v1/compliance/snapshot")).json()
        assert "snapshot_id" in data
        assert data["snapshot_id"].startswith("snap_")

    async def test_full_snapshot_has_frameworks(self, client):
        data = (await client.get("/v1/compliance/snapshot")).json()
        assert "frameworks" in data
        assert len(data["frameworks"]) == len(ALL_FRAMEWORK_CONTROLS)

    async def test_framework_snapshot_returns_200(self, client):
        resp = await client.get("/v1/compliance/snapshot/SOC-2")
        assert resp.status_code == 200

    async def test_framework_snapshot_unknown_returns_404(self, client):
        resp = await client.get("/v1/compliance/snapshot/FAKE-FW")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestEvidenceEndpoints:
    """Tests for GET /v1/compliance/evidence/{control_id}."""

    async def test_evidence_returns_200(self, client):
        resp = await client.get("/v1/compliance/evidence/AC-2")
        assert resp.status_code == 200

    async def test_evidence_has_records(self, client):
        data = (await client.get("/v1/compliance/evidence/AC-2")).json()
        assert "control_id" in data
        assert "evidence" in data
        assert isinstance(data["evidence"], list)
        assert data["total_records"] >= 0

    async def test_evidence_with_framework_filter(self, client):
        resp = await client.get(
            "/v1/compliance/evidence/AC-2?framework=NIST-800-53"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["framework"] == "NIST-800-53"


@pytest.mark.asyncio
class TestEvidenceExportEndpoint:
    """Tests for GET /v1/compliance/evidence/export/{framework}."""

    async def test_export_returns_200(self, client):
        resp = await client.get("/v1/compliance/evidence/export/NIST-800-53")
        assert resp.status_code == 200

    async def test_export_has_controls(self, client):
        data = (
            await client.get("/v1/compliance/evidence/export/GDPR")
        ).json()
        assert data["framework"] == "GDPR"
        assert data["total_controls"] > 0
        assert "controls" in data

    async def test_export_unknown_framework_returns_404(self, client):
        resp = await client.get("/v1/compliance/evidence/export/FAKE-FW")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestMonitorTriggerEndpoint:
    """Tests for POST /v1/compliance/monitor/trigger."""

    async def test_trigger_without_admin_key_returns_401(self, client):
        resp = await client.post("/v1/compliance/monitor/trigger")
        assert resp.status_code == 401

    async def test_trigger_with_invalid_key_returns_403(self, client):
        resp = await client.post(
            "/v1/compliance/monitor/trigger",
            headers={"X-Admin-Key": "wrong-key-value"},
        )
        assert resp.status_code == 403

    async def test_trigger_with_valid_key_returns_200(self, client):
        from app.config import get_settings

        settings = get_settings()
        resp = await client.post(
            "/v1/compliance/monitor/trigger",
            headers={"X-Admin-Key": settings.admin_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"


@pytest.mark.asyncio
class TestDashboardEndpoint:
    """Tests for GET /v1/compliance/dashboard."""

    async def test_dashboard_returns_200(self, client):
        resp = await client.get("/v1/compliance/dashboard")
        assert resp.status_code == 200

    async def test_dashboard_has_required_fields(self, client):
        data = (await client.get("/v1/compliance/dashboard")).json()
        assert "overall_status" in data
        assert "total_controls" in data
        assert "total_compliant" in data
        assert "overall_compliance_pct" in data
        assert "frameworks" in data
        assert "recent_alerts" in data

    async def test_dashboard_frameworks_are_list(self, client):
        data = (await client.get("/v1/compliance/dashboard")).json()
        assert isinstance(data["frameworks"], list)
        assert len(data["frameworks"]) == len(ALL_FRAMEWORK_CONTROLS)

    async def test_dashboard_framework_stat_has_fields(self, client):
        data = (await client.get("/v1/compliance/dashboard")).json()
        fw_stat = data["frameworks"][0]
        assert "framework" in fw_stat
        assert "status" in fw_stat
        assert "total_controls" in fw_stat
        assert "compliance_pct" in fw_stat

    async def test_dashboard_total_controls_positive(self, client):
        data = (await client.get("/v1/compliance/dashboard")).json()
        assert data["total_controls"] > 0


# =========================================================================
# Engine unit tests
# =========================================================================


@pytest.mark.asyncio
class TestControlHealthEngineHealthy:
    """Engine tests with all subsystems healthy."""

    async def test_all_controls_returns_all_frameworks(self, healthy_engine):
        result = await healthy_engine.compute_all_controls()
        for fw in ALL_FRAMEWORK_CONTROLS:
            assert fw in result.frameworks

    async def test_compliant_status_when_healthy(self, healthy_engine):
        result = await healthy_engine.compute_all_controls()
        # With policies loaded and signatures active, most controls should be
        # compliant and overall should be compliant.
        assert result.overall_status == "compliant"

    async def test_nist_ac2_compliant(self, healthy_engine):
        ctl = await healthy_engine.compute_control("AC-2", "NIST-800-53")
        assert ctl.status == "compliant"

    async def test_nist_ac3_compliant_with_policies(self, healthy_engine):
        ctl = await healthy_engine.compute_control("AC-3", "NIST-800-53")
        assert ctl.status == "compliant"
        assert ctl.details.get("policies_loaded", 0) > 0

    async def test_nist_au10_compliant_with_signatures(self, healthy_engine):
        ctl = await healthy_engine.compute_control("AU-10", "NIST-800-53")
        assert ctl.status == "compliant"

    async def test_nist_si3_compliant_with_tripwires(self, healthy_engine):
        ctl = await healthy_engine.compute_control("SI-3", "NIST-800-53")
        assert ctl.status == "compliant"
        assert ctl.details.get("patterns_loaded", 0) > 0

    async def test_eu_ai_act_article_9_compliant(self, healthy_engine):
        ctl = await healthy_engine.compute_control("Article-9", "EU-AI-ACT")
        assert ctl.status == "compliant"

    async def test_framework_health_computes(self, healthy_engine):
        fw = await healthy_engine.compute_framework_health("SOC-2")
        assert fw.framework == "SOC-2"
        assert len(fw.controls) > 0

    async def test_snapshot_has_id(self, healthy_engine):
        snap = await healthy_engine.get_compliance_snapshot()
        assert snap.snapshot_id.startswith("snap_")

    async def test_dashboard_compliance_pct(self, healthy_engine):
        dash = await healthy_engine.get_dashboard()
        assert dash.overall_compliance_pct > 0

    async def test_evidence_returns_records(self, healthy_engine):
        resp = await healthy_engine.get_control_evidence("AC-2", "NIST-800-53")
        assert resp.total_records > 0
        assert len(resp.evidence) > 0

    async def test_export_returns_all_controls(self, healthy_engine):
        export = await healthy_engine.export_framework_evidence("GDPR")
        assert export.framework == "GDPR"
        assert export.total_controls > 0


@pytest.mark.asyncio
class TestControlHealthEngineDegraded:
    """Engine tests with subsystems in degraded state."""

    async def test_degraded_overall_status(self, degraded_engine):
        result = await degraded_engine.compute_all_controls()
        assert result.overall_status in ("degraded", "non_compliant")

    async def test_circuit_breaker_open_degrades_si4(self, degraded_engine):
        ctl = await degraded_engine.compute_control("SI-4", "NIST-800-53")
        assert ctl.status == "degraded"
        assert "circuit_breaker_open" in ctl.issues

    async def test_no_policies_degrades_ac3(self, degraded_engine):
        ctl = await degraded_engine.compute_control("AC-3", "NIST-800-53")
        assert ctl.status == "non_compliant"
        assert "no_policies_loaded" in ctl.issues

    async def test_no_signatures_degrades_au9(self, degraded_engine):
        ctl = await degraded_engine.compute_control("AU-9", "NIST-800-53")
        assert ctl.status == "degraded"
        assert "signatures_not_initialized" in ctl.issues

    async def test_no_signatures_degrades_ia7(self, degraded_engine):
        ctl = await degraded_engine.compute_control("IA-7", "NIST-800-53")
        assert ctl.status == "degraded"
        assert "cryptographic_module_unavailable" in ctl.issues

    async def test_alerts_generated_for_degraded(self, degraded_engine):
        result = await degraded_engine.compute_all_controls()
        assert len(result.alerts) > 0
        # All alerts should have the required fields
        for alert in result.alerts:
            assert alert.control_id
            assert alert.framework
            assert alert.issue
            assert alert.severity in ("critical", "high", "medium", "low", "info")

    async def test_eu_ai_act_article14_degraded_cb_open(self, degraded_engine):
        ctl = await degraded_engine.compute_control("Article-14", "EU-AI-ACT")
        assert ctl.status == "degraded"
        assert "escalation_blocked_by_circuit_breaker" in ctl.issues

    async def test_no_signatures_degrades_gdpr_art30(self, degraded_engine):
        ctl = await degraded_engine.compute_control("Art-30", "GDPR")
        assert ctl.status == "degraded"

    async def test_no_policies_degrades_nist_ai_rmf_govern1(self, degraded_engine):
        ctl = await degraded_engine.compute_control("GOVERN-1", "NIST-AI-RMF")
        assert ctl.status == "degraded"


@pytest.mark.asyncio
class TestControlHealthEngineEdgeCases:
    """Edge case tests for the engine."""

    async def test_unknown_framework_returns_unknown_status(self, healthy_engine):
        ctl = await healthy_engine.compute_control("FAKE-1", "FAKE-FW")
        assert ctl.status == "unknown"

    async def test_unmapped_control_returns_unknown(self, healthy_engine):
        ctl = await healthy_engine.compute_control("FAKE-99", "NIST-800-53")
        assert ctl.status == "unknown"
        assert "Control not mapped" in ctl.issues

    async def test_halted_entity_degrades_ac2(self):
        """When entities are halted, AC-2 should show degraded."""
        cb = CircuitBreaker()
        cb.halt_entity("test-agent", "test halt")

        pe = PolicyEngine()
        pe.load_default_policies()
        sm = MagicMock(spec=SignatureManager)
        sm.is_initialized = True

        engine = ControlHealthEngine(
            circuit_breaker=cb,
            velocity_tracker=VelocityTracker(),
            policy_engine=pe,
            signature_manager=sm,
        )
        ctl = await engine.compute_control("AC-2", "NIST-800-53")
        assert ctl.status == "degraded"
        assert "1 entities halted" in ctl.issues

    async def test_framework_snapshot_metadata(self, healthy_engine):
        snap = await healthy_engine.get_framework_snapshot("SOC-2")
        assert snap.metadata.get("engine_version") == "1.0.0"

    async def test_dashboard_total_matches_sum(self, healthy_engine):
        dash = await healthy_engine.get_dashboard()
        total_from_fws = sum(fw.total_controls for fw in dash.frameworks)
        assert dash.total_controls == total_from_fws

    async def test_all_nine_frameworks_in_dashboard(self, healthy_engine):
        dash = await healthy_engine.get_dashboard()
        fw_names = {fw.framework for fw in dash.frameworks}
        for fw in ALL_FRAMEWORK_CONTROLS:
            assert fw in fw_names
