"""
Compliance monitoring models — CA-7 Continuous Control Health.

Pydantic response models for the /v1/compliance endpoints.
Covers control health, framework snapshots, evidence exports,
and dashboard aggregations across all mapped governance frameworks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .common import generate_id, utc_now


# ---------------------------------------------------------------------------
# Enums / Literals
# ---------------------------------------------------------------------------

ControlStatus = Literal["compliant", "degraded", "non_compliant", "unknown"]
OverallStatus = Literal["compliant", "degraded", "non_compliant"]
AlertSeverity = Literal["critical", "high", "medium", "low", "info"]

SUPPORTED_FRAMEWORKS: list[str] = [
    "NIST-800-53",
    "EU-AI-ACT",
    "ISO-42001",
    "SOC-2",
    "NIST-AI-RMF",
    "CMMC-2.0",
    "GDPR",
    "SINGAPORE-PDPA",
    "JAPAN-APPI",
]

# ---------------------------------------------------------------------------
# Control-level models
# ---------------------------------------------------------------------------


class ControlHealthStatus(BaseModel):
    """Health status for a single control within a framework."""

    control_id: str = Field(..., description="Control identifier (e.g. AC-2, Article 9)")
    status: ControlStatus = Field("unknown", description="Current compliance status")
    title: str = Field("", description="Human-readable control title")
    last_checked: datetime = Field(default_factory=utc_now)
    last_evidence: Optional[datetime] = Field(
        None, description="Timestamp of most recent evidence record"
    )
    evidence_count: int = Field(0, ge=0, description="Total evidence records")
    issues: list[str] = Field(default_factory=list, description="Active issue descriptions")
    implementing_component: str = Field(
        "", description="Cognigate subsystem implementing this control"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional diagnostic details"
    )


class ControlAlert(BaseModel):
    """An alert generated when a control is degraded or non-compliant."""

    alert_id: str = Field(default_factory=lambda: generate_id("alert_"))
    control_id: str
    framework: str
    issue: str
    severity: AlertSeverity = "medium"
    detected_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Framework-level models
# ---------------------------------------------------------------------------


class FrameworkSummary(BaseModel):
    """Counts of control statuses within a framework."""

    compliant: int = 0
    degraded: int = 0
    non_compliant: int = 0
    unknown: int = 0


class FrameworkHealth(BaseModel):
    """Aggregated health for all controls in a single framework."""

    framework: str
    status: ControlStatus = "unknown"
    controls: dict[str, ControlHealthStatus] = Field(default_factory=dict)
    summary: FrameworkSummary = Field(default_factory=FrameworkSummary)


# ---------------------------------------------------------------------------
# Top-level response models
# ---------------------------------------------------------------------------


class ComplianceHealthResponse(BaseModel):
    """
    Response for GET /v1/compliance/health.

    Returns health status of all mapped controls across every framework.
    This is the primary CA-7 continuous monitoring endpoint.
    """

    timestamp: datetime = Field(default_factory=utc_now)
    overall_status: OverallStatus = "compliant"
    frameworks: dict[str, FrameworkHealth] = Field(default_factory=dict)
    alerts: list[ControlAlert] = Field(default_factory=list)


class FrameworkHealthResponse(BaseModel):
    """Response for GET /v1/compliance/health/{framework}."""

    timestamp: datetime = Field(default_factory=utc_now)
    framework: FrameworkHealth


class ControlHealthResponse(BaseModel):
    """Response for GET /v1/compliance/health/{framework}/{control_id}."""

    timestamp: datetime = Field(default_factory=utc_now)
    framework: str
    control: ControlHealthStatus
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Snapshot models (point-in-time for auditors)
# ---------------------------------------------------------------------------


class ComplianceSnapshot(BaseModel):
    """Point-in-time compliance snapshot across all frameworks."""

    snapshot_id: str = Field(default_factory=lambda: generate_id("snap_"))
    generated_at: datetime = Field(default_factory=utc_now)
    overall_status: OverallStatus = "compliant"
    frameworks: dict[str, FrameworkHealth] = Field(default_factory=dict)
    alerts: list[ControlAlert] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FrameworkSnapshot(BaseModel):
    """Point-in-time snapshot for a specific framework."""

    snapshot_id: str = Field(default_factory=lambda: generate_id("snap_"))
    generated_at: datetime = Field(default_factory=utc_now)
    framework: FrameworkHealth
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evidence models
# ---------------------------------------------------------------------------


class EvidenceRecord(BaseModel):
    """A compliance evidence record linked to a control."""

    evidence_id: str = Field(default_factory=lambda: generate_id("evd_"))
    control_id: str
    framework: str
    source: str = Field("", description="Subsystem that produced this evidence")
    event_type: str = ""
    description: str = ""
    timestamp: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)


class ControlEvidenceResponse(BaseModel):
    """Response for GET /v1/compliance/evidence/{control_id}."""

    control_id: str
    framework: Optional[str] = None
    total_records: int = 0
    evidence: list[EvidenceRecord] = Field(default_factory=list)


class FrameworkEvidenceExport(BaseModel):
    """Response for GET /v1/compliance/evidence/export/{framework}."""

    framework: str
    exported_at: datetime = Field(default_factory=utc_now)
    format: str = "json"
    total_controls: int = 0
    total_evidence: int = 0
    controls: dict[str, list[EvidenceRecord]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Monitoring / trigger models
# ---------------------------------------------------------------------------


class ComplianceCheckTriggerResponse(BaseModel):
    """Response for POST /v1/compliance/monitor/trigger."""

    triggered_at: datetime = Field(default_factory=utc_now)
    status: str = "started"
    message: str = "Full compliance health check triggered"


# ---------------------------------------------------------------------------
# Dashboard models
# ---------------------------------------------------------------------------


class DashboardFrameworkStat(BaseModel):
    """Summary statistics for a single framework on the dashboard."""

    framework: str
    status: ControlStatus = "unknown"
    total_controls: int = 0
    compliant: int = 0
    degraded: int = 0
    non_compliant: int = 0
    unknown: int = 0
    compliance_pct: float = Field(0.0, description="Percentage of controls compliant")


class ComplianceDashboardResponse(BaseModel):
    """
    Response for GET /v1/compliance/dashboard.

    Aggregated dashboard data for all frameworks with summary stats,
    recent alerts, and per-framework breakdowns.
    """

    timestamp: datetime = Field(default_factory=utc_now)
    overall_status: OverallStatus = "compliant"
    total_controls: int = 0
    total_compliant: int = 0
    total_degraded: int = 0
    total_non_compliant: int = 0
    total_unknown: int = 0
    overall_compliance_pct: float = 0.0
    frameworks: list[DashboardFrameworkStat] = Field(default_factory=list)
    recent_alerts: list[ControlAlert] = Field(default_factory=list)
