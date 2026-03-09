# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Compliance monitoring endpoints — CA-7 Continuous Control Health.

Provides real-time visibility into the compliance posture of Cognigate
across every mapped governance framework:

    NIST 800-53, EU AI Act, ISO 42001, SOC 2, NIST AI RMF,
    CMMC 2.0, GDPR, Singapore PDPA, Japan APPI.

Endpoints are PUBLIC (no admin key required) for read-only health data.
The manual trigger endpoint requires admin authentication.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import verify_admin_key
from app.core.circuit_breaker import circuit_breaker
from app.core.control_health import (
    ALL_FRAMEWORK_CONTROLS,
    ControlHealthEngine,
    SUPPORTED_FRAMEWORKS,
)
from app.core.policy_engine import policy_engine
from app.core.signatures import signature_manager
from app.core.velocity import velocity_tracker
from app.models.compliance import (
    ComplianceCheckTriggerResponse,
    ComplianceDashboardResponse,
    ComplianceHealthResponse,
    ComplianceSnapshot,
    ControlEvidenceResponse,
    ControlHealthResponse,
    FrameworkEvidenceExport,
    FrameworkHealthResponse,
    FrameworkSnapshot,
    SUPPORTED_FRAMEWORKS as FRAMEWORK_LIST,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/compliance", tags=["Compliance"])


# ---------------------------------------------------------------------------
# Lazy-initialized singleton engine
# ---------------------------------------------------------------------------

_engine: ControlHealthEngine | None = None


def _get_engine() -> ControlHealthEngine:
    """Get or create the singleton ControlHealthEngine."""
    global _engine
    if _engine is None:
        _engine = ControlHealthEngine(
            circuit_breaker=circuit_breaker,
            velocity_tracker=velocity_tracker,
            policy_engine=policy_engine,
            signature_manager=signature_manager,
        )
    return _engine


# ---------------------------------------------------------------------------
# Control Health Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=ComplianceHealthResponse)
async def get_compliance_health() -> ComplianceHealthResponse:
    """
    Returns health status of ALL mapped controls across all frameworks.

    This is the CA-7 continuous monitoring endpoint.  The response
    includes per-framework breakdowns, per-control status, and any
    active alerts.
    """
    engine = _get_engine()
    return await engine.compute_all_controls()


@router.get("/health/{framework}", response_model=FrameworkHealthResponse)
async def get_framework_health(framework: str) -> FrameworkHealthResponse:
    """
    Detailed health for a specific framework.

    Raises 404 if the framework is not recognised.
    """
    _validate_framework(framework)
    engine = _get_engine()
    fw = await engine.compute_framework_health(framework)
    return FrameworkHealthResponse(framework=fw)


@router.get(
    "/health/{framework}/{control_id}",
    response_model=ControlHealthResponse,
)
async def get_control_health(
    framework: str, control_id: str
) -> ControlHealthResponse:
    """
    Detailed health for a specific control with evidence chain.

    Raises 404 if the framework or control is not recognised.
    """
    _validate_framework(framework)
    _validate_control(framework, control_id)

    engine = _get_engine()
    control = await engine.compute_control(control_id, framework)
    evidence = await engine.get_control_evidence(control_id, framework)

    return ControlHealthResponse(
        framework=framework,
        control=control,
        evidence_summary={
            "total_records": evidence.total_records,
            "sources": list({e.source for e in evidence.evidence}),
        },
    )


# ---------------------------------------------------------------------------
# Snapshot Endpoints
# ---------------------------------------------------------------------------


@router.get("/snapshot", response_model=ComplianceSnapshot)
async def get_compliance_snapshot() -> ComplianceSnapshot:
    """
    Point-in-time compliance snapshot across all frameworks.

    Suitable for auditor export — includes a unique snapshot ID and
    generation timestamp.
    """
    engine = _get_engine()
    return await engine.get_compliance_snapshot()


@router.get("/snapshot/{framework}", response_model=FrameworkSnapshot)
async def get_framework_snapshot(framework: str) -> FrameworkSnapshot:
    """
    Snapshot for a specific framework.
    """
    _validate_framework(framework)
    engine = _get_engine()
    return await engine.get_framework_snapshot(framework)


# ---------------------------------------------------------------------------
# Evidence Endpoints
# ---------------------------------------------------------------------------


@router.get("/evidence/{control_id}", response_model=ControlEvidenceResponse)
async def get_control_evidence(
    control_id: str,
    framework: str | None = Query(
        None, description="Optional framework filter"
    ),
) -> ControlEvidenceResponse:
    """
    Get all evidence records for a specific control.

    Optionally filter by framework.
    """
    engine = _get_engine()
    return await engine.get_control_evidence(control_id, framework)


@router.get(
    "/evidence/export/{framework}",
    response_model=FrameworkEvidenceExport,
)
async def export_framework_evidence(
    framework: str,
    format: str = Query("json", description="Export format: json or oscal"),
) -> FrameworkEvidenceExport:
    """
    Export all evidence for a framework.

    Currently supports JSON format.  OSCAL support is planned.
    """
    _validate_framework(framework)
    engine = _get_engine()
    return await engine.export_framework_evidence(framework, format)


# ---------------------------------------------------------------------------
# Monitoring Triggers
# ---------------------------------------------------------------------------


@router.post(
    "/monitor/trigger",
    response_model=ComplianceCheckTriggerResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def trigger_compliance_check() -> ComplianceCheckTriggerResponse:
    """
    Manually trigger a full compliance health check.

    Requires admin authentication via X-Admin-Key header.
    """
    engine = _get_engine()
    await engine.compute_all_controls()
    logger.info("compliance_check_triggered")
    return ComplianceCheckTriggerResponse(
        status="completed",
        message="Full compliance health check completed",
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=ComplianceDashboardResponse)
async def get_compliance_dashboard() -> ComplianceDashboardResponse:
    """
    Aggregated dashboard data for all frameworks.

    Returns summary stats, per-framework breakdowns, and recent alerts.
    """
    engine = _get_engine()
    return await engine.get_dashboard()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_framework(framework: str) -> None:
    """Raise 404 if the framework is not recognised."""
    if framework not in ALL_FRAMEWORK_CONTROLS:
        raise HTTPException(
            status_code=404,
            detail=f"Framework '{framework}' not found. "
            f"Supported: {', '.join(sorted(ALL_FRAMEWORK_CONTROLS.keys()))}",
        )


def _validate_control(framework: str, control_id: str) -> None:
    """Raise 404 if the control is not mapped in the framework."""
    controls = ALL_FRAMEWORK_CONTROLS.get(framework, {})
    if control_id not in controls:
        raise HTTPException(
            status_code=404,
            detail=f"Control '{control_id}' not found in framework '{framework}'. "
            f"Available: {', '.join(sorted(controls.keys()))}",
        )
