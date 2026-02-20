# PROOF Ledger Evidence Schema

## Overview

The Evidence Schema extends Cognigate's immutable Proof Chain (PROOF = Persistent Record of Operational Facts) with automated compliance evidence generation. Every proof chain event is automatically mapped to the compliance controls it satisfies across seven governance frameworks.

This document covers:

1. How proof events map to control evidence
2. Chain verification process
3. Evidence retention policies per framework
4. Audit consumption guide
5. Framework-specific evidence requirements

---

## Architecture

```
ProofRecord (immutable)
    │
    ├── EvidenceHook.on_proof_created()
    │       │
    │       ├── EvidenceMapper.map_event_to_evidence()
    │       │       │
    │       │       └── EVIDENCE_MAP (declarative rules)
    │       │               │
    │       │               └── ControlEvidence records (per framework, per control)
    │       │
    │       └── EvidenceRepository.record_evidence_batch()
    │               │
    │               └── control_evidence table (immutable)
    │
    └── ControlHealthStatus (computed on demand)
            │
            └── ComplianceSnapshot (aggregated per framework)
```

Every proof chain event flows through this pipeline automatically. There are no batch jobs, no manual mappings, and no evidence gaps.

---

## Proof Event to Control Evidence Mapping

### Event Types

| Event Type | Description | Primary Evidence |
|---|---|---|
| `INTENT_RECEIVED` | Agent submits intent for governance evaluation | Risk assessment input, audit log |
| `DECISION_MADE` | Policy enforcement decision rendered | Access enforcement, attestation |
| `TRUST_DELTA` | Entity trust score changed | Risk metric, identity management |
| `EXECUTION_STARTED` | Action execution initiated | Audit log, execution tracking |
| `EXECUTION_COMPLETED` | Action completed successfully | Integrity attestation, audit record |
| `EXECUTION_FAILED` | Action execution failed | Incident response, failure log |
| `TRIPWIRE_TRIGGERED` | Deterministic security pattern matched | Intrusion detection, incident |
| `CIRCUIT_BREAKER_OPEN` | System-level safety halt activated | Incident response, safety attestation |
| `CIRCUIT_BREAKER_CLOSE` | Circuit recovery after safety halt | Recovery log, resilience evidence |
| `VELOCITY_EXCEEDED` | Rate limit violation detected | Access control, anomaly detection |
| `CRITIC_VERDICT` | AI-vs-AI adversarial evaluation result | Risk assessment, independent verification |

### Evidence Types

| Type | Description | Example |
|---|---|---|
| `log` | Timestamped event record | Intent submission logged |
| `metric` | Quantitative measurement | Trust score delta: +15 |
| `attestation` | Verifiable assertion of compliance | Policy decision: allowed with constraints |
| `configuration` | System configuration state | Active policy set hash verified |
| `test_result` | Validation test outcome | Chain integrity verification passed |

### Evidence Categories

| Category | Description |
|---|---|
| `access_control` | Identity, authentication, authorization decisions |
| `audit` | Event logging, record-keeping, traceability |
| `risk_assessment` | Risk identification, evaluation, treatment |
| `incident_response` | Security incidents, failures, recovery |
| `system_integrity` | Integrity verification, monitoring, protection |
| `transparency` | Explainability, disclosure, human oversight |
| `accountability` | Governance, responsibility, decision authority |
| `data_governance` | Data handling, processing lawfulness |
| `identity_management` | Entity identity, trust levels, credentials |
| `configuration_management` | System configuration tracking |

---

## Supported Frameworks

### NIST 800-53 Rev 5

Controls addressed by Cognigate evidence:

| Family | Controls | Evidence Sources |
|---|---|---|
| AC (Access Control) | AC-2, AC-3, AC-6, AC-17 | DECISION_MADE, TRUST_DELTA, VELOCITY_EXCEEDED |
| AU (Audit) | AU-2, AU-3, AU-6, AU-9, AU-12 | All event types generate audit evidence |
| CA (Assessment) | CA-7 | DECISION_MADE, TRUST_DELTA, CRITIC_VERDICT |
| CM (Configuration) | CM-3, CM-8 | EXECUTION_STARTED, EXECUTION_COMPLETED |
| IA (Identification) | IA-2, IA-5 | TRUST_DELTA |
| IR (Incident Response) | IR-4, IR-5, IR-6 | EXECUTION_FAILED, TRIPWIRE, CIRCUIT_BREAKER |
| RA (Risk Assessment) | RA-3, RA-5 | INTENT_RECEIVED, CRITIC_VERDICT |
| SC (System Protection) | SC-7, SC-13, SC-28 | TRIPWIRE, CIRCUIT_BREAKER, EXECUTION_COMPLETED |
| SI (System Integrity) | SI-4, SI-7 | All security events |

**Retention**: 7 years from evidence collection date.

### EU AI Act

| Article | Requirement | Evidence Sources |
|---|---|---|
| Article 9 | Risk management system | INTENT, DECISION, TRUST_DELTA, TRIPWIRE, CIRCUIT_BREAKER |
| Article 10 | Data governance | CRITIC_VERDICT |
| Article 11 | Technical documentation | DECISION_MADE |
| Article 12 | Record-keeping | All event types |
| Article 13 | Transparency | INTENT_RECEIVED, DECISION_MADE |
| Article 14 | Human oversight | DECISION_MADE, CIRCUIT_BREAKER_OPEN |
| Article 15 | Accuracy and robustness | EXECUTION_COMPLETED, TRIPWIRE, CRITIC_VERDICT |
| Article 17 | Quality management | EXECUTION_COMPLETED, EXECUTION_FAILED |
| Article 72 | Serious incidents | EXECUTION_FAILED, CIRCUIT_BREAKER_OPEN |

**Retention**: 10 years from evidence collection date.

### ISO/IEC 42001

| Clause | Area | Evidence Sources |
|---|---|---|
| A.5.2-A.5.4 | AI policy and responsibilities | DECISION_MADE, TRIPWIRE |
| A.6.1.2, A.6.1.4 | Risk and incident management | EXECUTION_FAILED, TRIPWIRE, CIRCUIT_BREAKER |
| A.6.2.2, A.6.2.4, A.6.2.6 | Risk treatment and monitoring | TRUST_DELTA, CRITIC_VERDICT, all execution events |
| A.7.2, A.7.3 | AI safety and lifecycle | CIRCUIT_BREAKER, VELOCITY, EXECUTION_COMPLETED |
| A.8.2, A.8.4 | Operations and documentation | EXECUTION_STARTED, INTENT_RECEIVED |
| A.9.2-A.9.4 | Performance and nonconformity | DECISION_MADE, TRUST_DELTA, EXECUTION_FAILED |
| A.10.2, A.10.3 | Monitoring and improvement | INTENT_RECEIVED, TRUST_DELTA, CIRCUIT_BREAKER_CLOSE |

**Retention**: 7 years from evidence collection date.

### SOC 2 Type II

| Criteria | Description | Evidence Sources |
|---|---|---|
| CC1.1-CC1.2 | Control environment | Governance configuration |
| CC2.1 | Information and communication | INTENT_RECEIVED |
| CC3.1-CC3.3 | Risk assessment | INTENT_RECEIVED, TRUST_DELTA, EXECUTION_FAILED |
| CC4.1-CC4.2 | Monitoring | TRUST_DELTA, CRITIC_VERDICT |
| CC5.1-CC5.3 | Control activities | DECISION_MADE, CIRCUIT_BREAKER |
| CC6.1-CC6.8 | Logical access and boundaries | DECISION_MADE, TRIPWIRE, VELOCITY |
| CC7.1-CC7.4 | System operations and incidents | EXECUTION events, TRIPWIRE, CIRCUIT_BREAKER |
| CC8.1 | Change management | EXECUTION_STARTED |
| CC9.1 | Risk mitigation | EXECUTION_COMPLETED, CIRCUIT_BREAKER_CLOSE |

**Retention**: 5 years from evidence collection date.

### NIST AI RMF 1.0

| Function | Sub-functions | Evidence Sources |
|---|---|---|
| GOVERN | 1.1, 1.2, 1.5, 4.1, 4.2 | DECISION_MADE, CIRCUIT_BREAKER, CRITIC_VERDICT |
| MAP | 1.1, 1.5, 1.6, 2.1-2.3, 3.5 | INTENT_RECEIVED, VELOCITY, TRIPWIRE, CRITIC_VERDICT |
| MEASURE | 1.1, 2.2, 2.5, 2.6, 2.11 | EXECUTION events, TRUST_DELTA, CRITIC_VERDICT |
| MANAGE | 1.1, 2.2, 2.4, 3.1, 4.1 | DECISION_MADE, EXECUTION_FAILED, CIRCUIT_BREAKER |

**Retention**: 7 years from evidence collection date.

### CMMC 2.0

| Domain | Practices | Evidence Sources |
|---|---|---|
| AC (Access Control) | L1-3.1.1, L1-3.1.2, L2-3.1.5, L2-3.1.7 | DECISION_MADE, VELOCITY |
| AU (Audit) | L2-3.3.1, L2-3.3.2 | All event types |
| IA (Identification) | L1-3.5.1, L1-3.5.2 | TRUST_DELTA |
| IR (Incident Response) | L2-3.6.1, L2-3.6.2 | EXECUTION_FAILED, TRIPWIRE, CIRCUIT_BREAKER |
| SC (System Protection) | L1-3.13.1, L2-3.13.11 | TRIPWIRE, CIRCUIT_BREAKER, EXECUTION_COMPLETED |
| SI (System Integrity) | L1-3.14.1, L2-3.14.6, L2-3.14.7 | TRIPWIRE, TRUST_DELTA, CRITIC_VERDICT |

**Retention**: 7 years from evidence collection date.

### GDPR

| Article | Requirement | Evidence Sources |
|---|---|---|
| Article 5 | Principles of processing | INTENT_RECEIVED, TRUST_DELTA, EXECUTION_COMPLETED |
| Article 6 | Lawfulness of processing | DECISION_MADE |
| Article 12-14 | Transparency and information | INTENT_RECEIVED |
| Article 22 | Automated decision-making | DECISION_MADE, CRITIC_VERDICT |
| Article 25 | Data protection by design | DECISION_MADE |
| Article 30 | Records of processing | INTENT_RECEIVED, EXECUTION events |
| Article 32 | Security of processing | EXECUTION_COMPLETED, TRIPWIRE, CIRCUIT_BREAKER, VELOCITY |
| Article 33 | Breach notification | EXECUTION_FAILED, TRIPWIRE, CIRCUIT_BREAKER |
| Article 35 | Impact assessment | TRUST_DELTA, CRITIC_VERDICT |

**Retention**: 6 years from evidence collection date.

---

## Chain Verification Process

### Proof Chain Integrity

The proof chain is an append-only hash-linked ledger. Each proof record contains:

```
┌─────────────────────────────────────────────────┐
│ ProofRecord                                     │
│   proof_id:       prf_a1b2c3d4e5f6              │
│   chain_position: 42                            │
│   previous_hash:  SHA-256(record at position 41)│
│   hash:           SHA-256(this record)          │
│   signature:      Ed25519(hash, private_key)    │
│   inputs_hash:    SHA-256(request payload)      │
│   outputs_hash:   SHA-256(response payload)     │
│   created_at:     2026-02-19T14:30:00Z          │
│   ...                                           │
└─────────────────────────────────────────────────┘
```

Verification steps:

1. **Genesis check**: Position 0 must have `previous_hash` = `"0" * 64`.
2. **Chain linkage**: Each record's `previous_hash` must equal the preceding record's `hash`.
3. **Position continuity**: `chain_position` must be strictly sequential with no gaps.
4. **Hash verification**: Recompute `hash` from record fields and compare.
5. **Signature verification** (optional): Verify Ed25519 signature against the configured public key.

### Evidence Chain Integrity

Evidence records inherit their integrity from the proof chain:

1. Every `ControlEvidence.proof_id` links to a verified `ProofRecord`.
2. Evidence records are immutable once written (append-only table).
3. The `retention_expires` field ensures evidence is preserved for the required duration.
4. Evidence timestamps are derived from the proof record's `created_at`, not generated independently.

### Verification API

```python
# Verify proof chain integrity
is_valid, issues = await proof_repository.verify_chain_integrity()

# Verify evidence for a specific control
evidence = await evidence_repository.get_control_evidence("AC-3", "NIST-800-53")
health = await evidence_repository.get_control_health("AC-3", "NIST-800-53")

# Generate compliance snapshot
snapshot = await evidence_repository.get_compliance_snapshot("NIST-800-53")
```

---

## Evidence Retention Policies

| Framework | Retention Period | Legal Basis |
|---|---|---|
| NIST 800-53 | 7 years | Federal records management requirements |
| EU AI Act | 10 years | Article 12(1): logs retained for period appropriate to intended purpose |
| ISO 42001 | 7 years | Clause 7.5: documented information retention |
| SOC 2 | 5 years | AICPA professional standards |
| NIST AI RMF | 7 years | Aligned with NIST 800-53 |
| CMMC | 7 years | DFARS 252.204-7012 retention requirements |
| GDPR | 6 years | Statute of limitations for data protection claims |

The `retention_expires` field on each `ControlEvidence` record is automatically calculated at creation time based on the framework's retention requirement. Evidence records **must not be deleted** before their retention expiry.

---

## Audit Consumption Guide

### For Compliance Auditors

#### 1. Request a Compliance Snapshot

Start with a point-in-time snapshot to understand overall compliance posture:

```python
snapshot = await evidence_repository.get_compliance_snapshot("NIST-800-53")

# snapshot.total_controls    -> 24
# snapshot.compliant         -> 20
# snapshot.non_compliant     -> 1
# snapshot.degraded          -> 2
# snapshot.unknown           -> 1
# snapshot.compliance_ratio  -> 0.833
```

#### 2. Drill into Specific Controls

For controls that are non-compliant or degraded, examine the evidence:

```python
health = await evidence_repository.get_control_health("AC-3", "NIST-800-53")

# health.status          -> "compliant"
# health.evidence_count  -> 1247
# health.last_evidence_at -> 2026-02-19T14:28:00Z
# health.issues          -> []
```

#### 3. Retrieve Evidence Chain for Audit Period

Pull the full evidence chain for a specific audit window:

```python
from datetime import datetime

evidence_chain = await evidence_repository.get_evidence_chain(
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 12, 31),
    framework="NIST-800-53",
)

# Returns chronologically ordered ControlEvidence records
# Each record links back to a specific ProofRecord via proof_id
```

#### 4. Verify Proof Chain Integrity

Confirm the underlying proof chain has not been tampered with:

```python
is_valid, issues = await proof_repository.verify_chain_integrity()

# is_valid -> True
# issues   -> []
```

#### 5. Trace a Specific Decision

Follow a single enforcement decision through the full evidence chain:

```python
# Get evidence for a specific proof record
evidence = await evidence_repository.get_evidence_by_proof("prf_a1b2c3d4e5f6")

# Each ControlEvidence record shows:
# - Which control it satisfies (control_id + framework)
# - What type of evidence it provides (evidence_type)
# - How fully it satisfies the control (compliance_status)
# - Human-readable description for the auditor
# - Metadata linking back to entity, intent, and verdict
```

### Evidence Record Format

Each `ControlEvidence` record contains:

| Field | Description | Example |
|---|---|---|
| `evidence_id` | Unique identifier | `evi_a1b2c3d4e5f6` |
| `proof_id` | Link to proof chain | `prf_x9y8z7w6v5u4` |
| `control_id` | Control identifier | `AC-3` |
| `framework` | Framework name | `NIST-800-53` |
| `evidence_type` | Evidence classification | `attestation` |
| `evidence_category` | Grouping category | `access_control` |
| `description` | Human-readable description | `Access enforcement: policy decision rendered` |
| `compliance_status` | Satisfaction level | `satisfies` |
| `collected_at` | Collection timestamp (UTC) | `2026-02-19T14:30:00Z` |
| `retention_expires` | Retention expiry date | `2033-02-19T14:30:00Z` |
| `metadata` | Additional context | `{"entity_id": "...", "decision": "allowed"}` |

### Compliance Status Definitions

| Status | Meaning |
|---|---|
| `satisfies` | This evidence fully satisfies the control requirement |
| `partially_satisfies` | This evidence addresses part of the control; additional evidence may be needed |
| `supports` | This evidence supports the control but does not directly satisfy it |

### Control Health Status Definitions

| Status | Meaning |
|---|---|
| `compliant` | Recent evidence fully satisfies the control |
| `non_compliant` | No evidence within the lookback window |
| `degraded` | Evidence exists but only partially satisfies the control |
| `unknown` | No evidence has ever been recorded for this control |

---

## EvidenceChainEvent Format

For external audit system consumption, proof records can be enriched into `EvidenceChainEvent` objects that combine proof chain fields with cryptographic context and control mappings:

```json
{
    "proof_id": "prf_a1b2c3d4e5f6",
    "chain_position": 42,
    "intent_id": "int_x1y2z3",
    "verdict_id": "vrd_a4b5c6",
    "entity_id": "agent_primary_001",
    "action_type": "DECISION_MADE",
    "decision": "allowed",
    "inputs_hash": "sha256:e3b0c44298fc...",
    "outputs_hash": "sha256:d7a8fbb307d7...",
    "execution_hash": "sha256:5e884898da28...",
    "policy_hash": "sha256:9f86d081884c...",
    "actor_identity": "ed25519:MCowBQYDK2VwAyEA...",
    "timestamp_utc": "2026-02-19T14:30:00Z",
    "previous_hash": "sha256:2cf24dba5fb0...",
    "hash": "sha256:e3b0c44298fc...",
    "signature": "ed25519:JHy2jPn4...",
    "control_mappings": [
        {
            "control_id": "AC-3",
            "framework": "NIST-800-53",
            "evidence_type": "attestation",
            "satisfaction_level": "full"
        },
        {
            "control_id": "Article-9",
            "framework": "EU-AI-ACT",
            "evidence_type": "attestation",
            "satisfaction_level": "full"
        }
    ]
}
```

This format provides a self-contained, cryptographically verifiable audit record that can be consumed by any external compliance platform without access to the Cognigate database.

---

## Integration Points

### Automatic Evidence Generation

Evidence is generated automatically via the `EvidenceHook`:

```python
# In the proof record creation flow:
proof_record = await proof_repository.create(record)
await evidence_hook.on_proof_created(proof_record, session)
```

The hook is designed to be non-blocking: if evidence generation fails, the error is logged but the proof record commit proceeds. Evidence generation never blocks the governance pipeline.

### Compliance Dashboard

Use `ComplianceSnapshot` to power compliance dashboards:

```python
# Generate snapshots for all frameworks
for framework in ["NIST-800-53", "EU-AI-ACT", "ISO-42001", "SOC-2"]:
    snapshot = await evidence_repository.get_compliance_snapshot(framework)
    # Feed to dashboard
```

### Evidence Export

For external audit platforms, use the evidence chain query:

```python
# Export evidence for audit period as JSON
evidence = await evidence_repository.get_evidence_chain(
    start_time=audit_start,
    end_time=audit_end,
    framework="NIST-800-53",
)
export = [e.model_dump(mode="json") for e in evidence]
```
