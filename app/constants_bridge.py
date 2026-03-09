# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Cognigate Constants Bridge

Python mirror of @vorionsys/shared-constants — single source of truth for
the entire Vorion ecosystem.

Translates 7 TypeScript constant modules into Python dictionaries:
- Tiers (8-tier trust model, T0-T7)
- Capabilities (24 capability definitions)
- Error Codes (35+ standardized error codes)
- Rate Limits & Quotas (per-tier API limits)
- API Versions (all service version registries)
- Products (product catalog)
- Domains (domain registry)
"""

from __future__ import annotations

from enum import IntEnum, Enum
from typing import Any


# =============================================================================
# TRUST TIERS
# =============================================================================

class TrustTier(IntEnum):
    T0_SANDBOX = 0
    T1_OBSERVED = 1
    T2_PROVISIONAL = 2
    T3_MONITORED = 3
    T4_STANDARD = 4
    T5_TRUSTED = 5
    T6_CERTIFIED = 6
    T7_AUTONOMOUS = 7


TIER_THRESHOLDS: dict[int, dict[str, Any]] = {
    TrustTier.T0_SANDBOX: {
        "min": 0,
        "max": 199,
        "name": "Sandbox",
        "description": "Isolated, no external access, observation only",
        "color": "#78716c",
        "textColor": "#ffffff",
    },
    TrustTier.T1_OBSERVED: {
        "min": 200,
        "max": 349,
        "name": "Observed",
        "description": "Read-only, sandboxed execution, monitored",
        "color": "#ef4444",
        "textColor": "#ffffff",
    },
    TrustTier.T2_PROVISIONAL: {
        "min": 350,
        "max": 499,
        "name": "Provisional",
        "description": "Basic operations, heavy supervision",
        "color": "#f97316",
        "textColor": "#ffffff",
    },
    TrustTier.T3_MONITORED: {
        "min": 500,
        "max": 649,
        "name": "Monitored",
        "description": "Standard operations with continuous monitoring",
        "color": "#eab308",
        "textColor": "#000000",
    },
    TrustTier.T4_STANDARD: {
        "min": 650,
        "max": 799,
        "name": "Standard",
        "description": "External API access, policy-governed",
        "color": "#22c55e",
        "textColor": "#ffffff",
    },
    TrustTier.T5_TRUSTED: {
        "min": 800,
        "max": 875,
        "name": "Trusted",
        "description": "Cross-agent communication, delegated tasks",
        "color": "#3b82f6",
        "textColor": "#ffffff",
    },
    TrustTier.T6_CERTIFIED: {
        "min": 876,
        "max": 950,
        "name": "Certified",
        "description": "Admin tasks, agent spawning, minimal oversight",
        "color": "#8b5cf6",
        "textColor": "#ffffff",
    },
    TrustTier.T7_AUTONOMOUS: {
        "min": 951,
        "max": 1000,
        "name": "Autonomous",
        "description": "Full autonomy, self-governance, strategic only",
        "color": "#06b6d4",
        "textColor": "#ffffff",
    },
}


def score_to_tier(score: int) -> TrustTier:
    """Convert a trust score (0-1000) to a trust tier."""
    if score < 0 or score > 1000:
        raise ValueError(f"Trust score must be between 0 and 1000, got {score}")
    if score >= 951:
        return TrustTier.T7_AUTONOMOUS
    if score >= 876:
        return TrustTier.T6_CERTIFIED
    if score >= 800:
        return TrustTier.T5_TRUSTED
    if score >= 650:
        return TrustTier.T4_STANDARD
    if score >= 500:
        return TrustTier.T3_MONITORED
    if score >= 350:
        return TrustTier.T2_PROVISIONAL
    if score >= 200:
        return TrustTier.T1_OBSERVED
    return TrustTier.T0_SANDBOX


# =============================================================================
# CAPABILITIES
# =============================================================================

class CapabilityCategory(str, Enum):
    DATA_ACCESS = "data_access"
    API_ACCESS = "api_access"
    CODE_EXECUTION = "code_execution"
    AGENT_INTERACTION = "agent_interaction"
    RESOURCE_MANAGEMENT = "resource_management"
    GOVERNANCE = "governance"
    ADMIN = "admin"


CAPABILITIES: list[dict[str, Any]] = [
    # T0 - Sandbox
    {
        "code": "CAP-READ-PUBLIC",
        "name": "Read Public Data",
        "category": CapabilityCategory.DATA_ACCESS,
        "description": "Access publicly available data",
        "unlockTier": TrustTier.T0_SANDBOX,
    },
    {
        "code": "CAP-GENERATE-TEXT",
        "name": "Generate Text",
        "category": CapabilityCategory.CODE_EXECUTION,
        "description": "Generate text responses",
        "unlockTier": TrustTier.T0_SANDBOX,
    },
    # T1 - Observed
    {
        "code": "CAP-READ-INTERNAL",
        "name": "Read Internal Data",
        "category": CapabilityCategory.DATA_ACCESS,
        "description": "Access internal data within allowed scopes",
        "unlockTier": TrustTier.T1_OBSERVED,
        "constraints": ["Read-only", "Logged"],
    },
    {
        "code": "CAP-INTERNAL-API",
        "name": "Internal API Access",
        "category": CapabilityCategory.API_ACCESS,
        "description": "Make read-only internal API calls",
        "unlockTier": TrustTier.T1_OBSERVED,
        "constraints": ["GET only", "Rate limited"],
    },
    # T2 - Provisional
    {
        "code": "CAP-FILE-WRITE",
        "name": "Write Files",
        "category": CapabilityCategory.DATA_ACCESS,
        "description": "Write to approved directories",
        "unlockTier": TrustTier.T2_PROVISIONAL,
        "constraints": ["Approved dirs only", "Size limited"],
    },
    {
        "code": "CAP-DB-READ",
        "name": "Database Read",
        "category": CapabilityCategory.DATA_ACCESS,
        "description": "Read from approved database tables",
        "unlockTier": TrustTier.T2_PROVISIONAL,
        "constraints": ["Approved tables", "Query timeout"],
    },
    {
        "code": "CAP-EXTERNAL-API-READ",
        "name": "External API Read",
        "category": CapabilityCategory.API_ACCESS,
        "description": "Make GET requests to approved external APIs",
        "unlockTier": TrustTier.T2_PROVISIONAL,
        "constraints": ["GET only", "Approved endpoints"],
    },
    # T3 - Monitored
    {
        "code": "CAP-DB-WRITE",
        "name": "Database Write",
        "category": CapabilityCategory.DATA_ACCESS,
        "description": "Write to approved database tables",
        "unlockTier": TrustTier.T3_MONITORED,
        "constraints": ["Approved tables", "Transaction limits"],
    },
    {
        "code": "CAP-EXTERNAL-API-FULL",
        "name": "External API Full Access",
        "category": CapabilityCategory.API_ACCESS,
        "description": "Full REST operations on approved external APIs",
        "unlockTier": TrustTier.T3_MONITORED,
        "constraints": ["Approved endpoints", "Rate limited"],
    },
    {
        "code": "CAP-CODE-SANDBOX",
        "name": "Sandboxed Code Execution",
        "category": CapabilityCategory.CODE_EXECUTION,
        "description": "Execute code in isolated sandbox",
        "unlockTier": TrustTier.T3_MONITORED,
        "constraints": ["Sandboxed", "Time limited", "No network"],
    },
    # T4 - Standard
    {
        "code": "CAP-AGENT-COMMUNICATE",
        "name": "Agent Communication",
        "category": CapabilityCategory.AGENT_INTERACTION,
        "description": "Send and receive messages to/from other agents",
        "unlockTier": TrustTier.T4_STANDARD,
        "constraints": ["Approved agents", "Message limits"],
    },
    {
        "code": "CAP-WORKFLOW-MULTI",
        "name": "Multi-Step Workflow",
        "category": CapabilityCategory.CODE_EXECUTION,
        "description": "Orchestrate multi-step workflows",
        "unlockTier": TrustTier.T4_STANDARD,
        "constraints": ["Approved patterns", "Checkpoints required"],
    },
    {
        "code": "CAP-ESCALATE-HUMAN",
        "name": "Human Escalation",
        "category": CapabilityCategory.GOVERNANCE,
        "description": "Initiate escalation to human reviewers",
        "unlockTier": TrustTier.T4_STANDARD,
    },
    # T5 - Trusted
    {
        "code": "CAP-AGENT-DELEGATE",
        "name": "Task Delegation",
        "category": CapabilityCategory.AGENT_INTERACTION,
        "description": "Delegate tasks to other agents",
        "unlockTier": TrustTier.T5_TRUSTED,
        "constraints": ["Trust verified agents"],
    },
    {
        "code": "CAP-RESOURCE-PROVISION",
        "name": "Resource Provisioning",
        "category": CapabilityCategory.RESOURCE_MANAGEMENT,
        "description": "Provision computational resources",
        "unlockTier": TrustTier.T5_TRUSTED,
        "constraints": ["Budget limits", "Approval required"],
    },
    # T6 - Certified
    {
        "code": "CAP-AGENT-SPAWN",
        "name": "Spawn Agents",
        "category": CapabilityCategory.AGENT_INTERACTION,
        "description": "Create new agent instances",
        "unlockTier": TrustTier.T6_CERTIFIED,
        "constraints": ["Template required", "Quota limited"],
    },
    {
        "code": "CAP-INFRA-MANAGE",
        "name": "Infrastructure Management",
        "category": CapabilityCategory.RESOURCE_MANAGEMENT,
        "description": "Manage infrastructure resources",
        "unlockTier": TrustTier.T6_CERTIFIED,
        "constraints": ["Approved resources"],
    },
    {
        "code": "CAP-POLICY-CREATE",
        "name": "Policy Creation",
        "category": CapabilityCategory.GOVERNANCE,
        "description": "Create governance policies",
        "unlockTier": TrustTier.T6_CERTIFIED,
        "constraints": ["Review required"],
    },
    # T7 - Autonomous
    {
        "code": "CAP-FULL-ADMIN",
        "name": "Full Administration",
        "category": CapabilityCategory.ADMIN,
        "description": "Full administrative access",
        "unlockTier": TrustTier.T7_AUTONOMOUS,
    },
    {
        "code": "CAP-SELF-MODIFY",
        "name": "Self-Modification",
        "category": CapabilityCategory.CODE_EXECUTION,
        "description": "Modify own configuration and behavior",
        "unlockTier": TrustTier.T7_AUTONOMOUS,
        "constraints": ["Ethical bounds", "Audit logged"],
    },
    {
        "code": "CAP-STRATEGIC-DECISION",
        "name": "Strategic Decisions",
        "category": CapabilityCategory.GOVERNANCE,
        "description": "Make strategic organizational decisions",
        "unlockTier": TrustTier.T7_AUTONOMOUS,
        "constraints": ["Human oversight available"],
    },
]


def get_capabilities_for_tier(tier: int) -> list[dict[str, Any]]:
    """Get capabilities available at a specific tier."""
    return [cap for cap in CAPABILITIES if cap["unlockTier"] <= tier]


def get_capability(code: str) -> dict[str, Any] | None:
    """Get capability by code."""
    return next((cap for cap in CAPABILITIES if cap["code"] == code), None)


# =============================================================================
# ERROR CODES
# =============================================================================

class ErrorCategory(str, Enum):
    AUTH = "auth"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    NOT_FOUND = "not_found"
    TRUST = "trust"
    SERVER = "server"
    EXTERNAL = "external"
    CONFIG = "config"


AUTH_ERRORS: dict[str, dict[str, Any]] = {
    "MISSING_API_KEY": {
        "code": "E1001",
        "httpStatus": 401,
        "category": ErrorCategory.AUTH,
        "message": "API key is missing. Include it in the Authorization header.",
        "retryable": False,
        "docsUrl": "https://cognigate.dev/docs/authentication",
    },
    "INVALID_API_KEY": {
        "code": "E1002",
        "httpStatus": 401,
        "category": ErrorCategory.AUTH,
        "message": "API key is invalid or has been revoked.",
        "retryable": False,
        "docsUrl": "https://cognigate.dev/docs/authentication",
    },
    "EXPIRED_API_KEY": {
        "code": "E1003",
        "httpStatus": 401,
        "category": ErrorCategory.AUTH,
        "message": "API key has expired. Generate a new key.",
        "retryable": False,
        "docsUrl": "https://cognigate.dev/docs/authentication",
    },
    "INSUFFICIENT_PERMISSIONS": {
        "code": "E1004",
        "httpStatus": 403,
        "category": ErrorCategory.AUTH,
        "message": "Insufficient permissions for this operation.",
        "retryable": False,
    },
    "AGENT_NOT_AUTHORIZED": {
        "code": "E1005",
        "httpStatus": 403,
        "category": ErrorCategory.AUTH,
        "message": "Agent is not authorized for this action.",
        "retryable": False,
    },
    "TOKEN_EXPIRED": {
        "code": "E1006",
        "httpStatus": 401,
        "category": ErrorCategory.AUTH,
        "message": "Authentication token has expired.",
        "retryable": False,
    },
    "MFA_REQUIRED": {
        "code": "E1007",
        "httpStatus": 403,
        "category": ErrorCategory.AUTH,
        "message": "Multi-factor authentication is required for this operation.",
        "retryable": False,
    },
}

VALIDATION_ERRORS: dict[str, dict[str, Any]] = {
    "INVALID_REQUEST": {
        "code": "E2001",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Request body is invalid or malformed.",
        "retryable": False,
    },
    "MISSING_REQUIRED_FIELD": {
        "code": "E2002",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Required field is missing: {field}",
        "retryable": False,
    },
    "INVALID_FIELD_TYPE": {
        "code": "E2003",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Field {field} has invalid type. Expected {expected}.",
        "retryable": False,
    },
    "INVALID_FIELD_VALUE": {
        "code": "E2004",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Field {field} has invalid value.",
        "retryable": False,
    },
    "PAYLOAD_TOO_LARGE": {
        "code": "E2005",
        "httpStatus": 413,
        "category": ErrorCategory.VALIDATION,
        "message": "Request payload exceeds maximum size of {maxSize}.",
        "retryable": False,
    },
    "INVALID_JSON": {
        "code": "E2006",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Request body is not valid JSON.",
        "retryable": False,
    },
    "INVALID_CAR_ID": {
        "code": "E2007",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Invalid CAR ID format. Expected: car:domain/category/name:version",
        "retryable": False,
        "docsUrl": "https://carid.vorion.org/format",
    },
    "INVALID_TRUST_SCORE": {
        "code": "E2008",
        "httpStatus": 400,
        "category": ErrorCategory.VALIDATION,
        "message": "Trust score must be between 0 and 1000.",
        "retryable": False,
    },
}

RATE_LIMIT_ERRORS: dict[str, dict[str, Any]] = {
    "RATE_LIMIT_EXCEEDED": {
        "code": "E3001",
        "httpStatus": 429,
        "category": ErrorCategory.RATE_LIMIT,
        "message": "Rate limit exceeded. Retry after {retryAfter} seconds.",
        "retryable": True,
    },
    "QUOTA_EXCEEDED": {
        "code": "E3002",
        "httpStatus": 429,
        "category": ErrorCategory.RATE_LIMIT,
        "message": "Monthly quota exceeded. Upgrade your tier or wait for reset.",
        "retryable": False,
    },
    "CONCURRENT_LIMIT": {
        "code": "E3003",
        "httpStatus": 429,
        "category": ErrorCategory.RATE_LIMIT,
        "message": "Too many concurrent requests. Max burst: {burstLimit}.",
        "retryable": True,
    },
    "DAILY_LIMIT_EXCEEDED": {
        "code": "E3004",
        "httpStatus": 429,
        "category": ErrorCategory.RATE_LIMIT,
        "message": "Daily request limit exceeded. Resets at midnight UTC.",
        "retryable": True,
    },
}

NOT_FOUND_ERRORS: dict[str, dict[str, Any]] = {
    "RESOURCE_NOT_FOUND": {
        "code": "E4001",
        "httpStatus": 404,
        "category": ErrorCategory.NOT_FOUND,
        "message": "Resource not found: {resourceType}/{resourceId}",
        "retryable": False,
    },
    "AGENT_NOT_FOUND": {
        "code": "E4002",
        "httpStatus": 404,
        "category": ErrorCategory.NOT_FOUND,
        "message": "Agent not found: {agentId}",
        "retryable": False,
    },
    "PROOF_NOT_FOUND": {
        "code": "E4003",
        "httpStatus": 404,
        "category": ErrorCategory.NOT_FOUND,
        "message": "Proof not found: {proofId}",
        "retryable": False,
    },
    "ENDPOINT_NOT_FOUND": {
        "code": "E4004",
        "httpStatus": 404,
        "category": ErrorCategory.NOT_FOUND,
        "message": "API endpoint not found.",
        "retryable": False,
    },
    "ATTESTATION_NOT_FOUND": {
        "code": "E4005",
        "httpStatus": 404,
        "category": ErrorCategory.NOT_FOUND,
        "message": "Attestation not found: {attestationId}",
        "retryable": False,
    },
}

TRUST_ERRORS: dict[str, dict[str, Any]] = {
    "TRUST_TIER_INSUFFICIENT": {
        "code": "E5001",
        "httpStatus": 403,
        "category": ErrorCategory.TRUST,
        "message": "Trust tier {currentTier} insufficient. Required: {requiredTier}.",
        "retryable": False,
        "docsUrl": "https://basis.vorion.org/tiers",
    },
    "CAPABILITY_NOT_AVAILABLE": {
        "code": "E5002",
        "httpStatus": 403,
        "category": ErrorCategory.TRUST,
        "message": "Capability {capability} not available at tier {tier}.",
        "retryable": False,
        "docsUrl": "https://cognigate.dev/docs/capabilities",
    },
    "GOVERNANCE_DENIED": {
        "code": "E5003",
        "httpStatus": 403,
        "category": ErrorCategory.TRUST,
        "message": "Action denied by governance policy: {reason}.",
        "retryable": False,
    },
    "AGENT_SUSPENDED": {
        "code": "E5004",
        "httpStatus": 403,
        "category": ErrorCategory.TRUST,
        "message": "Agent is suspended. Contact support for reinstatement.",
        "retryable": False,
    },
    "PROOF_VERIFICATION_FAILED": {
        "code": "E5005",
        "httpStatus": 400,
        "category": ErrorCategory.TRUST,
        "message": "Proof verification failed: {reason}.",
        "retryable": False,
    },
    "ATTESTATION_INVALID": {
        "code": "E5006",
        "httpStatus": 400,
        "category": ErrorCategory.TRUST,
        "message": "Attestation is invalid or has expired.",
        "retryable": False,
    },
    "ESCALATION_REQUIRED": {
        "code": "E5007",
        "httpStatus": 403,
        "category": ErrorCategory.TRUST,
        "message": "Action requires human approval. Escalation ID: {escalationId}.",
        "retryable": False,
    },
}

SERVER_ERRORS: dict[str, dict[str, Any]] = {
    "INTERNAL_ERROR": {
        "code": "E6001",
        "httpStatus": 500,
        "category": ErrorCategory.SERVER,
        "message": "An internal error occurred. Please try again later.",
        "retryable": True,
    },
    "SERVICE_UNAVAILABLE": {
        "code": "E6002",
        "httpStatus": 503,
        "category": ErrorCategory.SERVER,
        "message": "Service is temporarily unavailable. Please try again later.",
        "retryable": True,
    },
    "DATABASE_ERROR": {
        "code": "E6003",
        "httpStatus": 500,
        "category": ErrorCategory.SERVER,
        "message": "Database operation failed. Please try again later.",
        "retryable": True,
    },
    "MAINTENANCE_MODE": {
        "code": "E6004",
        "httpStatus": 503,
        "category": ErrorCategory.SERVER,
        "message": "Service is under maintenance. Expected completion: {eta}.",
        "retryable": True,
    },
}

EXTERNAL_ERRORS: dict[str, dict[str, Any]] = {
    "BLOCKCHAIN_ERROR": {
        "code": "E7001",
        "httpStatus": 502,
        "category": ErrorCategory.EXTERNAL,
        "message": "Blockchain network error. Please try again later.",
        "retryable": True,
    },
    "UPSTREAM_TIMEOUT": {
        "code": "E7002",
        "httpStatus": 504,
        "category": ErrorCategory.EXTERNAL,
        "message": "Upstream service timed out.",
        "retryable": True,
    },
    "EXTERNAL_SERVICE_ERROR": {
        "code": "E7003",
        "httpStatus": 502,
        "category": ErrorCategory.EXTERNAL,
        "message": "External service error: {service}.",
        "retryable": True,
    },
}

ERROR_CODES: dict[str, dict[str, Any]] = {
    **AUTH_ERRORS,
    **VALIDATION_ERRORS,
    **RATE_LIMIT_ERRORS,
    **NOT_FOUND_ERRORS,
    **TRUST_ERRORS,
    **SERVER_ERRORS,
    **EXTERNAL_ERRORS,
}

ALL_ERROR_CODES: list[dict[str, Any]] = list(ERROR_CODES.values())


def get_error_by_code(code: str) -> dict[str, Any] | None:
    """Get error definition by error code (e.g. 'E1001')."""
    return next((e for e in ALL_ERROR_CODES if e["code"] == code), None)


def get_errors_by_category(category: str) -> list[dict[str, Any]]:
    """Get all errors in a category."""
    return [e for e in ALL_ERROR_CODES if e["category"] == category]


# =============================================================================
# RATE LIMITS
# =============================================================================

RATE_LIMITS: dict[int, dict[str, Any]] = {
    TrustTier.T0_SANDBOX: {
        "requestsPerSecond": 1,
        "requestsPerMinute": 10,
        "requestsPerHour": 100,
        "requestsPerDay": 500,
        "burstLimit": 2,
        "maxPayloadBytes": 10_240,
        "maxResponseBytes": 102_400,
        "connectionTimeoutMs": 5000,
        "requestTimeoutMs": 10_000,
    },
    TrustTier.T1_OBSERVED: {
        "requestsPerSecond": 2,
        "requestsPerMinute": 30,
        "requestsPerHour": 500,
        "requestsPerDay": 2000,
        "burstLimit": 5,
        "maxPayloadBytes": 51_200,
        "maxResponseBytes": 512_000,
        "connectionTimeoutMs": 5000,
        "requestTimeoutMs": 15_000,
    },
    TrustTier.T2_PROVISIONAL: {
        "requestsPerSecond": 5,
        "requestsPerMinute": 100,
        "requestsPerHour": 2000,
        "requestsPerDay": 10_000,
        "burstLimit": 10,
        "maxPayloadBytes": 102_400,
        "maxResponseBytes": 1_048_576,
        "connectionTimeoutMs": 10_000,
        "requestTimeoutMs": 30_000,
    },
    TrustTier.T3_MONITORED: {
        "requestsPerSecond": 10,
        "requestsPerMinute": 300,
        "requestsPerHour": 5000,
        "requestsPerDay": 50_000,
        "burstLimit": 20,
        "maxPayloadBytes": 512_000,
        "maxResponseBytes": 5_242_880,
        "connectionTimeoutMs": 10_000,
        "requestTimeoutMs": 60_000,
    },
    TrustTier.T4_STANDARD: {
        "requestsPerSecond": 20,
        "requestsPerMinute": 600,
        "requestsPerHour": 10_000,
        "requestsPerDay": 100_000,
        "burstLimit": 50,
        "maxPayloadBytes": 1_048_576,
        "maxResponseBytes": 10_485_760,
        "connectionTimeoutMs": 15_000,
        "requestTimeoutMs": 120_000,
    },
    TrustTier.T5_TRUSTED: {
        "requestsPerSecond": 50,
        "requestsPerMinute": 1500,
        "requestsPerHour": 30_000,
        "requestsPerDay": 300_000,
        "burstLimit": 100,
        "maxPayloadBytes": 5_242_880,
        "maxResponseBytes": 52_428_800,
        "connectionTimeoutMs": 30_000,
        "requestTimeoutMs": 300_000,
    },
    TrustTier.T6_CERTIFIED: {
        "requestsPerSecond": 100,
        "requestsPerMinute": 3000,
        "requestsPerHour": 100_000,
        "requestsPerDay": 1_000_000,
        "burstLimit": 200,
        "maxPayloadBytes": 10_485_760,
        "maxResponseBytes": 104_857_600,
        "connectionTimeoutMs": 60_000,
        "requestTimeoutMs": 600_000,
    },
    TrustTier.T7_AUTONOMOUS: {
        "requestsPerSecond": 500,
        "requestsPerMinute": 10_000,
        "requestsPerHour": 500_000,
        "requestsPerDay": 5_000_000,
        "burstLimit": 500,
        "maxPayloadBytes": 52_428_800,
        "maxResponseBytes": 524_288_000,
        "connectionTimeoutMs": 120_000,
        "requestTimeoutMs": 1_200_000,
    },
}

# =============================================================================
# TIER QUOTAS
# =============================================================================

TIER_QUOTAS: dict[int, dict[str, Any]] = {
    TrustTier.T0_SANDBOX: {
        "monthlyApiCalls": 1_000,
        "monthlyComputeUnits": 100,
        "monthlyStorageBytes": 10_485_760,
        "monthlyBandwidthBytes": 104_857_600,
        "maxAgents": 1,
        "maxWebhooks": 1,
        "maxTeamMembers": 1,
    },
    TrustTier.T1_OBSERVED: {
        "monthlyApiCalls": 10_000,
        "monthlyComputeUnits": 1_000,
        "monthlyStorageBytes": 104_857_600,
        "monthlyBandwidthBytes": 1_073_741_824,
        "maxAgents": 5,
        "maxWebhooks": 5,
        "maxTeamMembers": 3,
    },
    TrustTier.T2_PROVISIONAL: {
        "monthlyApiCalls": 50_000,
        "monthlyComputeUnits": 5_000,
        "monthlyStorageBytes": 524_288_000,
        "monthlyBandwidthBytes": 5_368_709_120,
        "maxAgents": 10,
        "maxWebhooks": 10,
        "maxTeamMembers": 5,
    },
    TrustTier.T3_MONITORED: {
        "monthlyApiCalls": 250_000,
        "monthlyComputeUnits": 25_000,
        "monthlyStorageBytes": 2_147_483_648,
        "monthlyBandwidthBytes": 26_843_545_600,
        "maxAgents": 50,
        "maxWebhooks": 25,
        "maxTeamMembers": 10,
    },
    TrustTier.T4_STANDARD: {
        "monthlyApiCalls": 1_000_000,
        "monthlyComputeUnits": 100_000,
        "monthlyStorageBytes": 10_737_418_240,
        "monthlyBandwidthBytes": 107_374_182_400,
        "maxAgents": 200,
        "maxWebhooks": 50,
        "maxTeamMembers": 25,
    },
    TrustTier.T5_TRUSTED: {
        "monthlyApiCalls": 5_000_000,
        "monthlyComputeUnits": 500_000,
        "monthlyStorageBytes": 53_687_091_200,
        "monthlyBandwidthBytes": 536_870_912_000,
        "maxAgents": 1_000,
        "maxWebhooks": 100,
        "maxTeamMembers": 50,
    },
    TrustTier.T6_CERTIFIED: {
        "monthlyApiCalls": 25_000_000,
        "monthlyComputeUnits": 2_500_000,
        "monthlyStorageBytes": 268_435_456_000,
        "monthlyBandwidthBytes": 2_684_354_560_000,
        "maxAgents": 5_000,
        "maxWebhooks": 250,
        "maxTeamMembers": 100,
    },
    TrustTier.T7_AUTONOMOUS: {
        "monthlyApiCalls": -1,
        "monthlyComputeUnits": -1,
        "monthlyStorageBytes": 1_099_511_627_776,
        "monthlyBandwidthBytes": 10_995_116_277_760,
        "maxAgents": -1,
        "maxWebhooks": -1,
        "maxTeamMembers": -1,
    },
}

# =============================================================================
# API VERSIONS
# =============================================================================

class VersionStatus(str, Enum):
    DEVELOPMENT = "development"
    PREVIEW = "preview"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


API_VERSIONS: dict[str, dict[str, Any]] = {
    "cognigate": {
        "v1": {
            "version": "v1",
            "fullVersion": "1.0.0",
            "releaseDate": "2026-02-01",
            "status": VersionStatus.STABLE,
            "changelogUrl": "https://cognigate.dev/changelog/v1",
        },
    },
    "trust": {
        "v1": {
            "version": "v1",
            "fullVersion": "1.0.0",
            "releaseDate": "2026-02-01",
            "status": VersionStatus.STABLE,
            "changelogUrl": "https://trust.vorion.org/changelog/v1",
        },
    },
    "logic": {
        "v1": {
            "version": "v1",
            "fullVersion": "1.0.0",
            "releaseDate": "2026-02-01",
            "status": VersionStatus.PREVIEW,
            "changelogUrl": "https://logic.vorion.org/changelog/v1",
        },
    },
    "basis": {
        "v1": {
            "version": "v1",
            "fullVersion": "1.0.0",
            "releaseDate": "2026-02-01",
            "status": VersionStatus.STABLE,
            "changelogUrl": "https://basis.vorion.org/changelog",
        },
    },
    "carSpec": {
        "v1": {
            "version": "v1",
            "fullVersion": "1.0.0",
            "releaseDate": "2026-02-01",
            "status": VersionStatus.STABLE,
            "changelogUrl": "https://carid.vorion.org/changelog",
        },
    },
}

CURRENT_VERSIONS: dict[str, str] = {
    "cognigate": "v1",
    "trust": "v1",
    "logic": "v1",
    "basis": "v1",
    "carSpec": "v1",
}

# =============================================================================
# PRODUCTS
# =============================================================================

class ProductCategory(str, Enum):
    OPEN_SOURCE = "open_source"
    COMMERCIAL = "commercial"
    DEVELOPER_TOOLS = "developer_tools"
    EDUCATION = "education"


class ProductStatus(str, Enum):
    DEVELOPMENT = "development"
    ALPHA = "alpha"
    BETA = "beta"
    GA = "ga"
    DEPRECATED = "deprecated"
    EOL = "eol"


VORION_PRODUCTS: dict[str, dict[str, Any]] = {
    "basis": {
        "id": "basis",
        "name": "BASIS",
        "description": "Blockchain Agent Safety & Identity Standard - Open framework for AI agent governance",
        "category": ProductCategory.OPEN_SOURCE,
        "status": ProductStatus.GA,
        "url": "https://basis.vorion.org",
        "docsUrl": "https://basis.vorion.org/docs",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/packages/basis",
        "npmPackage": "@vorionsys/basis",
        "organization": "vorion",
        "version": "1.0.0",
    },
    "carId": {
        "id": "car-id",
        "name": "CAR ID",
        "description": "Categorical Agent Registry - Universal agent identification system",
        "category": ProductCategory.OPEN_SOURCE,
        "status": ProductStatus.GA,
        "url": "https://carid.vorion.org",
        "docsUrl": "https://carid.vorion.org/docs",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/packages/car-spec",
        "npmPackage": "@vorionsys/car-spec",
        "organization": "vorion",
        "version": "1.0.0",
    },
    "atsf": {
        "id": "atsf",
        "name": "ATSF",
        "description": "Agent Trust & Safety Framework - Comprehensive safety evaluation system",
        "category": ProductCategory.OPEN_SOURCE,
        "status": ProductStatus.BETA,
        "url": "https://atsf.vorion.org",
        "docsUrl": "https://atsf.vorion.org/docs",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/packages/atsf-core",
        "npmPackage": "@vorionsys/atsf-core",
        "organization": "vorion",
        "version": "0.9.0",
    },
    "kaizen": {
        "id": "kaizen",
        "name": "Kaizen",
        "description": "Interactive AI Learning Experience - Educational platform for agentic AI",
        "category": ProductCategory.EDUCATION,
        "status": ProductStatus.BETA,
        "url": "https://learn.vorion.org",
        "docsUrl": "https://learn.vorion.org/docs",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/kaizen",
        "organization": "vorion",
    },
    "kaizenStudio": {
        "id": "kaizen-studio",
        "name": "Kaizen Studio",
        "description": "Interactive AI learning studio - hands-on agentic AI experiments",
        "category": ProductCategory.EDUCATION,
        "status": ProductStatus.BETA,
        "url": "https://kaizen.vorion.org",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/kaizen",
        "organization": "vorion",
    },
    "proofPlane": {
        "id": "proof-plane",
        "name": "Proof Plane",
        "description": "Cryptographic proof layer for agent attestations and verifiable execution",
        "category": ProductCategory.OPEN_SOURCE,
        "status": ProductStatus.BETA,
        "url": "https://vorion.org/proof-plane",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/packages/proof-plane",
        "npmPackage": "@vorionsys/proof-plane",
        "organization": "vorion",
        "version": "0.5.0",
    },
    "contracts": {
        "id": "contracts",
        "name": "Vorion Contracts",
        "description": "Smart contracts for on-chain agent governance and attestations",
        "category": ProductCategory.OPEN_SOURCE,
        "status": ProductStatus.BETA,
        "url": "https://vorion.org/contracts",
        "repoUrl": "https://github.com/vorionsys/vorion/tree/main/packages/contracts",
        "npmPackage": "@vorionsys/contracts",
        "organization": "vorion",
    },
}

VORION_COMMERCIAL_PRODUCTS: dict[str, dict[str, Any]] = {
    "cognigate": {
        "id": "cognigate",
        "name": "Cognigate",
        "description": "AI Governance API - Reference implementation of BASIS runtime",
        "category": ProductCategory.COMMERCIAL,
        "status": ProductStatus.GA,
        "url": "https://cognigate.dev",
        "docsUrl": "https://cognigate.dev/docs",
        "npmPackage": "@vorionsys/cognigate",
        "organization": "vorion",
        "version": "1.0.0",
    },
    "trust": {
        "id": "trust",
        "name": "Vorion Trust",
        "description": "Trust verification and certification platform for AI agents",
        "category": ProductCategory.COMMERCIAL,
        "status": ProductStatus.GA,
        "url": "https://trust.vorion.org",
        "docsUrl": "https://trust.vorion.org/docs",
        "organization": "vorion",
    },
    "logic": {
        "id": "logic",
        "name": "Vorion Logic",
        "description": "Policy engine and governance logic for enterprise AI",
        "category": ProductCategory.COMMERCIAL,
        "status": ProductStatus.BETA,
        "url": "https://logic.vorion.org",
        "docsUrl": "https://logic.vorion.org/docs",
        "organization": "vorion",
    },
    "platform": {
        "id": "platform",
        "name": "Vorion Platform",
        "description": "Enterprise AI governance dashboard and management console",
        "category": ProductCategory.COMMERCIAL,
        "status": ProductStatus.GA,
        "url": "https://vorion.org",
        "docsUrl": "https://vorion.org/docs",
        "organization": "vorion",
    },
}

ALL_PRODUCTS: dict[str, dict[str, dict[str, Any]]] = {
    "vorion": VORION_PRODUCTS,
    "vorionCommercial": VORION_COMMERCIAL_PRODUCTS,
}

# =============================================================================
# DOMAINS
# =============================================================================

VORION_DOMAINS: dict[str, str] = {
    "main": "https://vorion.org",
    "basis": "https://basis.vorion.org",
    "carId": "https://carid.vorion.org",
    "atsf": "https://atsf.vorion.org",
    "learn": "https://learn.vorion.org",
    "kaizen": "https://kaizen.vorion.org",
    "docs": "https://docs.vorion.org",
    "community": "https://community.vorion.org",
}

VORION_COMMERCIAL_DOMAINS: dict[str, str] = {
    "main": "https://vorion.org",
    "trust": "https://trust.vorion.org",
    "logic": "https://logic.vorion.org",
    "status": "https://status.vorion.org",
}

COGNIGATE_DOMAINS: dict[str, str] = {
    "main": "https://cognigate.dev",
    "docs": "https://cognigate.dev/docs",
}

API_ENDPOINTS: dict[str, dict[str, str]] = {
    "cognigate": {
        "production": "https://cognigate.dev/v1",
        "staging": "https://staging.cognigate.dev/v1",
    },
    "vorionApi": {
        "production": "https://api.vorion.org/v1",
        "staging": "https://staging-api.vorion.org/v1",
        "sandbox": "https://sandbox.vorion.org/v1",
    },
    "trust": {
        "production": "https://trust.vorion.org/v1",
        "staging": "https://staging.trust.vorion.org/v1",
    },
    "logic": {
        "production": "https://logic.vorion.org/v1",
        "staging": "https://staging.logic.vorion.org/v1",
    },
}

GITHUB: dict[str, dict[str, str]] = {
    "vorion": {
        "org": "https://github.com/vorionsys",
        "mainRepo": "https://github.com/vorionsys/vorion",
    },
    "vorionSys": {
        "org": "https://github.com/vorionsys",
    },
}

NPM_PACKAGES: dict[str, dict[str, str]] = {
    "vorion": {
        "basis": "@vorionsys/basis",
        "contracts": "@vorionsys/contracts",
        "carSpec": "@vorionsys/car-spec",
        "atsfCore": "@vorionsys/atsf-core",
        "cognigate": "@vorionsys/cognigate",
        "sharedConstants": "@vorionsys/shared-constants",
    },
    "vorionSys": {
        "sdk": "@vorionsys/sdk",
        "trust": "@vorionsys/trust",
        "logic": "@vorionsys/logic",
    },
}

ALL_DOMAINS: dict[str, Any] = {
    "vorion": VORION_DOMAINS,
    "vorionCommercial": VORION_COMMERCIAL_DOMAINS,
    "cognigate": COGNIGATE_DOMAINS,
    "api": API_ENDPOINTS,
    "github": GITHUB,
    "npm": NPM_PACKAGES,
}
