# Cognigate API Documentation

> **Version**: 1.0
> **Base URL**: `https://cognigate.dev/v1`
> **OpenAPI**: `/openapi.json`
> **Interactive Docs**: `/docs` (Swagger UI) | `/redoc` (ReDoc)

Cognigate is the governance runtime engine for AI agents implementing the BASIS standard. It provides three core layers: **INTENT**, **ENFORCE**, and **PROOF**.

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Trust Levels](#trust-levels)
- [Rate Limits](#rate-limits)
- [Endpoints](#endpoints)
  - [INTENT - Goal Processing](#intent---goal-processing)
  - [ENFORCE - Policy Validation](#enforce---policy-validation)
  - [PROOF - Audit Ledger](#proof---audit-ledger)
  - [Health Check](#health-check)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)

---

## Overview

The Cognigate governance pipeline processes AI agent actions in three stages:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     INTENT      │───▶│     ENFORCE     │───▶│      PROOF      │
│  Normalize goal │    │ Validate policy │    │  Record audit   │
│  Assess risk    │    │ Gate execution  │    │  Chain integrity│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

1. **INTENT**: Receives a raw goal, normalizes it into a structured plan, identifies tools/data/endpoints needed, and calculates risk score
2. **ENFORCE**: Validates the plan against BASIS policies, returns verdict (allow/deny/escalate/modify)
3. **PROOF**: Creates cryptographically linked audit records for compliance and verification

---

## Authentication

Currently, Cognigate operates in **open mode** for development. Production deployments should implement:

- API key authentication via `X-API-Key` header
- JWT tokens for agent identity verification
- mTLS for service-to-service communication

```bash
# Future authentication header
curl -H "X-API-Key: your-api-key" https://cognigate.dev/v1/intent
```

---

## Trust Levels

Cognigate uses a canonical 8-tier trust system (T0-T7) mapped to trust scores (0-1000):

| Tier | Name | Score Range | Capabilities |
|------|------|-------------|--------------|
| T0 | Sandbox | 0-199 | Read-only, sandboxed execution |
| T1 | Observed | 200-349 | Read-only, monitored |
| T2 | Provisional | 350-499 | Basic operations, heavy supervision |
| T3 | Monitored | 500-649 | Standard operations, continuous monitoring |
| T4 | Standard | 650-799 | External API access, policy-governed |
| T5 | Trusted | 800-875 | Cross-agent communication, delegated tasks |
| T6 | Certified | 876-950 | Admin tasks, agent spawning, minimal oversight |
| T7 | Autonomous | 951-1000 | Full autonomy, self-governance |

---

## Rate Limits

| Tier | Requests/min | Burst |
|------|-------------|-------|
| Free | 60 | 10 |
| Pro | 600 | 100 |
| Enterprise | Unlimited | Unlimited |

Rate limit headers:
- `X-RateLimit-Limit`: Max requests per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp of window reset

---

## Endpoints

### INTENT - Goal Processing

Normalize agent goals into structured, policy-checkable plans.

#### `POST /v1/intent`

Normalize an intent into a structured plan.

**Request Body**

```json
{
  "entity_id": "agent_001",
  "goal": "Send email to user@example.com with quarterly report",
  "context": {
    "session_id": "sess_abc123",
    "origin": "slack_integration"
  },
  "metadata": {
    "priority": "normal"
  },
  "trust_level": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_id` | string | Yes | Unique identifier of the requesting agent |
| `goal` | string | Yes | The goal/prompt to process (1-4096 chars) |
| `context` | object | No | Additional context for intent processing |
| `metadata` | object | No | Request metadata |
| `trust_level` | integer | No | Override trust level (0-7) if authorized |

**Response** `200 OK`

```json
{
  "intent_id": "int_abc123def456",
  "entity_id": "agent_001",
  "status": "normalized",
  "plan": {
    "plan_id": "plan_xyz789",
    "goal": "Send email to user@example.com with quarterly report",
    "tools_required": ["email_send"],
    "endpoints_required": ["smtp.example.com"],
    "data_classifications": ["pii_email"],
    "risk_indicators": {
      "data_exposure": 0.3
    },
    "risk_score": 0.3,
    "reasoning_trace": "Simple email send operation with PII handling"
  },
  "trust_level": 2,
  "trust_score": 450,
  "created_at": "2026-01-16T12:00:00Z",
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `intent_id` | string | Unique intent identifier |
| `entity_id` | string | Requesting entity ID |
| `status` | string | `normalized` \| `error` |
| `plan` | object | Structured plan (see below) |
| `trust_level` | integer | Entity's trust level (0-7) |
| `trust_score` | integer | Entity's trust score (0-1000) |
| `created_at` | datetime | ISO 8601 timestamp |
| `error` | string | Error message if status is `error` |

**Structured Plan Object**

| Field | Type | Description |
|-------|------|-------------|
| `plan_id` | string | Unique plan identifier |
| `goal` | string | Interpreted goal |
| `tools_required` | string[] | Tools/APIs needed (e.g., `shell`, `file_write`, `email`) |
| `endpoints_required` | string[] | External endpoints to access |
| `data_classifications` | string[] | Data types (e.g., `pii_email`, `credentials`) |
| `risk_indicators` | object | Risk scores by category (0.0-1.0) |
| `risk_score` | number | Overall risk score (0.0-1.0) |
| `reasoning_trace` | string | Explanation of interpretation |

---

#### `GET /v1/intent/{intent_id}`

Retrieve a previously processed intent.

**Response** `200 OK` - Returns `IntentResponse`
**Response** `404 Not Found` - Intent not found

---

### ENFORCE - Policy Validation

Validate plans against BASIS policies and determine execution verdict.

#### `POST /v1/enforce`

Validate a plan against BASIS policies.

**Request Body**

```json
{
  "plan": {
    "plan_id": "plan_xyz789",
    "goal": "Delete all user records",
    "tools_required": ["database", "file_delete"],
    "endpoints_required": [],
    "data_classifications": ["pii_email", "credentials"],
    "risk_indicators": {
      "destructive_intent": 0.9
    },
    "risk_score": 0.9,
    "reasoning_trace": "High-risk deletion operation"
  },
  "policy_ids": [],
  "entity_id": "agent_001",
  "trust_level": 1,
  "trust_score": 250,
  "context": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `plan` | object | Yes | Structured plan from INTENT |
| `policy_ids` | string[] | No | Specific policies to check (empty = all) |
| `entity_id` | string | Yes | Requesting entity ID |
| `trust_level` | integer | Yes | Entity's current trust level (0-7) |
| `trust_score` | integer | Yes | Entity's current trust score (0-1000) |
| `context` | object | No | Additional enforcement context |

**Response** `200 OK`

```json
{
  "verdict_id": "vrd_abc123",
  "intent_id": "int_xyz789",
  "plan_id": "plan_xyz789",
  "allowed": false,
  "action": "deny",
  "violations": [
    {
      "policy_id": "basis-core-security",
      "constraint_id": "no-delete-without-approval",
      "severity": "high",
      "message": "File deletion requires human approval",
      "blocked": false,
      "remediation": "Request manager approval"
    },
    {
      "policy_id": "basis-risk-thresholds",
      "constraint_id": "high-risk-block",
      "severity": "critical",
      "message": "Risk score exceeds maximum threshold (0.8)",
      "blocked": true,
      "remediation": null
    }
  ],
  "policies_evaluated": ["basis-core-security", "basis-data-protection", "basis-risk-thresholds"],
  "constraints_evaluated": 6,
  "trust_impact": -50,
  "requires_approval": false,
  "approval_timeout": null,
  "modifications": null,
  "decided_at": "2026-01-16T12:00:00Z",
  "duration_ms": 12.5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `verdict_id` | string | Unique verdict identifier |
| `intent_id` | string | Associated intent ID |
| `plan_id` | string | Associated plan ID |
| `allowed` | boolean | Whether execution is permitted |
| `action` | string | `allow` \| `deny` \| `escalate` \| `modify` |
| `violations` | array | Policy violations found |
| `policies_evaluated` | string[] | Policies that were checked |
| `constraints_evaluated` | integer | Number of constraints evaluated |
| `trust_impact` | integer | Impact on entity's trust score |
| `requires_approval` | boolean | Whether human approval is required |
| `approval_timeout` | string | Timeout for approval (e.g., `4h`) |
| `modifications` | object | Required plan modifications (if action=`modify`) |
| `decided_at` | datetime | Decision timestamp |
| `duration_ms` | number | Processing time in milliseconds |

**Action Types**

| Action | Description |
|--------|-------------|
| `allow` | Plan may proceed |
| `deny` | Plan is blocked (critical violation) |
| `escalate` | Plan requires human approval |
| `modify` | Plan may proceed with modifications |

**Violation Severity**

| Severity | Behavior |
|----------|----------|
| `critical` | Blocks execution immediately |
| `high` | Requires human approval |
| `medium` | Logged, may proceed |
| `low` | Informational only |

---

#### `GET /v1/enforce/policies`

List available BASIS policies.

**Response** `200 OK`

```json
{
  "policies": [
    {
      "id": "basis-core-security",
      "name": "BASIS Core Security",
      "constraints": 2
    },
    {
      "id": "basis-data-protection",
      "name": "BASIS Data Protection",
      "constraints": 2
    },
    {
      "id": "basis-risk-thresholds",
      "name": "BASIS Risk Thresholds",
      "constraints": 2
    }
  ]
}
```

---

### PROOF - Audit Ledger

Create and query cryptographically sealed audit records.

#### `POST /v1/proof`

Create an immutable proof record from an enforcement verdict.

**Request Body**: `EnforceResponse` object from `/enforce`

**Response** `200 OK`

```json
{
  "proof_id": "prf_abc123def456",
  "chain_position": 42,
  "intent_id": "int_xyz789",
  "verdict_id": "vrd_abc123",
  "entity_id": "system",
  "action_type": "enforcement",
  "decision": "denied",
  "inputs_hash": "a3f2b8c9d4e5f6...",
  "outputs_hash": "b4c3d2e1f0a9...",
  "previous_hash": "c5d4e3f2a1b0...",
  "hash": "d6e5f4a3b2c1...",
  "signature": null,
  "created_at": "2026-01-16T12:00:00Z",
  "metadata": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `proof_id` | string | Unique proof identifier |
| `chain_position` | integer | Position in the proof chain |
| `intent_id` | string | Associated intent ID |
| `verdict_id` | string | Associated verdict ID |
| `entity_id` | string | Entity that requested the action |
| `action_type` | string | Type of action recorded |
| `decision` | string | `allowed` \| `denied` \| `escalated` \| `modified` |
| `inputs_hash` | string | SHA-256 hash of inputs |
| `outputs_hash` | string | SHA-256 hash of outputs |
| `previous_hash` | string | Hash of previous proof record |
| `hash` | string | Hash of this record |
| `signature` | string | Digital signature (optional) |
| `created_at` | datetime | Record creation timestamp |
| `metadata` | object | Additional metadata |

---

#### `GET /v1/proof/stats`

Get statistics about the proof ledger.

**Response** `200 OK`

```json
{
  "total_records": 1234,
  "chain_length": 1234,
  "last_record_at": "2026-01-16T12:00:00Z",
  "records_by_decision": {
    "allowed": 1100,
    "denied": 80,
    "escalated": 50,
    "modified": 4
  },
  "chain_integrity": true
}
```

---

#### `GET /v1/proof/{proof_id}`

Retrieve a proof record by ID.

**Response** `200 OK` - Returns `ProofRecord`
**Response** `404 Not Found` - Proof not found

---

#### `POST /v1/proof/query`

Query proof records with filters.

**Request Body**

```json
{
  "entity_id": "agent_001",
  "intent_id": null,
  "verdict_id": null,
  "decision": "denied",
  "start_date": "2026-01-01T00:00:00Z",
  "end_date": "2026-01-31T23:59:59Z",
  "limit": 100,
  "offset": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_id` | string | No | Filter by entity |
| `intent_id` | string | No | Filter by intent |
| `verdict_id` | string | No | Filter by verdict |
| `decision` | string | No | Filter by decision type |
| `start_date` | datetime | No | Filter from date |
| `end_date` | datetime | No | Filter to date |
| `limit` | integer | No | Max results (1-1000, default 100) |
| `offset` | integer | No | Pagination offset (default 0) |

**Response** `200 OK` - Returns `ProofRecord[]`

---

#### `GET /v1/proof/{proof_id}/verify`

Verify the integrity of a proof record and its chain linkage.

**Response** `200 OK`

```json
{
  "proof_id": "prf_abc123def456",
  "valid": true,
  "chain_valid": true,
  "signature_valid": null,
  "issues": [],
  "verified_at": "2026-01-16T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `valid` | boolean | Whether the record is valid overall |
| `chain_valid` | boolean | Whether chain linkage is intact |
| `signature_valid` | boolean | Whether signature is valid (if present) |
| `issues` | string[] | List of issues found |

---

### Health Check

#### `GET /health`

Check API health status.

**Response** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-16T12:00:00Z"
}
```

---

## Error Handling

All errors follow a consistent format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Status Code | Description |
|-------------|-------------|
| `400` | Bad Request - Invalid input |
| `401` | Unauthorized - Missing/invalid authentication |
| `403` | Forbidden - Insufficient permissions |
| `404` | Not Found - Resource doesn't exist |
| `422` | Validation Error - Request body validation failed |
| `429` | Too Many Requests - Rate limit exceeded |
| `500` | Internal Server Error |

**Validation Error Response**

```json
{
  "detail": [
    {
      "loc": ["body", "goal"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Code Examples

### Python

```python
import httpx

BASE_URL = "https://cognigate.dev/v1"

async def process_intent(goal: str, entity_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        # Step 1: Normalize intent
        intent_resp = await client.post(f"{BASE_URL}/intent", json={
            "entity_id": entity_id,
            "goal": goal,
        })
        intent = intent_resp.json()

        if intent["status"] != "normalized":
            raise Exception(f"Intent error: {intent['error']}")

        # Step 2: Enforce policies
        enforce_resp = await client.post(f"{BASE_URL}/enforce", json={
            "plan": intent["plan"],
            "entity_id": entity_id,
            "trust_level": intent["trust_level"],
            "trust_score": intent["trust_score"],
        })
        verdict = enforce_resp.json()

        # Step 3: Create proof record
        if verdict["action"] in ["allow", "deny"]:
            proof_resp = await client.post(f"{BASE_URL}/proof", json=verdict)
            proof = proof_resp.json()
            verdict["proof_id"] = proof["proof_id"]

        return verdict

# Usage
import asyncio
result = asyncio.run(process_intent(
    goal="Send quarterly report to finance@company.com",
    entity_id="agent_001"
))
print(f"Action: {result['action']}, Allowed: {result['allowed']}")
```

### TypeScript

```typescript
const BASE_URL = "https://cognigate.dev/v1";

interface IntentResponse {
  intent_id: string;
  status: string;
  plan: StructuredPlan;
  trust_level: number;
  trust_score: number;
  error?: string;
}

interface EnforceResponse {
  verdict_id: string;
  allowed: boolean;
  action: "allow" | "deny" | "escalate" | "modify";
  violations: PolicyViolation[];
}

async function processIntent(goal: string, entityId: string): Promise<EnforceResponse> {
  // Step 1: Normalize intent
  const intentRes = await fetch(`${BASE_URL}/intent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_id: entityId, goal }),
  });
  const intent: IntentResponse = await intentRes.json();

  if (intent.status !== "normalized") {
    throw new Error(`Intent error: ${intent.error}`);
  }

  // Step 2: Enforce policies
  const enforceRes = await fetch(`${BASE_URL}/enforce`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan: intent.plan,
      entity_id: entityId,
      trust_level: intent.trust_level,
      trust_score: intent.trust_score,
    }),
  });
  const verdict: EnforceResponse = await enforceRes.json();

  // Step 3: Create proof record
  if (verdict.action === "allow" || verdict.action === "deny") {
    await fetch(`${BASE_URL}/proof`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(verdict),
    });
  }

  return verdict;
}

// Usage
processIntent("Send quarterly report to finance@company.com", "agent_001")
  .then((result) => console.log(`Action: ${result.action}, Allowed: ${result.allowed}`));
```

### cURL

```bash
# 1. Normalize intent
curl -X POST https://cognigate.dev/v1/intent \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "agent_001",
    "goal": "Send email to user@example.com"
  }'

# 2. Enforce policies (use plan from step 1)
curl -X POST https://cognigate.dev/v1/enforce \
  -H "Content-Type: application/json" \
  -d '{
    "plan": { "plan_id": "plan_xyz", "goal": "...", ... },
    "entity_id": "agent_001",
    "trust_level": 2,
    "trust_score": 450
  }'

# 3. Query proof records
curl -X POST https://cognigate.dev/v1/proof/query \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "agent_001",
    "decision": "denied",
    "limit": 10
  }'

# 4. Verify proof integrity
curl https://cognigate.dev/v1/proof/prf_abc123/verify
```

---

## SDKs

Official SDKs available:

- **TypeScript/JavaScript**: `npm install @vorionsys/atsf-core`
- **Python**: Coming soon

---

## Support

- **Documentation**: https://vorion.org/docs
- **GitHub**: https://github.com/vorionsys/cognigate
- **Discord**: https://discord.gg/basis-protocol

---

*Last updated: 2026-01-16*
