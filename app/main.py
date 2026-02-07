"""
Cognigate Engine - Main FastAPI Application

The operational engine that enforces the BASIS standard for AI agent governance.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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


@app.get("/status", include_in_schema=False)
async def status() -> dict[str, str]:
    """Programmatic status endpoint."""
    return {
        "service": "Cognigate Engine",
        "status": "BASIS_ACTIVE",
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root() -> str:
    """Landing page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Cognigate — The Open Governance Engine</title>
<meta name="description" content="The open-source enforcement engine for the BASIS standard. Trust scoring, capability gating, and cryptographic audit trails for AI agents." />
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: #0a0a0f;
    color: #e0e0e6;
    min-height: 100vh;
}}
a {{ color: #06b6d4; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.nav {{
    display: flex; gap: 1.5rem; padding: 1rem 2rem;
    background: #111118; border-bottom: 1px solid #1e1e2e;
    align-items: center; flex-wrap: wrap;
}}
.nav-brand {{ font-weight: 700; font-size: 1.1rem; color: #06b6d4; margin-right: auto; }}
.nav a {{ color: #888; font-size: 0.85rem; padding: 0.3rem 0.6rem; border-radius: 4px; transition: all 0.2s; }}
.nav a:hover {{ color: #06b6d4; background: rgba(6,182,212,0.1); text-decoration: none; }}

.hero {{
    max-width: 900px; margin: 0 auto; padding: 5rem 2rem 3rem;
    text-align: center;
}}
.hero h1 {{
    font-size: 3rem; color: #fff; line-height: 1.15; margin-bottom: 1rem;
    letter-spacing: -0.03em;
}}
.hero h1 span {{ color: #06b6d4; }}
.hero .subtitle {{
    font-size: 1.15rem; color: #888; max-width: 600px; margin: 0 auto 2rem;
    line-height: 1.6;
}}
.badge {{
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.35rem 0.85rem; border-radius: 99px;
    background: rgba(6,182,212,0.1); border: 1px solid rgba(6,182,212,0.2);
    color: #06b6d4; font-size: 0.8rem; font-weight: 600; margin-bottom: 1.5rem;
}}
.badge::before {{
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: #06b6d4; animation: pulse 2s infinite;
}}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}

.cta-row {{ display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; margin-bottom: 3rem; }}
.cta {{
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.75rem 1.5rem; border-radius: 8px;
    font-weight: 600; font-size: 0.95rem; transition: all 0.2s;
}}
.cta-primary {{ background: #06b6d4; color: #000; }}
.cta-primary:hover {{ background: #22d3ee; text-decoration: none; }}
.cta-secondary {{ background: rgba(255,255,255,0.05); color: #fff; border: 1px solid rgba(255,255,255,0.1); }}
.cta-secondary:hover {{ background: rgba(255,255,255,0.1); text-decoration: none; }}

.stack {{
    max-width: 900px; margin: 0 auto; padding: 0 2rem 4rem;
}}
.stack h2 {{
    text-align: center; font-size: 1.6rem; color: #fff; margin-bottom: 0.5rem;
}}
.stack .stack-sub {{
    text-align: center; color: #888; margin-bottom: 2rem; font-size: 0.95rem;
}}

.pipe {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;
}}
@media (max-width: 700px) {{ .pipe {{ grid-template-columns: 1fr 1fr; }} }}
.pipe-item {{
    background: #111118; border: 1px solid #1e1e2e; border-radius: 10px;
    padding: 1.5rem; text-align: center; transition: border-color 0.2s;
}}
.pipe-item:hover {{ border-color: rgba(6,182,212,0.4); }}
.pipe-label {{
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; margin-bottom: 0.5rem;
}}
.pipe-item:nth-child(1) .pipe-label {{ color: #fbbf24; }}
.pipe-item:nth-child(2) .pipe-label {{ color: #60a5fa; }}
.pipe-item:nth-child(3) .pipe-label {{ color: #818cf8; }}
.pipe-item:nth-child(4) .pipe-label {{ color: #34d399; }}
.pipe-name {{ font-size: 1.3rem; font-weight: 700; color: #fff; margin-bottom: 0.5rem; }}
.pipe-desc {{ font-size: 0.82rem; color: #888; line-height: 1.5; }}

.features {{
    max-width: 900px; margin: 0 auto; padding: 0 2rem 4rem;
}}
.features h2 {{
    text-align: center; font-size: 1.6rem; color: #fff; margin-bottom: 2rem;
}}
.feat-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }}
@media (max-width: 600px) {{ .feat-grid {{ grid-template-columns: 1fr; }} }}
.feat {{
    background: #111118; border: 1px solid #1e1e2e; border-radius: 10px;
    padding: 1.25rem; transition: border-color 0.2s;
}}
.feat:hover {{ border-color: rgba(6,182,212,0.3); }}
.feat h3 {{ color: #fff; font-size: 1rem; margin-bottom: 0.4rem; }}
.feat p {{ color: #888; font-size: 0.85rem; line-height: 1.5; }}

.tools-section {{
    max-width: 900px; margin: 0 auto; padding: 0 2rem 4rem;
}}
.tools-section h2 {{
    text-align: center; font-size: 1.6rem; color: #fff; margin-bottom: 0.5rem;
}}
.tools-sub {{
    text-align: center; color: #888; margin-bottom: 2rem; font-size: 0.95rem;
}}
.tool-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }}
@media (max-width: 700px) {{ .tool-grid {{ grid-template-columns: 1fr 1fr; }} }}
.tool-card {{
    background: #111118; border: 1px solid #1e1e2e; border-radius: 10px;
    padding: 1.25rem; text-align: center; transition: all 0.2s;
    display: block; color: inherit;
}}
.tool-card:hover {{ border-color: #06b6d4; text-decoration: none; transform: translateY(-2px); }}
.tool-icon {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
.tool-card h3 {{ color: #fff; font-size: 0.95rem; margin-bottom: 0.3rem; }}
.tool-card p {{ color: #666; font-size: 0.8rem; }}

.open-source {{
    max-width: 900px; margin: 0 auto; padding: 0 2rem 4rem; text-align: center;
}}
.os-box {{
    background: #111118; border: 1px solid #1e1e2e; border-radius: 12px;
    padding: 2.5rem; display: inline-block; max-width: 600px;
}}
.os-box h2 {{ color: #fff; font-size: 1.4rem; margin-bottom: 0.75rem; }}
.os-box p {{ color: #888; font-size: 0.95rem; line-height: 1.6; margin-bottom: 1.5rem; }}
.os-box code {{
    display: block; background: #0d0d14; border: 1px solid #2a2a3a;
    padding: 0.75rem 1rem; border-radius: 6px; color: #06b6d4;
    font-size: 0.9rem; margin-bottom: 1rem;
}}

footer {{
    border-top: 1px solid #1e1e2e; padding: 2rem;
    text-align: center; color: #555; font-size: 0.8rem;
}}
footer a {{ color: #666; }}
footer a:hover {{ color: #06b6d4; }}
</style>
</head>
<body>

<nav class="nav">
    <span class="nav-brand">Cognigate</span>
    <a href="/docs">API Docs</a>
    <a href="/redoc">ReDoc</a>
    <a href="/tools/calculator">Trust Calculator</a>
    <a href="/tools/errors">Error Codes</a>
    <a href="/tools/sdks">SDKs</a>
    <a href="/tools/playground">Playground</a>
    <a href="https://github.com/voriongit/cognigate">GitHub</a>
</nav>

<section class="hero">
    <div class="badge">Open Source &middot; Apache 2.0</div>
    <h1>The <span>Governance Engine</span> for Autonomous AI</h1>
    <p class="subtitle">
        Cognigate enforces the BASIS standard. Trust scoring, capability gating, policy enforcement, and cryptographic audit trails &mdash; all through a single API.
    </p>
    <div class="cta-row">
        <a href="/docs" class="cta cta-primary">Explore the API &rarr;</a>
        <a href="/tools/playground" class="cta cta-secondary">Try the Playground</a>
        <a href="https://github.com/voriongit/cognigate" class="cta cta-secondary">View Source</a>
    </div>
</section>

<section class="stack">
    <h2>The Stack</h2>
    <p class="stack-sub">Four layers. One pipeline. Every action governed.</p>
    <div class="pipe">
        <div class="pipe-item">
            <div class="pipe-label">Standard</div>
            <div class="pipe-name">BASIS</div>
            <div class="pipe-desc">The governance rules. What agents can and cannot do, before reasoning begins.</div>
        </div>
        <div class="pipe-item">
            <div class="pipe-label">Reasoning</div>
            <div class="pipe-name">INTENT</div>
            <div class="pipe-desc">Parses agent goals into structured plans. Surfaces risk without executing.</div>
        </div>
        <div class="pipe-item">
            <div class="pipe-label">Enforcement</div>
            <div class="pipe-name">ENFORCE</div>
            <div class="pipe-desc">Validates plans against BASIS policies. Gates execution. Escalates when needed.</div>
        </div>
        <div class="pipe-item">
            <div class="pipe-label">Audit</div>
            <div class="pipe-name">PROOF</div>
            <div class="pipe-desc">Cryptographic record of every decision. Immutable. Verifiable. The receipts.</div>
        </div>
    </div>
</section>

<section class="features">
    <h2>What Cognigate Does</h2>
    <div class="feat-grid">
        <div class="feat">
            <h3>8-Tier Trust Scoring</h3>
            <p>Agents earn autonomy through behavior. 0&ndash;1000 scores map to 8 tiers from Sandbox to Autonomous. Higher trust unlocks more capability.</p>
        </div>
        <div class="feat">
            <h3>24 Capability Gates</h3>
            <p>Fine-grained permission model. Each capability requires a minimum trust tier. Agents can only access what they have earned.</p>
        </div>
        <div class="feat">
            <h3>Policy Enforcement</h3>
            <p>Every agent action passes through ENFORCE before execution. Risk-based routing sends low-risk actions to express path, high-risk to council review.</p>
        </div>
        <div class="feat">
            <h3>Cryptographic Audit Trail</h3>
            <p>PROOF layer logs every intent, enforcement decision, and outcome with cryptographic signatures. Tamper-evident and compliance-ready.</p>
        </div>
        <div class="feat">
            <h3>Agent Lifecycle Management</h3>
            <p>Register, admit, monitor, and revoke agents. Gate Trust admission with observation tiers. Full signal history per agent.</p>
        </div>
        <div class="feat">
            <h3>Gateway to AgentAnchor</h3>
            <p>Single API surface that proxies to the full AgentAnchor platform &mdash; compliance, council, observer, truth-chain, academy, and more.</p>
        </div>
    </div>
</section>

<section class="tools-section">
    <h2>Developer Tools</h2>
    <p class="tools-sub">Interactive tools powered by live reference data. No login required.</p>
    <div class="tool-grid">
        <a href="/tools/calculator" class="tool-card">
            <div class="tool-icon">&#9878;</div>
            <h3>Trust Calculator</h3>
            <p>Explore the 8-tier model</p>
        </a>
        <a href="/tools/errors" class="tool-card">
            <div class="tool-icon">&#9888;</div>
            <h3>Error Codes</h3>
            <p>Search 38+ error codes</p>
        </a>
        <a href="/tools/sdks" class="tool-card">
            <div class="tool-icon">&lt;/&gt;</div>
            <h3>SDK Quickstart</h3>
            <p>TS, Python, Go, cURL</p>
        </a>
        <a href="/tools/playground" class="tool-card">
            <div class="tool-icon">&#9654;</div>
            <h3>Playground</h3>
            <p>Full pipeline testing</p>
        </a>
    </div>
</section>

<section class="open-source">
    <div class="os-box">
        <h2>Open Source. Apache 2.0.</h2>
        <p>Cognigate is the reference implementation of the BASIS standard. Inspect it, fork it, build on it. The governance engine should be as transparent as the systems it governs.</p>
        <code>git clone https://github.com/voriongit/cognigate.git</code>
        <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;">
            <a href="https://github.com/voriongit/cognigate" class="cta cta-primary" style="font-size:0.85rem;padding:0.6rem 1.2rem;">GitHub Repository</a>
            <a href="https://basis.vorion.org" class="cta cta-secondary" style="font-size:0.85rem;padding:0.6rem 1.2rem;">Read the BASIS Standard</a>
            <a href="https://vorion.org" class="cta cta-secondary" style="font-size:0.85rem;padding:0.6rem 1.2rem;">Vorion.org</a>
        </div>
    </div>
</section>

<footer>
    <p>
        Cognigate Engine v{settings.app_version} &middot;
        <a href="/docs">API Docs</a> &middot;
        <a href="/openapi.json">OpenAPI Spec</a> &middot;
        <a href="/status">JSON Status</a> &middot;
        <a href="https://github.com/voriongit/cognigate">GitHub</a>
    </p>
    <p style="margin-top:0.5rem;">&copy; 2026 Vorion Risk, LLC. &middot; Powered by <a href="https://vorion.org">VORION</a></p>
</footer>

</body>
</html>"""
