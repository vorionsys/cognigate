"""
Evidence Mapper — Automatic Proof-to-Compliance Control Mapping Engine.

This module is the ENGINE that maps every proof chain event to the
compliance controls it satisfies across all supported frameworks.

When a ProofRecord is created in the proof chain, the EvidenceMapper
determines which compliance controls that event provides evidence for,
and generates the corresponding ControlEvidence records.

Supported frameworks and their coverage:

    NIST 800-53 Rev 5    — Access control, audit, risk, integrity controls
    EU AI Act            — Articles 9-15, 17, 72
    ISO/IEC 42001        — AI management system controls
    SOC 2 Type II        — Trust services criteria (CC series)
    NIST AI RMF 1.0      — Govern, Map, Measure, Manage functions
    CMMC 2.0             — Access, audit, identity, incident, system integrity
    GDPR                 — Lawfulness, transparency, accountability, security
    Singapore PDPA       — Protection, retention, accuracy, breach notification
    Japan APPI           — Third-party provision, security measures, supervision

Proof event types mapped:

    INTENT_RECEIVED       — Agent intent submission and analysis
    DECISION_MADE         — Policy enforcement decision
    TRUST_DELTA           — Trust score change event
    EXECUTION_STARTED     — Action execution initiated
    EXECUTION_COMPLETED   — Action execution completed successfully
    EXECUTION_FAILED      — Action execution failed
    TRIPWIRE_TRIGGERED    — Deterministic security pattern match
    CIRCUIT_BREAKER_OPEN  — System-level safety halt
    CIRCUIT_BREAKER_CLOSE — Circuit recovery
    VELOCITY_EXCEEDED     — Rate limit violation
    CRITIC_VERDICT        — AI-vs-AI adversarial evaluation result
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.models.proof import ProofRecord
from app.models.evidence import (
    ControlEvidence,
    ControlHealthStatus,
    ControlMapping,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retention policies (years) — per framework
# ---------------------------------------------------------------------------
_RETENTION_YEARS: dict[str, int] = {
    "NIST-800-53": 7,
    "EU-AI-ACT": 10,
    "ISO-42001": 7,
    "SOC-2": 5,
    "NIST-AI-RMF": 7,
    "CMMC": 7,
    "GDPR": 6,
    "SINGAPORE-PDPA": 7,
    "JAPAN-APPI": 7,
}


def _retention_expiry(framework: str) -> datetime:
    """Calculate retention expiry for a given framework."""
    years = _RETENTION_YEARS.get(framework, 7)
    return datetime.utcnow() + timedelta(days=365 * years)


# ============================================================================
# EVIDENCE MAP — Exhaustive mapping of proof events to compliance controls
# ============================================================================
#
# Structure:
#   event_type -> framework -> list of mapping rules
#
# Each mapping rule:
#   control   — Control identifier within the framework
#   type      — Evidence type (log, metric, attestation, configuration, test_result)
#   category  — Evidence category for grouping
#   desc      — Human-readable description for auditors
#   status    — Compliance status (satisfies, partially_satisfies, supports)
#
# ============================================================================

EVIDENCE_MAP: dict[str, dict[str, list[dict]]] = {

    # ======================================================================
    # INTENT_RECEIVED — Agent submits an intent for governance evaluation
    # ======================================================================
    "INTENT_RECEIVED": {
        "NIST-800-53": [
            {"control": "RA-3", "type": "log", "category": "risk_assessment",
             "desc": "Real-time risk assessment initiated for agent intent",
             "status": "satisfies"},
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: intent submission recorded",
             "status": "satisfies"},
            {"control": "AU-3", "type": "log", "category": "audit",
             "desc": "Audit record content: entity, intent type, timestamp captured",
             "status": "satisfies"},
            {"control": "AU-12", "type": "log", "category": "audit",
             "desc": "Audit record generation at intent submission point",
             "status": "satisfies"},
            {"control": "SI-4", "type": "log", "category": "system_integrity",
             "desc": "System monitoring: agent action intent captured for analysis",
             "status": "partially_satisfies"},
            {"control": "AC-2", "type": "log", "category": "access_control",
             "desc": "Account management: entity identity verified at intent submission",
             "status": "supports"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "log", "category": "risk_assessment",
             "desc": "Risk management system input: intent logged for risk evaluation",
             "status": "satisfies"},
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: intent automatically logged with traceability",
             "status": "satisfies"},
            {"control": "Article-13", "type": "log", "category": "transparency",
             "desc": "Transparency: agent intent logged with full context for review",
             "status": "satisfies"},
            {"control": "Article-14", "type": "log", "category": "accountability",
             "desc": "Human oversight: intent available for human review before execution",
             "status": "partially_satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.2.6", "type": "log", "category": "system_integrity",
             "desc": "AI system monitoring: intent received and logged for governance",
             "status": "satisfies"},
            {"control": "A.6.1.4", "type": "log", "category": "risk_assessment",
             "desc": "AI risk assessment input: agent intent captured for evaluation",
             "status": "satisfies"},
            {"control": "A.8.4", "type": "log", "category": "audit",
             "desc": "AI system operation documented: intent lifecycle started",
             "status": "partially_satisfies"},
            {"control": "A.10.2", "type": "log", "category": "audit",
             "desc": "Monitoring and measurement: intent event recorded",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC2.1", "type": "log", "category": "audit",
             "desc": "Information and communication: intent data captured and communicated",
             "status": "satisfies"},
            {"control": "CC3.1", "type": "log", "category": "risk_assessment",
             "desc": "Risk assessment: intent triggers risk evaluation process",
             "status": "satisfies"},
            {"control": "CC7.1", "type": "log", "category": "system_integrity",
             "desc": "System operations monitoring: agent intent detected and logged",
             "status": "satisfies"},
            {"control": "CC7.2", "type": "log", "category": "system_integrity",
             "desc": "Anomaly detection: intent analyzed for anomalous patterns",
             "status": "partially_satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MAP-1.1", "type": "log", "category": "risk_assessment",
             "desc": "Intended purpose documented: agent intent captured with context",
             "status": "satisfies"},
            {"control": "MAP-2.1", "type": "log", "category": "risk_assessment",
             "desc": "AI risks identified: intent evaluated against known risk patterns",
             "status": "satisfies"},
            {"control": "MEASURE-2.6", "type": "log", "category": "system_integrity",
             "desc": "AI system performance measured: intent processing metrics captured",
             "status": "partially_satisfies"},
            {"control": "GOVERN-1.2", "type": "log", "category": "accountability",
             "desc": "Accountability structure: intent linked to responsible entity",
             "status": "supports"},
        ],
        "CMMC": [
            {"control": "AU.L2-3.3.1", "type": "log", "category": "audit",
             "desc": "System-level audit: agent intent submission event logged",
             "status": "satisfies"},
            {"control": "AU.L2-3.3.2", "type": "log", "category": "audit",
             "desc": "Audit record content: intent event captures entity and action details",
             "status": "satisfies"},
            {"control": "SI.L1-3.14.1", "type": "log", "category": "system_integrity",
             "desc": "System flaw identification: intent analyzed for security flaws",
             "status": "partially_satisfies"},
        ],
        "GDPR": [
            {"control": "Article-5", "type": "log", "category": "data_governance",
             "desc": "Lawfulness and transparency: intent processing purpose recorded",
             "status": "partially_satisfies"},
            {"control": "Article-13", "type": "log", "category": "transparency",
             "desc": "Information provided: intent data processing details logged",
             "status": "satisfies"},
            {"control": "Article-30", "type": "log", "category": "audit",
             "desc": "Records of processing: intent submission recorded in processing log",
             "status": "satisfies"},
        ],
        "SINGAPORE-PDPA": [
            {"control": "Part-IV-s24", "type": "log", "category": "data_protection",
             "desc": "Protection obligation: intent submission recorded with proof chain integrity",
             "status": "satisfies"},
            {"control": "Part-IV-s26", "type": "log", "category": "retention",
             "desc": "Retention limitation: intent record subject to 7-year retention policy",
             "status": "satisfies"},
        ],
        "JAPAN-APPI": [
            {"control": "Art-23", "type": "log", "category": "third_party",
             "desc": "Third-party provision: entity management logging for intent submission",
             "status": "satisfies"},
            {"control": "Art-25", "type": "log", "category": "security",
             "desc": "Security measures: intent recorded in proof chain with crypto verification",
             "status": "satisfies"},
            {"control": "Art-26", "type": "log", "category": "supervision",
             "desc": "Supervision: admin monitoring endpoint captures intent for oversight",
             "status": "partially_satisfies"},
        ],
    },

    # ======================================================================
    # DECISION_MADE — Policy enforcement decision rendered
    # ======================================================================
    "DECISION_MADE": {
        "NIST-800-53": [
            {"control": "AC-3", "type": "attestation", "category": "access_control",
             "desc": "Access enforcement: policy decision (allow/deny/escalate/modify) rendered",
             "status": "satisfies"},
            {"control": "AC-6", "type": "attestation", "category": "access_control",
             "desc": "Least privilege: action scoped to entity trust level and permissions",
             "status": "satisfies"},
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: authorization decision recorded",
             "status": "satisfies"},
            {"control": "AU-3", "type": "log", "category": "audit",
             "desc": "Audit record with entity, action, decision result, and timestamp",
             "status": "satisfies"},
            {"control": "AU-6", "type": "log", "category": "audit",
             "desc": "Audit review: decision available for compliance review and analysis",
             "status": "partially_satisfies"},
            {"control": "CA-7", "type": "attestation", "category": "risk_assessment",
             "desc": "Continuous monitoring: real-time policy enforcement decision",
             "status": "satisfies"},
            {"control": "SI-4", "type": "log", "category": "system_integrity",
             "desc": "System monitoring: enforcement decision logged with full context",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk management decision: action risk evaluated and decision rendered",
             "status": "satisfies"},
            {"control": "Article-11", "type": "log", "category": "audit",
             "desc": "Technical documentation: decision rationale and policy applied recorded",
             "status": "satisfies"},
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: enforcement decision immutably logged",
             "status": "satisfies"},
            {"control": "Article-13", "type": "attestation", "category": "transparency",
             "desc": "Transparency: decision outcome and reasoning available for inspection",
             "status": "satisfies"},
            {"control": "Article-14", "type": "attestation", "category": "accountability",
             "desc": "Human oversight: escalation path available for denied/modified actions",
             "status": "satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.5.2", "type": "attestation", "category": "access_control",
             "desc": "AI policy enforcement: decision aligned with organizational AI policy",
             "status": "satisfies"},
            {"control": "A.5.4", "type": "attestation", "category": "accountability",
             "desc": "Roles and responsibilities: decision linked to entity trust level",
             "status": "satisfies"},
            {"control": "A.6.2.2", "type": "attestation", "category": "risk_assessment",
             "desc": "AI risk treatment: risk-based enforcement decision rendered",
             "status": "satisfies"},
            {"control": "A.9.2", "type": "log", "category": "audit",
             "desc": "Performance evaluation input: decision outcome logged for review",
             "status": "satisfies"},
            {"control": "A.10.2", "type": "log", "category": "audit",
             "desc": "Monitoring: enforcement decision captured for continuous monitoring",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC5.1", "type": "attestation", "category": "access_control",
             "desc": "Control activities: policy enforcement executed on agent action",
             "status": "satisfies"},
            {"control": "CC5.2", "type": "attestation", "category": "access_control",
             "desc": "Control selection: appropriate policy applied based on risk assessment",
             "status": "satisfies"},
            {"control": "CC6.1", "type": "attestation", "category": "access_control",
             "desc": "Logical access: entity identity verified and access decision enforced",
             "status": "satisfies"},
            {"control": "CC6.3", "type": "attestation", "category": "access_control",
             "desc": "Access authorization: role-based trust level determines action scope",
             "status": "satisfies"},
            {"control": "CC7.2", "type": "log", "category": "system_integrity",
             "desc": "Anomaly detection: denied or modified decisions flag potential threats",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "GOVERN-1.1", "type": "attestation", "category": "accountability",
             "desc": "AI governance: enforcement decision applied per organizational policy",
             "status": "satisfies"},
            {"control": "GOVERN-4.1", "type": "attestation", "category": "accountability",
             "desc": "Organizational AI policy applied in real-time enforcement",
             "status": "satisfies"},
            {"control": "MANAGE-1.1", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk management: AI risk mitigated through enforcement decision",
             "status": "satisfies"},
            {"control": "MANAGE-2.2", "type": "log", "category": "incident_response",
             "desc": "Response mechanisms: denied actions trigger documented response",
             "status": "partially_satisfies"},
        ],
        "CMMC": [
            {"control": "AC.L1-3.1.1", "type": "attestation", "category": "access_control",
             "desc": "Authorized access control: system enforces access decisions",
             "status": "satisfies"},
            {"control": "AC.L1-3.1.2", "type": "attestation", "category": "access_control",
             "desc": "Transaction control: individual actions authorized or denied",
             "status": "satisfies"},
            {"control": "AC.L2-3.1.5", "type": "attestation", "category": "access_control",
             "desc": "Least privilege: action scope limited by trust level",
             "status": "satisfies"},
            {"control": "AU.L2-3.3.1", "type": "log", "category": "audit",
             "desc": "Audit event: enforcement decision logged in proof chain",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-6", "type": "attestation", "category": "data_governance",
             "desc": "Lawfulness of processing: processing decision based on legal basis",
             "status": "partially_satisfies"},
            {"control": "Article-22", "type": "attestation", "category": "accountability",
             "desc": "Automated decision-making: safeguards in place via escalation path",
             "status": "satisfies"},
            {"control": "Article-25", "type": "attestation", "category": "data_governance",
             "desc": "Data protection by design: enforcement applied before data processing",
             "status": "satisfies"},
            {"control": "Article-32", "type": "attestation", "category": "system_integrity",
             "desc": "Security of processing: access control decision enforced",
             "status": "partially_satisfies"},
        ],
        "SINGAPORE-PDPA": [
            {"control": "Part-IV-s24", "type": "attestation", "category": "data_protection",
             "desc": "Protection obligation: enforcement decision protects personal data integrity",
             "status": "satisfies"},
            {"control": "Part-V-s28", "type": "attestation", "category": "accuracy",
             "desc": "Accuracy obligation: decision validated against current policy state",
             "status": "partially_satisfies"},
        ],
        "JAPAN-APPI": [
            {"control": "Art-23", "type": "attestation", "category": "third_party",
             "desc": "Third-party provision: authorization decision logged for entity actions",
             "status": "satisfies"},
            {"control": "Art-25", "type": "attestation", "category": "security",
             "desc": "Security measures: enforcement decision secured via proof chain and crypto",
             "status": "satisfies"},
        ],
    },

    # ======================================================================
    # TRUST_DELTA — Entity trust score changed
    # ======================================================================
    "TRUST_DELTA": {
        "NIST-800-53": [
            {"control": "AC-2", "type": "metric", "category": "identity_management",
             "desc": "Account management: entity trust level adjusted based on behavior",
             "status": "satisfies"},
            {"control": "IA-5", "type": "metric", "category": "identity_management",
             "desc": "Authenticator management: trust score reflects credential reliability",
             "status": "partially_satisfies"},
            {"control": "RA-3", "type": "metric", "category": "risk_assessment",
             "desc": "Risk assessment: entity risk profile updated with trust delta",
             "status": "satisfies"},
            {"control": "CA-7", "type": "metric", "category": "risk_assessment",
             "desc": "Continuous monitoring: trust score change reflects ongoing assessment",
             "status": "satisfies"},
            {"control": "SI-4", "type": "metric", "category": "system_integrity",
             "desc": "System monitoring: behavioral trust adjustment captured",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "metric", "category": "risk_assessment",
             "desc": "Risk management: entity risk level dynamically recalculated",
             "status": "satisfies"},
            {"control": "Article-15", "type": "metric", "category": "system_integrity",
             "desc": "Accuracy and robustness: trust scoring demonstrates system reliability",
             "status": "partially_satisfies"},
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: trust change event immutably recorded",
             "status": "satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.2.4", "type": "metric", "category": "risk_assessment",
             "desc": "AI risk assessment update: trust delta reflects risk change",
             "status": "satisfies"},
            {"control": "A.9.3", "type": "metric", "category": "audit",
             "desc": "Management review input: trust trend data for governance review",
             "status": "satisfies"},
            {"control": "A.10.3", "type": "metric", "category": "system_integrity",
             "desc": "Continual improvement: trust changes drive adaptive behavior",
             "status": "partially_satisfies"},
        ],
        "SOC-2": [
            {"control": "CC3.2", "type": "metric", "category": "risk_assessment",
             "desc": "Risk identification: entity risk re-evaluated via trust delta",
             "status": "satisfies"},
            {"control": "CC3.3", "type": "metric", "category": "risk_assessment",
             "desc": "Risk evaluation: trust score change quantifies behavioral risk",
             "status": "satisfies"},
            {"control": "CC4.1", "type": "metric", "category": "audit",
             "desc": "Monitoring activities: trust changes monitored continuously",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MEASURE-2.2", "type": "metric", "category": "risk_assessment",
             "desc": "AI system trustworthiness measured via trust delta",
             "status": "satisfies"},
            {"control": "MEASURE-2.5", "type": "metric", "category": "system_integrity",
             "desc": "AI system fairness: trust adjustments applied equitably",
             "status": "partially_satisfies"},
            {"control": "MANAGE-2.4", "type": "metric", "category": "risk_assessment",
             "desc": "Risk management: trust-based risk response mechanism operational",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "IA.L1-3.5.1", "type": "metric", "category": "identity_management",
             "desc": "Identification: entity identity validated through trust scoring",
             "status": "partially_satisfies"},
            {"control": "IA.L1-3.5.2", "type": "metric", "category": "identity_management",
             "desc": "Authentication: trust level reflects authentication confidence",
             "status": "partially_satisfies"},
            {"control": "SI.L2-3.14.6", "type": "metric", "category": "system_integrity",
             "desc": "System monitoring: behavioral changes tracked via trust delta",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-5", "type": "metric", "category": "data_governance",
             "desc": "Accountability: trust scoring demonstrates processing oversight",
             "status": "supports"},
            {"control": "Article-35", "type": "metric", "category": "risk_assessment",
             "desc": "Data protection impact: trust delta feeds impact assessment",
             "status": "partially_satisfies"},
        ],
    },

    # ======================================================================
    # EXECUTION_STARTED — Action execution initiated
    # ======================================================================
    "EXECUTION_STARTED": {
        "NIST-800-53": [
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: action execution initiated",
             "status": "satisfies"},
            {"control": "AU-12", "type": "log", "category": "audit",
             "desc": "Audit generation: execution start event generated and recorded",
             "status": "satisfies"},
            {"control": "CM-3", "type": "log", "category": "configuration_management",
             "desc": "Configuration change control: action execution tracked",
             "status": "partially_satisfies"},
            {"control": "SI-7", "type": "log", "category": "system_integrity",
             "desc": "Software integrity: execution initiated with verified policy state",
             "status": "partially_satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: action execution start immutably recorded",
             "status": "satisfies"},
            {"control": "Article-14", "type": "log", "category": "accountability",
             "desc": "Human oversight: execution start point logged for intervention window",
             "status": "partially_satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.2.6", "type": "log", "category": "system_integrity",
             "desc": "AI system monitoring: execution lifecycle started",
             "status": "satisfies"},
            {"control": "A.8.2", "type": "log", "category": "configuration_management",
             "desc": "Operational planning: execution initiated under governance",
             "status": "partially_satisfies"},
        ],
        "SOC-2": [
            {"control": "CC7.1", "type": "log", "category": "system_integrity",
             "desc": "System operations: execution start event detected and logged",
             "status": "satisfies"},
            {"control": "CC8.1", "type": "log", "category": "configuration_management",
             "desc": "Change management: action execution tracked from initiation",
             "status": "partially_satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MANAGE-3.1", "type": "log", "category": "accountability",
             "desc": "AI deployment: execution initiated under governance framework",
             "status": "satisfies"},
            {"control": "MEASURE-1.1", "type": "log", "category": "system_integrity",
             "desc": "Performance measurement: execution timing captured",
             "status": "partially_satisfies"},
        ],
        "CMMC": [
            {"control": "AU.L2-3.3.1", "type": "log", "category": "audit",
             "desc": "Audit event: execution start recorded in proof chain",
             "status": "satisfies"},
            {"control": "SI.L2-3.14.7", "type": "log", "category": "system_integrity",
             "desc": "Unauthorized activity detection: execution tracked from start",
             "status": "partially_satisfies"},
        ],
        "GDPR": [
            {"control": "Article-30", "type": "log", "category": "audit",
             "desc": "Records of processing: data processing execution initiated and logged",
             "status": "satisfies"},
        ],
    },

    # ======================================================================
    # EXECUTION_COMPLETED — Action execution completed successfully
    # ======================================================================
    "EXECUTION_COMPLETED": {
        "NIST-800-53": [
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: action execution completed successfully",
             "status": "satisfies"},
            {"control": "AU-3", "type": "log", "category": "audit",
             "desc": "Audit record: execution result with inputs/outputs hash recorded",
             "status": "satisfies"},
            {"control": "AU-9", "type": "attestation", "category": "audit",
             "desc": "Audit protection: execution record immutably chained in proof ledger",
             "status": "satisfies"},
            {"control": "SC-13", "type": "attestation", "category": "system_integrity",
             "desc": "Cryptographic protection: execution result hash-chained",
             "status": "satisfies"},
            {"control": "SI-7", "type": "attestation", "category": "system_integrity",
             "desc": "Integrity verification: output hash proves execution integrity",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: execution completion with outputs recorded",
             "status": "satisfies"},
            {"control": "Article-15", "type": "attestation", "category": "system_integrity",
             "desc": "Accuracy: execution completed with verified output integrity",
             "status": "satisfies"},
            {"control": "Article-17", "type": "attestation", "category": "system_integrity",
             "desc": "Quality management: successful execution demonstrates system quality",
             "status": "partially_satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.2.6", "type": "log", "category": "system_integrity",
             "desc": "AI system monitoring: execution completed successfully",
             "status": "satisfies"},
            {"control": "A.9.2", "type": "metric", "category": "audit",
             "desc": "Performance evaluation: successful execution contributes to metrics",
             "status": "satisfies"},
            {"control": "A.7.3", "type": "attestation", "category": "system_integrity",
             "desc": "AI system lifecycle: execution within expected parameters",
             "status": "partially_satisfies"},
        ],
        "SOC-2": [
            {"control": "CC7.1", "type": "log", "category": "system_integrity",
             "desc": "System operations: execution completed and result logged",
             "status": "satisfies"},
            {"control": "CC7.3", "type": "log", "category": "system_integrity",
             "desc": "Evaluation of events: successful completion evaluated against expectations",
             "status": "partially_satisfies"},
            {"control": "CC9.1", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk mitigation: action completed within governance constraints",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MEASURE-1.1", "type": "metric", "category": "system_integrity",
             "desc": "Performance measurement: execution success recorded",
             "status": "satisfies"},
            {"control": "MANAGE-4.1", "type": "log", "category": "accountability",
             "desc": "AI system operated within defined parameters",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "AU.L2-3.3.1", "type": "log", "category": "audit",
             "desc": "Audit event: execution completion recorded with hash verification",
             "status": "satisfies"},
            {"control": "SC.L2-3.13.11", "type": "attestation", "category": "system_integrity",
             "desc": "Cryptographic integrity: execution result hash-chained in ledger",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-5", "type": "attestation", "category": "data_governance",
             "desc": "Integrity and confidentiality: processing completed with verified integrity",
             "status": "partially_satisfies"},
            {"control": "Article-30", "type": "log", "category": "audit",
             "desc": "Records of processing: processing activity completed and recorded",
             "status": "satisfies"},
            {"control": "Article-32", "type": "attestation", "category": "system_integrity",
             "desc": "Security of processing: execution integrity verified via hash chain",
             "status": "partially_satisfies"},
        ],
        "SINGAPORE-PDPA": [
            {"control": "Part-IV-s24", "type": "attestation", "category": "data_protection",
             "desc": "Protection obligation: execution completed with proof chain integrity verified",
             "status": "satisfies"},
            {"control": "Part-IV-s26", "type": "log", "category": "retention",
             "desc": "Retention limitation: execution record retained per 7-year policy",
             "status": "satisfies"},
            {"control": "Part-V-s26C", "type": "log", "category": "breach_notification",
             "desc": "Data breach notification: successful execution — no breach condition",
             "status": "supports"},
        ],
        "JAPAN-APPI": [
            {"control": "Art-23", "type": "log", "category": "third_party",
             "desc": "Third-party provision: execution completion logged for entity audit trail",
             "status": "satisfies"},
            {"control": "Art-25", "type": "attestation", "category": "security",
             "desc": "Security measures: execution integrity verified via proof chain and crypto",
             "status": "satisfies"},
            {"control": "Art-26", "type": "log", "category": "supervision",
             "desc": "Supervision: execution completion available at admin monitoring endpoints",
             "status": "satisfies"},
        ],
    },

    # ======================================================================
    # EXECUTION_FAILED — Action execution failed
    # ======================================================================
    "EXECUTION_FAILED": {
        "NIST-800-53": [
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: action execution failure recorded",
             "status": "satisfies"},
            {"control": "IR-4", "type": "log", "category": "incident_response",
             "desc": "Incident handling: execution failure captured for incident analysis",
             "status": "satisfies"},
            {"control": "IR-5", "type": "log", "category": "incident_response",
             "desc": "Incident monitoring: failure event tracked for pattern analysis",
             "status": "satisfies"},
            {"control": "SI-4", "type": "log", "category": "system_integrity",
             "desc": "System monitoring: execution failure detected and logged",
             "status": "satisfies"},
            {"control": "RA-5", "type": "log", "category": "risk_assessment",
             "desc": "Vulnerability monitoring: failure may indicate vulnerability",
             "status": "partially_satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: execution failure immutably recorded",
             "status": "satisfies"},
            {"control": "Article-15", "type": "log", "category": "system_integrity",
             "desc": "Accuracy and robustness: failure logged for reliability analysis",
             "status": "satisfies"},
            {"control": "Article-17", "type": "log", "category": "system_integrity",
             "desc": "Quality management: failure feeds quality improvement process",
             "status": "satisfies"},
            {"control": "Article-72", "type": "log", "category": "incident_response",
             "desc": "Serious incident: execution failure logged as potential incident",
             "status": "partially_satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.1.2", "type": "log", "category": "incident_response",
             "desc": "Incident management: AI execution failure captured",
             "status": "satisfies"},
            {"control": "A.9.4", "type": "log", "category": "audit",
             "desc": "Nonconformity handling: execution failure is nonconformity event",
             "status": "satisfies"},
            {"control": "A.10.3", "type": "log", "category": "system_integrity",
             "desc": "Continual improvement: failure data drives system improvement",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC3.3", "type": "log", "category": "risk_assessment",
             "desc": "Risk evaluation: execution failure increases risk assessment",
             "status": "satisfies"},
            {"control": "CC7.3", "type": "log", "category": "incident_response",
             "desc": "Event evaluation: failure analyzed for security implications",
             "status": "satisfies"},
            {"control": "CC7.4", "type": "log", "category": "incident_response",
             "desc": "Incident response: failure triggers response evaluation",
             "status": "partially_satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MEASURE-2.11", "type": "log", "category": "system_integrity",
             "desc": "System reliability: failure event recorded for reliability metrics",
             "status": "satisfies"},
            {"control": "MANAGE-2.2", "type": "log", "category": "incident_response",
             "desc": "Incident response: AI execution failure tracked and managed",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "IR.L2-3.6.1", "type": "log", "category": "incident_response",
             "desc": "Incident handling: execution failure captured as incident",
             "status": "satisfies"},
            {"control": "IR.L2-3.6.2", "type": "log", "category": "incident_response",
             "desc": "Incident reporting: failure event available for reporting",
             "status": "satisfies"},
            {"control": "AU.L2-3.3.1", "type": "log", "category": "audit",
             "desc": "Audit event: execution failure recorded in proof chain",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-33", "type": "log", "category": "incident_response",
             "desc": "Breach notification: execution failure logged for breach assessment",
             "status": "partially_satisfies"},
            {"control": "Article-32", "type": "log", "category": "system_integrity",
             "desc": "Security of processing: failure event feeds security assessment",
             "status": "partially_satisfies"},
        ],
    },

    # ======================================================================
    # TRIPWIRE_TRIGGERED — Deterministic security pattern match
    # ======================================================================
    "TRIPWIRE_TRIGGERED": {
        "NIST-800-53": [
            {"control": "SI-4", "type": "attestation", "category": "system_integrity",
             "desc": "Intrusion detection: deterministic security pattern matched and blocked",
             "status": "satisfies"},
            {"control": "SI-7", "type": "attestation", "category": "system_integrity",
             "desc": "Software integrity: malicious pattern detected before execution",
             "status": "satisfies"},
            {"control": "IR-4", "type": "log", "category": "incident_response",
             "desc": "Incident handling: tripwire trigger initiates incident response",
             "status": "satisfies"},
            {"control": "IR-6", "type": "log", "category": "incident_response",
             "desc": "Incident reporting: tripwire event reported for analysis",
             "status": "satisfies"},
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: security tripwire trigger recorded",
             "status": "satisfies"},
            {"control": "SC-7", "type": "attestation", "category": "system_integrity",
             "desc": "Boundary protection: malicious input blocked at governance boundary",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk management: high-risk pattern detected and mitigated",
             "status": "satisfies"},
            {"control": "Article-15", "type": "attestation", "category": "system_integrity",
             "desc": "Robustness: system resilient against detected attack pattern",
             "status": "satisfies"},
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: security event immutably recorded",
             "status": "satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.5.3", "type": "attestation", "category": "system_integrity",
             "desc": "Information security: deterministic threat pattern blocked",
             "status": "satisfies"},
            {"control": "A.6.1.2", "type": "log", "category": "incident_response",
             "desc": "Incident management: security incident detected and handled",
             "status": "satisfies"},
            {"control": "A.6.2.6", "type": "attestation", "category": "system_integrity",
             "desc": "AI monitoring: malicious input detected in AI pipeline",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC6.6", "type": "attestation", "category": "system_integrity",
             "desc": "System boundary: malicious input blocked at system boundary",
             "status": "satisfies"},
            {"control": "CC6.7", "type": "attestation", "category": "system_integrity",
             "desc": "Data transmission: dangerous payload detected and prevented",
             "status": "satisfies"},
            {"control": "CC7.2", "type": "attestation", "category": "system_integrity",
             "desc": "Anomaly detection: deterministic pattern match identifies threat",
             "status": "satisfies"},
            {"control": "CC7.3", "type": "log", "category": "incident_response",
             "desc": "Event evaluation: tripwire event classified as security incident",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MAP-2.3", "type": "attestation", "category": "risk_assessment",
             "desc": "AI risk identification: known attack vector detected",
             "status": "satisfies"},
            {"control": "MANAGE-2.2", "type": "log", "category": "incident_response",
             "desc": "Incident response: security event managed through auto-block",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "SC.L1-3.13.1", "type": "attestation", "category": "system_integrity",
             "desc": "Communication protection: malicious input blocked at boundary",
             "status": "satisfies"},
            {"control": "SI.L1-3.14.1", "type": "attestation", "category": "system_integrity",
             "desc": "Flaw remediation: known-dangerous pattern detected and neutralized",
             "status": "satisfies"},
            {"control": "SI.L2-3.14.6", "type": "attestation", "category": "system_integrity",
             "desc": "Security monitoring: deterministic threat detection operational",
             "status": "satisfies"},
            {"control": "IR.L2-3.6.1", "type": "log", "category": "incident_response",
             "desc": "Incident handling: tripwire event captured as security incident",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-32", "type": "attestation", "category": "system_integrity",
             "desc": "Security of processing: attack vector detected and blocked",
             "status": "satisfies"},
            {"control": "Article-33", "type": "log", "category": "incident_response",
             "desc": "Breach notification: security event logged for breach assessment",
             "status": "partially_satisfies"},
        ],
    },

    # ======================================================================
    # CIRCUIT_BREAKER_OPEN — System-level safety halt activated
    # ======================================================================
    "CIRCUIT_BREAKER_OPEN": {
        "NIST-800-53": [
            {"control": "IR-4", "type": "attestation", "category": "incident_response",
             "desc": "Incident handling: autonomous system halt initiated",
             "status": "satisfies"},
            {"control": "IR-5", "type": "log", "category": "incident_response",
             "desc": "Incident monitoring: circuit breaker trip tracked for analysis",
             "status": "satisfies"},
            {"control": "SI-4", "type": "attestation", "category": "system_integrity",
             "desc": "System monitoring: threshold exceeded, system self-protected",
             "status": "satisfies"},
            {"control": "CA-7", "type": "attestation", "category": "risk_assessment",
             "desc": "Continuous monitoring: real-time risk threshold triggered system halt",
             "status": "satisfies"},
            {"control": "SC-7", "type": "attestation", "category": "system_integrity",
             "desc": "Boundary protection: system boundary locked during incident",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk management: risk threshold exceeded, system halted",
             "status": "satisfies"},
            {"control": "Article-14", "type": "attestation", "category": "accountability",
             "desc": "Human oversight: system halted pending human intervention",
             "status": "satisfies"},
            {"control": "Article-72", "type": "log", "category": "incident_response",
             "desc": "Serious incident: system halt may indicate serious incident",
             "status": "satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.1.2", "type": "attestation", "category": "incident_response",
             "desc": "Incident management: system-level safety halt executed",
             "status": "satisfies"},
            {"control": "A.7.2", "type": "attestation", "category": "system_integrity",
             "desc": "AI system safety: autonomous safety mechanism activated",
             "status": "satisfies"},
            {"control": "A.9.4", "type": "log", "category": "audit",
             "desc": "Nonconformity: circuit breaker trip is nonconformity event",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC7.3", "type": "attestation", "category": "incident_response",
             "desc": "Event evaluation: system determined threat level warrants halt",
             "status": "satisfies"},
            {"control": "CC7.4", "type": "attestation", "category": "incident_response",
             "desc": "Incident response: automatic containment via system halt",
             "status": "satisfies"},
            {"control": "CC5.3", "type": "attestation", "category": "access_control",
             "desc": "Control enforcement: system enforces halt when thresholds exceeded",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "GOVERN-1.5", "type": "attestation", "category": "accountability",
             "desc": "Kill switch: autonomous halt mechanism operational",
             "status": "satisfies"},
            {"control": "MANAGE-2.2", "type": "attestation", "category": "incident_response",
             "desc": "Incident response: AI system halted during safety event",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "IR.L2-3.6.1", "type": "attestation", "category": "incident_response",
             "desc": "Incident handling: system-wide safety halt executed",
             "status": "satisfies"},
            {"control": "SC.L1-3.13.1", "type": "attestation", "category": "system_integrity",
             "desc": "System protection: all communications halted during incident",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-32", "type": "attestation", "category": "system_integrity",
             "desc": "Security of processing: system halted to prevent data exposure",
             "status": "satisfies"},
            {"control": "Article-33", "type": "log", "category": "incident_response",
             "desc": "Breach notification: system halt triggers breach assessment",
             "status": "partially_satisfies"},
        ],
    },

    # ======================================================================
    # CIRCUIT_BREAKER_CLOSE — Circuit recovery after safety halt
    # ======================================================================
    "CIRCUIT_BREAKER_CLOSE": {
        "NIST-800-53": [
            {"control": "IR-4", "type": "log", "category": "incident_response",
             "desc": "Incident handling: system recovered from safety halt",
             "status": "satisfies"},
            {"control": "CA-7", "type": "log", "category": "risk_assessment",
             "desc": "Continuous monitoring: system returned to normal monitoring state",
             "status": "satisfies"},
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: circuit breaker recovery recorded",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-12", "type": "log", "category": "audit",
             "desc": "Record-keeping: system recovery from halt immutably recorded",
             "status": "satisfies"},
            {"control": "Article-17", "type": "log", "category": "system_integrity",
             "desc": "Quality management: system recovery demonstrates resilience",
             "status": "partially_satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.1.2", "type": "log", "category": "incident_response",
             "desc": "Incident management: incident resolved, system recovered",
             "status": "satisfies"},
            {"control": "A.10.3", "type": "log", "category": "system_integrity",
             "desc": "Continual improvement: recovery event feeds improvement process",
             "status": "partially_satisfies"},
        ],
        "SOC-2": [
            {"control": "CC7.4", "type": "log", "category": "incident_response",
             "desc": "Incident response: system recovered and operations restored",
             "status": "satisfies"},
            {"control": "CC9.1", "type": "log", "category": "risk_assessment",
             "desc": "Risk mitigation: system demonstrated successful recovery",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MANAGE-2.2", "type": "log", "category": "incident_response",
             "desc": "Incident response: AI system recovered from safety halt",
             "status": "satisfies"},
            {"control": "MANAGE-4.1", "type": "log", "category": "accountability",
             "desc": "AI system re-deployed within governance constraints",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "IR.L2-3.6.2", "type": "log", "category": "incident_response",
             "desc": "Incident reporting: recovery event documented",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-32", "type": "log", "category": "system_integrity",
             "desc": "Security of processing: processing restored after incident resolution",
             "status": "supports"},
        ],
    },

    # ======================================================================
    # VELOCITY_EXCEEDED — Rate limit violation detected
    # ======================================================================
    "VELOCITY_EXCEEDED": {
        "NIST-800-53": [
            {"control": "AC-17", "type": "attestation", "category": "access_control",
             "desc": "Remote access: rate limiting enforced on entity actions",
             "status": "satisfies"},
            {"control": "SI-4", "type": "log", "category": "system_integrity",
             "desc": "System monitoring: velocity threshold exceeded by entity",
             "status": "satisfies"},
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: rate limit violation recorded",
             "status": "satisfies"},
            {"control": "IR-4", "type": "log", "category": "incident_response",
             "desc": "Incident handling: velocity abuse may indicate attack",
             "status": "partially_satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk management: excessive usage rate detected and controlled",
             "status": "satisfies"},
            {"control": "Article-15", "type": "attestation", "category": "system_integrity",
             "desc": "Robustness: rate limiting prevents system abuse",
             "status": "satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.2.6", "type": "log", "category": "system_integrity",
             "desc": "AI monitoring: abnormal usage velocity detected",
             "status": "satisfies"},
            {"control": "A.7.2", "type": "attestation", "category": "system_integrity",
             "desc": "AI safety: velocity controls protect system from abuse",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC6.1", "type": "attestation", "category": "access_control",
             "desc": "Logical access: rate limiting controls entity access frequency",
             "status": "satisfies"},
            {"control": "CC7.2", "type": "log", "category": "system_integrity",
             "desc": "Anomaly detection: abnormal velocity pattern detected",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MAP-2.2", "type": "log", "category": "risk_assessment",
             "desc": "Risk identification: excessive AI usage rate flagged",
             "status": "satisfies"},
            {"control": "MANAGE-1.1", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk response: velocity cap enforced as risk mitigation",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "AC.L2-3.1.7", "type": "attestation", "category": "access_control",
             "desc": "Privileged function control: rate limiting restricts entity actions",
             "status": "satisfies"},
            {"control": "SI.L2-3.14.6", "type": "log", "category": "system_integrity",
             "desc": "System monitoring: velocity violation detected",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-32", "type": "attestation", "category": "system_integrity",
             "desc": "Security of processing: rate limiting protects processing systems",
             "status": "partially_satisfies"},
        ],
    },

    # ======================================================================
    # CRITIC_VERDICT — AI-vs-AI adversarial evaluation result
    # ======================================================================
    "CRITIC_VERDICT": {
        "NIST-800-53": [
            {"control": "RA-3", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk assessment: AI adversarial evaluation of action risk",
             "status": "satisfies"},
            {"control": "RA-5", "type": "attestation", "category": "risk_assessment",
             "desc": "Vulnerability assessment: critic identifies potential vulnerabilities",
             "status": "satisfies"},
            {"control": "CA-7", "type": "attestation", "category": "risk_assessment",
             "desc": "Continuous monitoring: real-time AI-based risk evaluation",
             "status": "satisfies"},
            {"control": "AU-2", "type": "log", "category": "audit",
             "desc": "Auditable event: critic verdict recorded with rationale",
             "status": "satisfies"},
            {"control": "SI-4", "type": "attestation", "category": "system_integrity",
             "desc": "System monitoring: adversarial AI provides independent verification",
             "status": "satisfies"},
        ],
        "EU-AI-ACT": [
            {"control": "Article-9", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk management: independent AI risk evaluation performed",
             "status": "satisfies"},
            {"control": "Article-10", "type": "attestation", "category": "data_governance",
             "desc": "Data governance: critic validates data handling appropriateness",
             "status": "partially_satisfies"},
            {"control": "Article-15", "type": "attestation", "category": "system_integrity",
             "desc": "Accuracy: adversarial evaluation validates AI output quality",
             "status": "satisfies"},
        ],
        "ISO-42001": [
            {"control": "A.6.2.2", "type": "attestation", "category": "risk_assessment",
             "desc": "AI risk treatment: independent AI evaluation of risk treatment",
             "status": "satisfies"},
            {"control": "A.9.2", "type": "attestation", "category": "audit",
             "desc": "Performance evaluation: AI-vs-AI evaluation provides performance data",
             "status": "satisfies"},
        ],
        "SOC-2": [
            {"control": "CC4.1", "type": "attestation", "category": "audit",
             "desc": "Monitoring: independent AI evaluation acts as monitoring control",
             "status": "satisfies"},
            {"control": "CC4.2", "type": "attestation", "category": "audit",
             "desc": "Evaluation: critic identifies and communicates deficiencies",
             "status": "satisfies"},
            {"control": "CC3.1", "type": "attestation", "category": "risk_assessment",
             "desc": "Risk assessment: AI adversarial evaluation quantifies risk",
             "status": "satisfies"},
        ],
        "NIST-AI-RMF": [
            {"control": "MEASURE-2.2", "type": "attestation", "category": "risk_assessment",
             "desc": "AI trustworthiness: adversarial evaluation measures trustworthiness",
             "status": "satisfies"},
            {"control": "MAP-3.5", "type": "attestation", "category": "risk_assessment",
             "desc": "AI benefit-risk: critic evaluates action benefit vs. risk",
             "status": "satisfies"},
            {"control": "GOVERN-4.2", "type": "attestation", "category": "accountability",
             "desc": "Accountability: independent AI verification of governance decisions",
             "status": "satisfies"},
        ],
        "CMMC": [
            {"control": "SI.L2-3.14.6", "type": "attestation", "category": "system_integrity",
             "desc": "Security monitoring: AI adversarial evaluation as monitoring layer",
             "status": "satisfies"},
            {"control": "SI.L2-3.14.7", "type": "attestation", "category": "system_integrity",
             "desc": "Unauthorized activity: critic detects potentially unauthorized actions",
             "status": "satisfies"},
        ],
        "GDPR": [
            {"control": "Article-22", "type": "attestation", "category": "accountability",
             "desc": "Automated decision-making: adversarial AI provides independent check",
             "status": "satisfies"},
            {"control": "Article-35", "type": "attestation", "category": "risk_assessment",
             "desc": "Data protection impact: critic evaluation feeds impact assessment",
             "status": "partially_satisfies"},
        ],
    },
}


class EvidenceMapper:
    """
    Automatically maps proof chain events to compliance control evidence.

    This is the core engine of the evidence layer. Given a ProofRecord,
    it consults the EVIDENCE_MAP to determine which compliance controls
    the event satisfies, and generates ControlEvidence records for each.

    Usage::

        mapper = EvidenceMapper()
        evidence_list = mapper.map_event_to_evidence(proof_record)
        # evidence_list contains ControlEvidence for every applicable control

    The mapper is stateless — all mapping logic is declarative in EVIDENCE_MAP.
    """

    def __init__(self) -> None:
        self._evidence_map = EVIDENCE_MAP

    @property
    def supported_event_types(self) -> list[str]:
        """Return all event types that have evidence mappings."""
        return list(self._evidence_map.keys())

    @property
    def supported_frameworks(self) -> list[str]:
        """Return all frameworks covered by the evidence map."""
        frameworks: set[str] = set()
        for event_rules in self._evidence_map.values():
            frameworks.update(event_rules.keys())
        return sorted(frameworks)

    def map_event_to_evidence(
        self,
        proof_record: ProofRecord,
        *,
        frameworks: Optional[list[str]] = None,
    ) -> list[ControlEvidence]:
        """
        Given a proof record, generate all compliance evidence records.

        Args:
            proof_record: The proof chain event to map.
            frameworks: Optional filter — only generate evidence for
                these frameworks. If None, generates for all.

        Returns:
            List of ControlEvidence records, one per applicable control
            mapping.
        """
        event_type = proof_record.action_type
        event_rules = self._evidence_map.get(event_type)

        if not event_rules:
            logger.debug(
                "no_evidence_mapping",
                extra={"action_type": event_type, "proof_id": proof_record.proof_id},
            )
            return []

        evidence_records: list[ControlEvidence] = []

        for framework, rules in event_rules.items():
            if frameworks and framework not in frameworks:
                continue

            for rule in rules:
                evidence = ControlEvidence(
                    proof_id=proof_record.proof_id,
                    control_id=rule["control"],
                    framework=framework,
                    evidence_type=rule["type"],
                    evidence_category=rule["category"],
                    description=rule["desc"],
                    compliance_status=rule["status"],
                    collected_at=proof_record.created_at,
                    retention_expires=_retention_expiry(framework),
                    metadata={
                        "intent_id": proof_record.intent_id,
                        "verdict_id": proof_record.verdict_id,
                        "entity_id": proof_record.entity_id,
                        "decision": proof_record.decision,
                        "chain_position": proof_record.chain_position,
                    },
                )
                evidence_records.append(evidence)

        logger.info(
            "evidence_mapped",
            extra={
                "proof_id": proof_record.proof_id,
                "action_type": event_type,
                "evidence_count": len(evidence_records),
            },
        )
        return evidence_records

    def get_control_mappings(
        self,
        proof_record: ProofRecord,
        *,
        frameworks: Optional[list[str]] = None,
    ) -> list[ControlMapping]:
        """
        Generate ControlMapping objects for a proof record.

        Lighter than full ControlEvidence — used when enriching
        proof records into EvidenceChainEvent objects.

        Args:
            proof_record: The proof chain event.
            frameworks: Optional framework filter.

        Returns:
            List of ControlMapping objects.
        """
        event_type = proof_record.action_type
        event_rules = self._evidence_map.get(event_type, {})

        mappings: list[ControlMapping] = []
        for framework, rules in event_rules.items():
            if frameworks and framework not in frameworks:
                continue

            for rule in rules:
                # Map compliance_status to satisfaction_level
                status = rule["status"]
                if status == "satisfies":
                    satisfaction = "full"
                elif status == "partially_satisfies":
                    satisfaction = "partial"
                else:
                    satisfaction = "supporting"

                mappings.append(
                    ControlMapping(
                        control_id=rule["control"],
                        framework=framework,
                        evidence_type=rule["type"],
                        satisfaction_level=satisfaction,
                    )
                )
        return mappings

    def compute_control_health(
        self,
        control_id: str,
        framework: str,
        evidence: list[ControlEvidence],
    ) -> ControlHealthStatus:
        """
        Compute health status from a set of evidence records.

        This is a pure-computation method (no DB access). It analyzes
        the provided evidence list and determines the control status.

        Logic:
        - No evidence -> unknown
        - All evidence "satisfies" -> compliant
        - Any evidence "partially_satisfies" -> degraded
        - Only "supports" evidence -> degraded
        - No recent evidence (>24h) -> non_compliant

        Args:
            control_id: Control identifier.
            framework: Framework identifier.
            evidence: List of evidence records to analyze.

        Returns:
            ControlHealthStatus for the control.
        """
        if not evidence:
            return ControlHealthStatus(
                control_id=control_id,
                framework=framework,
                status="unknown",
                evidence_count=0,
                issues=["No evidence recorded for this control"],
                remediation="Ensure proof chain events map to this control",
            )

        # Sort by collection time, most recent first
        sorted_evidence = sorted(
            evidence, key=lambda e: e.collected_at, reverse=True
        )

        latest = sorted_evidence[0]
        now = datetime.utcnow()
        hours_since_latest = (now - latest.collected_at).total_seconds() / 3600

        issues: list[str] = []
        remediation: Optional[str] = None

        # Staleness check
        if hours_since_latest > 24:
            status = "non_compliant"
            issues.append(
                f"No evidence collected in {hours_since_latest:.0f} hours"
            )
            remediation = (
                "Investigate whether proof events are being generated "
                "for actions related to this control"
            )
        elif latest.compliance_status == "satisfies":
            status = "compliant"
        elif latest.compliance_status == "partially_satisfies":
            status = "degraded"
            issues.append("Latest evidence only partially satisfies the control")
            remediation = (
                "Review partial satisfaction and determine if "
                "additional controls are needed"
            )
        else:
            status = "degraded"
            issues.append("Latest evidence provides only supporting evidence")
            remediation = "Additional primary evidence may be required"

        return ControlHealthStatus(
            control_id=control_id,
            framework=framework,
            status=status,
            last_evidence_at=latest.collected_at,
            evidence_count=len(evidence),
            issues=issues,
            remediation=remediation,
        )

    def get_framework_coverage(self, framework: str) -> dict:
        """
        Return the set of controls covered by evidence mappings
        for a specific framework.

        Args:
            framework: Framework identifier.

        Returns:
            Dictionary with control IDs mapped to the event types
            that provide evidence for them.
        """
        coverage: dict[str, list[str]] = {}
        for event_type, fw_rules in self._evidence_map.items():
            rules = fw_rules.get(framework, [])
            for rule in rules:
                ctrl = rule["control"]
                if ctrl not in coverage:
                    coverage[ctrl] = []
                coverage[ctrl].append(event_type)
        return coverage

    def get_total_mapping_count(self) -> int:
        """Return total number of evidence mapping rules across all events and frameworks."""
        count = 0
        for fw_rules in self._evidence_map.values():
            for rules in fw_rules.values():
                count += len(rules)
        return count
