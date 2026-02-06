"""
Cognigate Engine - Main FastAPI Application

The operational engine that enforces the BASIS standard for AI agent governance.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import enforce, intent, proof, health, reference, agents, trust, auth_keys, tools, gateway

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info(
        "cognigate_starting",
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    logger.info("cognigate_shutdown")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
## Cognigate Engine

The operational engine that enforces the **BASIS** standard for AI agent governance.

### Core Endpoints

- **INTENT** (`/v1/intent`) - Normalize and validate agent intentions
- **ENFORCE** (`/v1/enforce`) - Evaluate intentions against BASIS policies
- **PROOF** (`/v1/proof`) - Generate and verify cryptographic evidence

### Agent Management

- **Agents** (`/v1/agents`) - Register, list, update, and revoke agents
- **Trust** (`/v1/trust`) - Admit agents, record signals, query trust scores
- **Auth** (`/v1/auth/keys`) - Create and manage API keys

### Developer Tools

- **Trust Calculator** (`/tools/calculator`) - Interactive tier explorer
- **Error Codes** (`/tools/errors`) - Searchable error code reference
- **SDKs** (`/tools/sdks`) - Quickstart guides for all languages
- **Playground** (`/tools/playground`) - Full pipeline testing

### Reference Data

- **Tiers** (`/v1/reference/tiers`) - 8-tier trust model (T0-T7)
- **Capabilities** (`/v1/reference/capabilities`) - 24 capability definitions
- **Error Codes** (`/v1/reference/errors`) - 35+ standardized error codes
- **Rate Limits** (`/v1/reference/rate-limits`) - Per-tier API limits and quotas
- **Versions** (`/v1/reference/versions`) - API version registry
- **Products** (`/v1/reference/products`) - Ecosystem product catalog
- **Domains** (`/v1/reference/domains`) - Domain registry

### Gateway (Proxy to AgentAnchor)

- **Gateway Status** (`/v1/gateway/status`) - Connection health check
- **Gateway Proxy** (`/v1/gateway/{domain}/*`) - Forward to AgentAnchor API
  - Domains: compliance, council, observer, truth-chain, academy, orchestrator, webhooks, dashboard

### The Stack

```
BASIS sets the rules.
INTENT figures out the goal.
ENFORCE stops the bad stuff.
PROOF shows the receipts.
```

Powered by **VORION** - The Steward of Safe Autonomous Systems.
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(intent.router, prefix=settings.api_prefix, tags=["Intent"])
app.include_router(enforce.router, prefix=settings.api_prefix, tags=["Enforce"])
app.include_router(proof.router, prefix=settings.api_prefix, tags=["Proof"])
app.include_router(reference.router, prefix=settings.api_prefix, tags=["Reference Data"])
app.include_router(agents.router, prefix=settings.api_prefix, tags=["Agents"])
app.include_router(trust.router, prefix=settings.api_prefix, tags=["Trust"])
app.include_router(auth_keys.router, prefix=settings.api_prefix, tags=["Auth"])
app.include_router(tools.router)
app.include_router(gateway.router, prefix=settings.api_prefix, tags=["Gateway"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint - API status."""
    return {
        "service": "Cognigate Engine",
        "status": "BASIS_ACTIVE",
        "version": settings.app_version,
        "docs": "/docs",
    }
