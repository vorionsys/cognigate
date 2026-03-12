# Cognigate

**Open enforcement runtime for the BASIS governance standard**

INTENT → ENFORCE → PROOF · Live at [cognigate.dev](https://cognigate.dev)

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com)
[![CI](https://github.com/vorionsys/cognigate/actions/workflows/ci.yml/badge.svg)](https://github.com/vorionsys/cognigate/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
![Stars](https://img.shields.io/github/stars/vorionsys/cognigate?style=social)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2?logo=discord&logoColor=white)](https://discord.gg/basis-protocol)

> **This is v0.1 — early, experimental, and explicitly not production-hardened.**
> We built it because we needed it ourselves and wanted to share it humbly with the community.

The Cognigate Engine implements the **BASIS** (Behavioral Agent Standard for Integrity and Safety) specification through three core governance layers:

| Layer | Purpose | Endpoint |
|-------|---------|----------|
| **INTENT** | Goal normalization & risk assessment | `POST /v1/intent` |
| **ENFORCE** | Policy validation & trust gating | `POST /v1/enforce` |
| **PROOF** | Immutable cryptographic audit ledger | `POST /v1/proof` |

## Why Cognigate?

LangChain, CrewAI, and AutoGen give you powerful agent orchestration.
Cognigate adds the missing open governance layer:

- **BASIS compliance enforcement** — deterministic pre-reasoning checks
- **Real-time ATSF trust tiers** (T0–T7) — capability gating by trust score
- **Cryptographic PROOF generation** — SHA-256 linked audit chain
- **Seamless wrapping** around any agent framework

We know this is early. Help us make it better.

## Quick Start

```bash
git clone https://github.com/vorionsys/cognigate.git
cd cognigate
pip install -e .
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs
```

## Live API

- **Production**: https://cognigate.dev
- **Swagger UI**: https://cognigate.dev/docs
- **ReDoc**: https://cognigate.dev/redoc
- **OpenAPI Schema**: https://cognigate.dev/openapi.json

## Documentation

- **[Full API Documentation](docs/API.md)** — Complete endpoint reference with examples
- **[BASIS Specification](https://github.com/vorionsys/vorion/blob/main/docs/BASIS.md)** — Governance standard

## Usage Example

```python
import httpx

async def check_intent(goal: str, entity_id: str):
    async with httpx.AsyncClient() as client:
        # 1. Normalize intent
        intent = await client.post("https://cognigate.dev/v1/intent", json={
            "entity_id": entity_id,
            "goal": goal,
        })

        # 2. Enforce policies
        verdict = await client.post("https://cognigate.dev/v1/enforce", json={
            "plan": intent.json()["plan"],
            "entity_id": entity_id,
            "trust_level": intent.json()["trust_level"],
            "trust_score": intent.json()["trust_score"],
        })

        return verdict.json()

# Returns: {"allowed": true, "action": "allow", ...}
```

## Trust Tiers (T0–T7)

Tier definitions are sourced from `@vorionsys/shared-constants` — canonical definitions for the Vorion ecosystem.

| Tier | Name | Score Range | Capabilities |
|------|------|-------------|--------------|
| T0 | Sandbox | 0–199 | Read-only, no external calls; all intents require approval |
| T1 | Observed | 200–349 | Basic tools, scoped data; enhanced logging active |
| T2 | Provisional | 350–499 | Standard tools, rate-limited; sensitive ops require review |
| T3 | Monitored | 500–649 | Full standard toolset; continuous monitoring |
| T4 | Standard | 650–799 | Extended tools + external APIs; green-light for most operations |
| T5 | Trusted | 800–875 | Cross-namespace access; elevated authority scope |
| T6 | Certified | 876–950 | Administrative operations; can approve others' intents |
| T7 | Autonomous | 951–1000 | Unrestricted within policy; self-governing |

Trust scores use **asymmetric dynamics**: failures apply a tier-scaled 7–10× penalty while positive signals provide smaller recovery bonuses. Idle agents decay to 50% at 182 days (182-day half-life). See [BASIS spec](https://github.com/vorionsys/vorion/blob/main/docs/BASIS.md) for full scoring model.

## Test Coverage

Cognigate's Python test suite covers compliance verification across 13 frameworks:

| Framework | Tests | Coverage |
|-----------|-------|---------|
| NIST SP 800-53 | 20 | 52 controls implemented |
| SOC 2 | 13 | Type II controls |
| PCI DSS | 32 | Controls mapped |
| FedRAMP | 35 | Controls mapped |
| ISO 27001, GDPR, EU AI Act, + 6 more | ~15 | Framework health checks |

**Total Python tests: 692** | Run: `pytest tests/`

## Vorion Ecosystem

| Component | Description |
|-----------|-------------|
| [**Vorion monorepo**](https://github.com/vorionsys/vorion) | Full governance stack (BASIS, ATSF, CAR, SDKs) |
| [@vorionsys/atsf-core](https://npmjs.com/package/@vorionsys/atsf-core) | TypeScript trust scoring SDK |
| [vorion.org](https://vorion.org) | Main site |
| [cognigate.dev](https://cognigate.dev) | Live runtime demo |

## Governance

- [Contributing](.github/CONTRIBUTING.md)
- [Security Policy](.github/SECURITY.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)

## The people behind Cognigate

Created by **Alex Blanc** and **Ryan Cason (Bo Xandar Lee)** — two former banquet servers who taught themselves to code with AI and wanted to give something back to the community.

[Read our full story →](https://vorion.org/about)

## Support

- **Documentation**: [cognigate.dev/docs](https://cognigate.dev/docs)
- **Issues**: [GitHub Issues](https://github.com/vorionsys/cognigate/issues)
- **Discord**: [Join the community](https://discord.gg/basis-protocol)
- **Email**: hello@vorion.org

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.

---

*Built with BASIS · [vorion.org](https://vorion.org) · Feedback welcome — even the brutal kind.*
