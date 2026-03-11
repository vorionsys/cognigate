# Cognigate Engine — CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-09

### Added
- **INTENT endpoint** — Normalizes raw goals into structured, risk-assessed plans (`POST /v1/intent`)
- **ENFORCE endpoint** — Validates plans against 24+ capability gates with trust-tier gating (`POST /v1/enforce`)
- **PROOF endpoint** — Creates SHA-256 hash-chain audit trails (`POST /v1/proof`)
- **Trust tiers T0–T7** — Full 8-tier enforcement with ATSF scoring and tier-scaled failure multipliers (T0=2x…T7=10x)
- **TRIPWIRE checks** — Deterministic pre-reasoning safety patterns for attack detection
- **AI Critic pattern** — Multi-provider critic (Anthropic, OpenAI, Google, xAI) with prompt injection defense
- **Policy engine** — BASIS-aligned constraint evaluation with configurable rigor modes
- **Circuit breaker** — Production-grade circuit breaker with half-open recovery
- **Velocity limiting** — Per-entity rate limiting with sliding window
- **Compliance evidence mapping** — 13 frameworks: NIST SP 800-53, SOC 2, PCI-DSS, FedRAMP, ISO 27001, GDPR, EU AI Act, HIPAA, CCPA, CSA STAR, CIS Controls, OWASP ASVS, NIST CSF
- **Cryptographic signatures** — Ed25519 digital signatures on proof records
- **Agent registry** — Register, list, update, and revoke agents via CRUD API
- **Admin endpoints** — 13 admin endpoints for system management
- **Reference data API** — Trust tiers, capabilities, errors, rate limits, versions, products, domains
- **Gateway proxy** — Proxy to upstream Vorion platform with timeout handling
- **Developer tools** — Calculator, error explorer, SDK reference, playground at `/tools/*`
- **Database support** — SQLAlchemy async with PostgreSQL (asyncpg) and SQLite (aiosqlite) backends
- **Alembic migrations** — Schema migration support with initial migration
- **Redis caching** — Optional Redis caching with graceful degradation to in-memory
- **Swagger/ReDoc docs** — Auto-generated API documentation at `/docs` and `/redoc`
- **CI pipeline** — Tests, lint (ruff), type check (mypy), security scanning (pip-audit, bandit)
- **692 tests** — Property-based (Hypothesis), adversarial, chaos, compliance, regression, invariant, and integration tests
- **85% minimum coverage** enforced in CI
- **SPDX headers** — Apache-2.0 SPDX license identifiers on all 88 Python source files
- **Open source governance** — CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, issue/PR templates

### Infrastructure
- **Dockerfile** — Multi-stage production build with non-root user, health check
- **docker-compose.yml** — Full local dev stack (API + PostgreSQL 16 + Redis 7)
- **Vercel deployment** — `api/index.py` entry point for serverless deployment

### Standards Alignment
- NIST SP 800-53 — 52 controls implemented
- SOC 2 Type II — Control mapping complete
- PCI-DSS — 32 controls mapped
- FedRAMP — 35 controls mapped
- ISO 27001, GDPR, EU AI Act — Framework health checks passing

---

_Built with BASIS · [cognigate.dev](https://cognigate.dev) · Apache-2.0_
