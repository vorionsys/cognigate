# Cognigate

**Open enforcement runtime for the BASIS governance standard**

INTENT → ENFORCE → PROOF · Live at [cognigate.dev](https://cognigate.dev)

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
![Stars](https://img.shields.io/github/stars/vorionsys/cognigate?style=social)

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

| Tier | Name | Score | Execution Path | Capabilities |
|------|------|-------|----------------|--------------|
| T0 | Untrusted | 0–199 | Full sandbox | Read-only, no external calls |
| T1 | Provisional | 200–399 | Restricted | Basic internal ops |
| T2 | Trusted | 400–599 | Standard | External APIs (rate-limited) |
| T3 | Verified | 600–799 | Elevated | PII, shell, limited write |
| T4 | Privileged | 800–899 | High-trust | Full tools with audit |
| T5 | Autonomous | 900–949 | Express path | Near-full autonomy |
| T6 | Council | 950–989 | Multi-agent oversight | Requires peer council |
| T7 | Sovereign | 990–1000 | Minimal gating | Full autonomy (with provable receipts) |

*These tier boundaries are our arbitrary starting point. Help us refine them.*

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

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.

---

*Built with BASIS · [vorion.org](https://vorion.org) · Feedback welcome — even the brutal kind.*
