# Cognigate Engine

> **VORION Governance Runtime for AI Agents**

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The Cognigate Engine implements the **BASIS** (Behavioral Agent Standard for Integrity and Safety) specification through three core governance layers:

| Layer | Purpose | Endpoint |
|-------|---------|----------|
| **INTENT** | Goal processing & risk assessment | `POST /v1/intent` |
| **ENFORCE** | Policy validation & gating | `POST /v1/enforce` |
| **PROOF** | Immutable audit ledger | `POST /v1/proof` |

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run locally
uvicorn app.main:app --reload

# API docs
open http://localhost:8000/docs
```

## Live API

- **Production**: https://cognigate.dev
- **Swagger UI**: https://cognigate.dev/docs
- **ReDoc**: https://cognigate.dev/redoc
- **OpenAPI Schema**: https://cognigate.dev/openapi.json

## Documentation

- **[Full API Documentation](docs/API.md)** - Complete endpoint reference with examples
- **[BASIS Specification](https://vorion.org/basis)** - Governance standard

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

## Trust Levels

| Level | Name | Score | Capabilities |
|-------|------|-------|--------------|
| 0 | Untrusted | 0-199 | Read-only, sandboxed |
| 1 | Provisional | 200-399 | Basic operations |
| 2 | Trusted | 400-599 | External APIs |
| 3 | Verified | 600-799 | PII access, shell |
| 4 | Privileged | 800-1000 | Full autonomy |

## Vorion Ecosystem

| Component | Description |
|-----------|-------------|
| [vorion.org](https://vorion.org) | AI Governance Infrastructure |
| [atsf-core](https://npmjs.com/package/@vorionsys/atsf-core) | TypeScript SDK |
| [Aurais](https://aurais.vorion.org) | Live Demo Platform |
| [Vorion](https://vorion.org) | Enterprise Platform |

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built with BASIS** - [vorion.org](https://vorion.org)
