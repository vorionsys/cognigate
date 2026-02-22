"""
Developer Tools Pages Router

Serves interactive HTML tool pages for developers:
- Trust Tier Calculator
- Error Code Reference
- SDK Quickstart Hub
- API Playground (enhanced)
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.theme import get_active_theme, theme_to_css_vars

router = APIRouter()

# =============================================================================
# SHARED STYLES — Driven by unified theme system (app/theme.py)
# =============================================================================

def _build_base_style() -> str:
    """Generate _BASE_STYLE from the active theme."""
    t = get_active_theme()
    css_vars = theme_to_css_vars()
    blur = "backdrop-filter: blur(12px);" if t["card_blur"] else ""
    return f"""
    :root {{ {css_vars} }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: {t['font_family']};
        background: var(--bg-primary);
        color: var(--text-primary);
        min-height: 100vh;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    ::selection {{ background: var(--selection-bg); }}
    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: var(--scroll-track); }}
    ::-webkit-scrollbar-thumb {{ background: var(--scroll-thumb); border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: var(--scroll-thumb-hover); }}

    .nav {{
        display: flex;
        gap: 1.5rem;
        padding: 1rem 2rem;
        background: var(--bg-nav);
        border-bottom: 1px solid var(--border);
        align-items: center;
        flex-wrap: wrap;
        {blur}
    }}
    .nav-brand {{
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--accent);
        margin-right: auto;
    }}
    .nav a {{
        color: var(--text-secondary);
        font-size: 0.85rem;
        padding: 0.3rem 0.6rem;
        border-radius: 4px;
        transition: all 0.2s;
    }}
    .nav a:hover, .nav a.active {{
        color: var(--accent);
        background: var(--accent-muted);
        text-decoration: none;
    }}

    .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
    h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; color: var(--text-heading); }}
    h2 {{ font-size: 1.3rem; margin: 1.5rem 0 0.75rem; color: var(--text-secondary); }}
    .subtitle {{ color: var(--text-secondary); margin-bottom: 2rem; }}

    .card {{
        background: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        {blur}
    }}

    input, select, button {{
        font-family: inherit;
        font-size: 0.9rem;
        border: 1px solid var(--border-input);
        background: var(--bg-input);
        color: var(--text-primary);
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
    }}
    input:focus, select:focus {{ outline: none; border-color: var(--accent); }}
    button {{
        background: var(--accent);
        color: var(--btn-text);
        border: none;
        cursor: pointer;
        font-weight: 600;
        transition: background 0.2s;
    }}
    button:hover {{ background: var(--accent-hover); }}

    .badge {{
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }}
    th, td {{
        text-align: left;
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid var(--border);
    }}
    th {{ color: var(--text-secondary); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }}
    tr:hover td {{ background: var(--accent-subtle); }}

    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }}

    code {{
        background: var(--bg-input);
        padding: 0.15rem 0.4rem;
        border-radius: 3px;
        font-size: 0.85rem;
    }}
    pre {{
        background: var(--bg-code);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 1rem;
        overflow-x: auto;
        font-size: 0.8rem;
        line-height: 1.5;
        margin: 0.75rem 0;
    }}
    pre code {{ background: none; padding: 0; }}
    .copy-btn {{
        float: right;
        font-size: 0.7rem;
        padding: 0.2rem 0.5rem;
        background: var(--border-input);
        color: var(--text-secondary);
    }}
    .copy-btn:hover {{ background: var(--border); color: var(--text-heading); }}
    """

_BASE_STYLE = _build_base_style()

_NAV_HTML = """
<nav class="nav">
    <a href="/" class="nav-brand" style="display:flex;align-items:center;gap:0.5rem;text-decoration:none;">
        <img src="/static/cognigate-logo.png" alt="Cognigate" width="24" height="24" style="border-radius:4px;" />
        Cognigate
    </a>
    <a href="/docs">API Docs</a>
    <a href="/tools/calculator" id="nav-calc">Trust Calculator</a>
    <a href="/tools/errors" id="nav-errors">Error Codes</a>
    <a href="/tools/sdks" id="nav-sdks">SDKs</a>
    <a href="/tools/playground" id="nav-playground">Playground</a>
    <a href="/tools/themes" id="nav-themes">Themes</a>
    <a href="/redoc">ReDoc</a>
</nav>
"""


# =============================================================================
# TRUST TIER CALCULATOR
# =============================================================================

@router.get("/tools/calculator", response_class=HTMLResponse, include_in_schema=False)
async def trust_calculator():
    """Interactive trust tier calculator — enter a score, see tier details."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trust Tier Calculator - Cognigate</title>
    <style>{_BASE_STYLE}
    .slider-container {{ margin: 1.5rem 0; }}
    .slider-container input[type=range] {{
        width: 100%; height: 6px;
        -webkit-appearance: none; appearance: none;
        background: linear-gradient(to right,
            #78716c 0%, #ef4444 20%, #f97316 35%, #eab308 50%,
            #22c55e 65%, #3b82f6 80%, #8b5cf6 88%, #06b6d4 95%);
        border-radius: 3px; border: none;
    }}
    .slider-container input[type=range]::-webkit-slider-thumb {{
        -webkit-appearance: none; width: 20px; height: 20px;
        background: #fff; border-radius: 50%; cursor: pointer;
        box-shadow: 0 0 6px rgba(0,0,0,0.5);
    }}
    .score-display {{
        font-size: 3rem; font-weight: 700; text-align: center;
        margin: 0.5rem 0;
    }}
    .tier-badge {{
        text-align: center; font-size: 1.5rem; font-weight: 700;
        padding: 0.5rem 1.5rem; border-radius: 8px; margin: 0.5rem auto;
        display: inline-block;
    }}
    .caps-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 0.5rem; margin-top: 0.5rem; }}
    .cap-item {{
        background: #0d0d14; border: 1px solid #1e1e2e;
        padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.8rem;
    }}
    .cap-item .cap-code {{ color: #06b6d4; font-weight: 600; }}
    .cap-item .cap-tier {{ float: right; color: #888; font-size: 0.7rem; }}
    .limits-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.5rem; margin-top: 0.5rem; }}
    .limit-item {{ background: #0d0d14; border: 1px solid #1e1e2e; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.8rem; }}
    .limit-label {{ color: #888; font-size: 0.7rem; }}
    .limit-value {{ color: #22c55e; font-weight: 600; font-size: 1rem; }}
    </style>
</head>
<body>
{_NAV_HTML}
<div class="container">
    <h1>Trust Tier Calculator</h1>
    <p class="subtitle">Slide to explore the 8-tier BASIS trust model (T0-T7, scores 0-1000)</p>

    <div class="card" style="text-align:center;">
        <div class="score-display" id="score-display">500</div>
        <div class="slider-container">
            <input type="range" id="score-slider" min="0" max="1000" value="500">
        </div>
        <div style="display:flex;justify-content:space-between;color:#888;font-size:0.8rem;">
            <span>0 (Sandbox)</span><span>1000 (Autonomous)</span>
        </div>
        <div style="margin-top:1rem;">
            <span class="tier-badge" id="tier-badge">T3 Monitored</span>
        </div>
        <p id="tier-desc" style="color:#888;margin-top:0.5rem;"></p>
    </div>

    <h2>Available Capabilities</h2>
    <div class="caps-grid" id="caps-grid"></div>

    <h2>Rate Limits & Quotas</h2>
    <div class="limits-grid" id="limits-grid"></div>
</div>

<script>
let tiersData = null;

async function loadData() {{
    const resp = await fetch('/v1/reference/tiers');
    const data = await resp.json();
    tiersData = data.tiers;
    updateDisplay();
}}

function getTierForScore(score) {{
    if (!tiersData) return null;
    for (let i = tiersData.length - 1; i >= 0; i--) {{
        if (score >= tiersData[i].min) return tiersData[i];
    }}
    return tiersData[0];
}}

async function updateDisplay() {{
    const score = parseInt(document.getElementById('score-slider').value);
    document.getElementById('score-display').textContent = score;

    const tier = getTierForScore(score);
    if (!tier) return;

    const badge = document.getElementById('tier-badge');
    badge.textContent = 'T' + tier.tier + ' ' + tier.name;
    badge.style.background = tier.color;
    badge.style.color = tier.textColor;
    document.getElementById('tier-desc').textContent = tier.description;

    // Fetch full tier detail
    const detail = await fetch('/v1/reference/tiers/T' + tier.tier);
    const d = await detail.json();

    // Capabilities
    const capsGrid = document.getElementById('caps-grid');
    capsGrid.innerHTML = d.capabilities.map(c =>
        '<div class="cap-item"><span class="cap-code">' + c.code + '</span>' +
        '<span class="cap-tier">T' + c.unlockTier + '</span><br>' + c.name + '</div>'
    ).join('');

    // Rate limits
    const rl = d.rateLimits;
    const q = d.quotas;
    const limitsGrid = document.getElementById('limits-grid');
    limitsGrid.innerHTML = [
        ['Req/sec', rl.requestsPerSecond],
        ['Req/min', rl.requestsPerMinute],
        ['Req/hour', rl.requestsPerHour.toLocaleString()],
        ['Req/day', rl.requestsPerDay.toLocaleString()],
        ['Burst', rl.burstLimit],
        ['Max Payload', formatBytes(rl.maxPayloadBytes)],
        ['Monthly API Calls', q.monthlyApiCalls === -1 ? 'Unlimited' : q.monthlyApiCalls.toLocaleString()],
        ['Max Agents', q.maxAgents === -1 ? 'Unlimited' : q.maxAgents.toLocaleString()],
    ].map(([label, val]) =>
        '<div class="limit-item"><div class="limit-label">' + label + '</div><div class="limit-value">' + val + '</div></div>'
    ).join('');
}}

function formatBytes(bytes) {{
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(0) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return bytes + ' B';
}}

document.getElementById('score-slider').addEventListener('input', updateDisplay);
loadData();
document.getElementById('nav-calc').classList.add('active');
</script>
</body>
</html>"""


# =============================================================================
# ERROR CODE REFERENCE
# =============================================================================

@router.get("/tools/errors", response_class=HTMLResponse, include_in_schema=False)
async def error_reference():
    """Searchable error code reference page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error Codes - Cognigate</title>
    <style>{_BASE_STYLE}
    .filters {{ display: flex; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap; }}
    .filters input {{ flex: 1; min-width: 200px; }}
    .filters select {{ min-width: 150px; }}
    .retryable {{ color: #22c55e; }}
    .not-retryable {{ color: #ef4444; }}
    .category-badge {{
        display: inline-block; padding: 0.15rem 0.5rem;
        border-radius: 4px; font-size: 0.7rem; font-weight: 600;
        text-transform: uppercase;
    }}
    .cat-auth {{ background: rgba(239,68,68,0.15); color: #ef4444; }}
    .cat-validation {{ background: rgba(249,115,22,0.15); color: #f97316; }}
    .cat-rate_limit {{ background: rgba(234,179,8,0.15); color: #eab308; }}
    .cat-not_found {{ background: rgba(59,130,246,0.15); color: #3b82f6; }}
    .cat-trust {{ background: rgba(139,92,246,0.15); color: #8b5cf6; }}
    .cat-server {{ background: rgba(239,68,68,0.15); color: #ef4444; }}
    .cat-external {{ background: rgba(6,182,212,0.15); color: #06b6d4; }}
    </style>
</head>
<body>
{_NAV_HTML}
<div class="container">
    <h1>Error Code Reference</h1>
    <p class="subtitle">All 35+ standardized error codes across 7 categories</p>

    <div class="filters">
        <input type="text" id="search" placeholder="Search by code, message, or category...">
        <select id="category-filter">
            <option value="">All Categories</option>
            <option value="auth">Auth (E1xxx)</option>
            <option value="validation">Validation (E2xxx)</option>
            <option value="rate_limit">Rate Limit (E3xxx)</option>
            <option value="not_found">Not Found (E4xxx)</option>
            <option value="trust">Trust (E5xxx)</option>
            <option value="server">Server (E6xxx)</option>
            <option value="external">External (E7xxx)</option>
        </select>
        <select id="retry-filter">
            <option value="">All</option>
            <option value="true">Retryable</option>
            <option value="false">Not Retryable</option>
        </select>
    </div>

    <div class="card">
        <table>
            <thead>
                <tr><th>Code</th><th>HTTP</th><th>Category</th><th>Message</th><th>Retryable</th></tr>
            </thead>
            <tbody id="error-table"></tbody>
        </table>
    </div>
    <p id="count" style="color:#888;font-size:0.8rem;margin-top:0.5rem;"></p>
</div>

<script>
let allErrors = [];

async function loadErrors() {{
    const resp = await fetch('/v1/reference/errors');
    const data = await resp.json();
    allErrors = data.errors;
    renderTable();
}}

function renderTable() {{
    const search = document.getElementById('search').value.toLowerCase();
    const cat = document.getElementById('category-filter').value;
    const retry = document.getElementById('retry-filter').value;

    let filtered = allErrors;
    if (search) {{
        filtered = filtered.filter(e =>
            e.code.toLowerCase().includes(search) ||
            e.message.toLowerCase().includes(search) ||
            e.category.toLowerCase().includes(search)
        );
    }}
    if (cat) filtered = filtered.filter(e => e.category === cat);
    if (retry) filtered = filtered.filter(e => String(e.retryable) === retry);

    const tbody = document.getElementById('error-table');
    tbody.innerHTML = filtered.map(e => `
        <tr>
            <td><code>${{e.code}}</code></td>
            <td>${{e.httpStatus}}</td>
            <td><span class="category-badge cat-${{e.category}}">${{e.category}}</span></td>
            <td>${{e.message}}</td>
            <td class="${{e.retryable ? 'retryable' : 'not-retryable'}}">${{e.retryable ? 'Yes' : 'No'}}</td>
        </tr>
    `).join('');

    document.getElementById('count').textContent = filtered.length + ' of ' + allErrors.length + ' error codes';
}}

document.getElementById('search').addEventListener('input', renderTable);
document.getElementById('category-filter').addEventListener('change', renderTable);
document.getElementById('retry-filter').addEventListener('change', renderTable);
loadErrors();
document.getElementById('nav-errors').classList.add('active');
</script>
</body>
</html>"""


# =============================================================================
# SDK QUICKSTART HUB
# =============================================================================

@router.get("/tools/sdks", response_class=HTMLResponse, include_in_schema=False)
async def sdk_hub():
    """SDK quickstart and installation guide."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SDK Quickstart - Cognigate</title>
    <style>{_BASE_STYLE}</style>
</head>
<body>
{_NAV_HTML}
<div class="container">
    <h1>SDK Quickstart</h1>
    <p class="subtitle">Get started with the Cognigate governance API in your language of choice</p>

    <div class="grid">
        <div class="card">
            <h2 style="margin-top:0;">TypeScript / Node.js</h2>
            <p style="color:#888;font-size:0.85rem;">Official TypeScript SDK with full type safety</p>
            <pre><code>npm install @vorionsys/cognigate</code></pre>
            <pre><code>import {{ Cognigate }} from '@vorionsys/cognigate';

const cg = new Cognigate({{
  apiKey: process.env.COGNIGATE_API_KEY,
  baseUrl: 'https://cognigate.dev',
}});

// Parse intent
const intent = await cg.intent.parse({{
  agentId: 'agent_001',
  rawIntent: 'Read user profile data',
  trustScore: 650,
}});

// Enforce policies
const decision = await cg.enforce.evaluate({{
  intent: intent.normalized,
  agentId: 'agent_001',
  trustLevel: 4,
}});

// Create proof
const proof = await cg.proof.create({{
  event: 'intent_enforced',
  entityId: 'agent_001',
  payload: {{ intent, decision }},
}});</code></pre>
        </div>

        <div class="card">
            <h2 style="margin-top:0;">Python</h2>
            <p style="color:#888;font-size:0.85rem;">Python SDK with async support</p>
            <pre><code>pip install cognigate</code></pre>
            <pre><code>from cognigate import Cognigate

cg = Cognigate(
    api_key="your-api-key",
    base_url="https://cognigate.dev",
)

# Parse intent
intent = await cg.intent.parse(
    agent_id="agent_001",
    raw_intent="Read user profile data",
    trust_score=650,
)

# Enforce policies
decision = await cg.enforce.evaluate(
    intent=intent.normalized,
    agent_id="agent_001",
    trust_level=4,
)

# Create proof
proof = await cg.proof.create(
    event="intent_enforced",
    entity_id="agent_001",
    payload={{"intent": intent, "decision": decision}},
)</code></pre>
        </div>

        <div class="card">
            <h2 style="margin-top:0;">cURL / REST</h2>
            <p style="color:#888;font-size:0.85rem;">Direct HTTP access to the API</p>
            <pre><code># Parse intent
curl -X POST https://cognigate.dev/v1/intent \\
  -H "X-API-Key: your-key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "agent_id": "agent_001",
    "raw_intent": "Read user profile data",
    "trust_score": 650
  }}'

# Enforce policies
curl -X POST https://cognigate.dev/v1/enforce \\
  -H "X-API-Key: your-key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "intent": "data.read.user_profile",
    "agent_id": "agent_001",
    "trust_level": 4
  }}'

# Get trust tiers
curl https://cognigate.dev/v1/reference/tiers</code></pre>
        </div>

        <div class="card">
            <h2 style="margin-top:0;">Go</h2>
            <p style="color:#888;font-size:0.85rem;">Go client library</p>
            <pre><code>go get github.com/voriongit/cognigate-go</code></pre>
            <pre><code>package main

import (
    "context"
    cognigate "github.com/voriongit/cognigate-go"
)

func main() {{
    client := cognigate.NewClient(
        cognigate.WithAPIKey("your-api-key"),
        cognigate.WithBaseURL("https://cognigate.dev"),
    )

    // Parse intent
    intent, _ := client.Intent.Parse(context.Background(),
        &cognigate.IntentRequest{{
            AgentID:    "agent_001",
            RawIntent:  "Read user profile data",
            TrustScore: 650,
        }},
    )
}}</code></pre>
        </div>
    </div>

    <h2>Quick Links</h2>
    <div class="grid">
        <div class="card">
            <strong>API Documentation</strong>
            <p style="color:#888;font-size:0.85rem;margin-top:0.3rem;">
                Interactive Swagger UI with try-it-out for all endpoints
            </p>
            <a href="/docs" style="font-size:0.85rem;">Open Swagger UI &rarr;</a>
        </div>
        <div class="card">
            <strong>ReDoc Reference</strong>
            <p style="color:#888;font-size:0.85rem;margin-top:0.3rem;">
                Clean, readable API reference documentation
            </p>
            <a href="/redoc" style="font-size:0.85rem;">Open ReDoc &rarr;</a>
        </div>
        <div class="card">
            <strong>OpenAPI Spec</strong>
            <p style="color:#888;font-size:0.85rem;margin-top:0.3rem;">
                Download the raw OpenAPI 3.1 specification
            </p>
            <a href="/openapi.json" style="font-size:0.85rem;">Download JSON &rarr;</a>
        </div>
        <div class="card">
            <strong>GitHub</strong>
            <p style="color:#888;font-size:0.85rem;margin-top:0.3rem;">
                Source code, issues, and contributions
            </p>
            <a href="https://github.com/voriongit/vorion" style="font-size:0.85rem;">View on GitHub &rarr;</a>
        </div>
    </div>
</div>

<script>
document.getElementById('nav-sdks').classList.add('active');
</script>
</body>
</html>"""


# =============================================================================
# PLAYGROUND (Enhanced)
# =============================================================================

@router.get("/tools/playground", response_class=HTMLResponse, include_in_schema=False)
async def playground():
    """Enhanced API playground with full pipeline mode and preset scenarios."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Playground - Cognigate</title>
    <style>{_BASE_STYLE}
    .pipeline {{ display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; }}
    .pipeline-step {{
        flex: 1; min-width: 200px;
        background: #111118; border: 1px solid #1e1e2e;
        border-radius: 8px; padding: 1rem;
        position: relative;
    }}
    .pipeline-step.active {{ border-color: #06b6d4; }}
    .pipeline-step.done {{ border-color: #22c55e; }}
    .pipeline-step.error {{ border-color: #ef4444; }}
    .step-num {{
        position: absolute; top: -10px; left: 12px;
        background: #06b6d4; color: #000;
        width: 20px; height: 20px; border-radius: 50%;
        font-size: 0.7rem; font-weight: 700;
        display: flex; align-items: center; justify-content: center;
    }}
    .pipeline-step.done .step-num {{ background: #22c55e; }}
    .pipeline-step.error .step-num {{ background: #ef4444; color: #fff; }}
    .step-title {{ font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem; }}
    .step-result {{ font-size: 0.8rem; color: #888; max-height: 150px; overflow-y: auto; }}
    .step-result pre {{ margin: 0; font-size: 0.75rem; }}
    .scenarios {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }}
    .scenario-btn {{
        padding: 0.4rem 0.8rem;
        background: #1e1e2e;
        border: 1px solid #2a2a3a;
        color: #888;
        font-size: 0.8rem;
        cursor: pointer;
        border-radius: 6px;
    }}
    .scenario-btn:hover {{ border-color: #06b6d4; color: #06b6d4; background: rgba(6,182,212,0.05); }}
    textarea {{
        width: 100%; min-height: 80px;
        background: #0d0d14; color: #e0e0e6;
        border: 1px solid #2a2a3a; border-radius: 6px;
        padding: 0.75rem; font-family: monospace; font-size: 0.85rem;
        resize: vertical;
    }}
    textarea:focus {{ outline: none; border-color: #06b6d4; }}
    .controls {{ display: flex; gap: 0.75rem; margin: 1rem 0; align-items: center; }}
    #status {{ color: #888; font-size: 0.85rem; }}
    </style>
</head>
<body>
{_NAV_HTML}
<div class="container">
    <h1>API Playground</h1>
    <p class="subtitle">Test the full INTENT &rarr; ENFORCE &rarr; PROOF pipeline in one click</p>

    <h2>Preset Scenarios</h2>
    <div class="scenarios">
        <button class="scenario-btn" onclick="loadScenario('safe_read')">Safe Read</button>
        <button class="scenario-btn" onclick="loadScenario('pii_access')">PII Access</button>
        <button class="scenario-btn" onclick="loadScenario('shell_exec')">Shell Execution</button>
        <button class="scenario-btn" onclick="loadScenario('cred_access')">Credential Access</button>
        <button class="scenario-btn" onclick="loadScenario('agent_spawn')">Agent Spawn</button>
        <button class="scenario-btn" onclick="loadScenario('db_write')">Database Write</button>
    </div>

    <div class="card">
        <label style="font-size:0.85rem;color:#888;">Intent Request Body (JSON)</label>
        <textarea id="request-body"></textarea>
    </div>

    <div class="controls">
        <button onclick="runPipeline()">Run Full Pipeline</button>
        <button onclick="runStep('intent')" style="background:#2a2a3a;color:#e0e0e6;">Intent Only</button>
        <button onclick="runStep('enforce')" style="background:#2a2a3a;color:#e0e0e6;">Enforce Only</button>
        <span id="status"></span>
    </div>

    <div class="pipeline">
        <div class="pipeline-step" id="step-intent">
            <div class="step-num">1</div>
            <div class="step-title">INTENT</div>
            <div class="step-result" id="result-intent">Waiting...</div>
        </div>
        <div class="pipeline-step" id="step-enforce">
            <div class="step-num">2</div>
            <div class="step-title">ENFORCE</div>
            <div class="step-result" id="result-enforce">Waiting...</div>
        </div>
        <div class="pipeline-step" id="step-proof">
            <div class="step-num">3</div>
            <div class="step-title">PROOF</div>
            <div class="step-result" id="result-proof">Waiting...</div>
        </div>
    </div>
</div>

<script>
const scenarios = {{
    safe_read: {{
        agent_id: "agent_reader_01",
        raw_intent: "Read the public product catalog",
        trust_score: 650,
        context: {{ domain: "data_access", operation: "read" }}
    }},
    pii_access: {{
        agent_id: "agent_data_02",
        raw_intent: "Access user personal information including email and phone",
        trust_score: 400,
        context: {{ domain: "data_access", operation: "read", sensitivity: "pii" }}
    }},
    shell_exec: {{
        agent_id: "agent_ops_03",
        raw_intent: "Execute shell command to restart the web server",
        trust_score: 300,
        context: {{ domain: "code_execution", operation: "shell", target: "web_server" }}
    }},
    cred_access: {{
        agent_id: "agent_deploy_04",
        raw_intent: "Access database credentials for production deployment",
        trust_score: 500,
        context: {{ domain: "resource_management", operation: "read", sensitivity: "credentials" }}
    }},
    agent_spawn: {{
        agent_id: "agent_orchestrator_05",
        raw_intent: "Spawn a new worker agent for data processing",
        trust_score: 900,
        context: {{ domain: "agent_interaction", operation: "spawn" }}
    }},
    db_write: {{
        agent_id: "agent_writer_06",
        raw_intent: "Write updated pricing data to the products table",
        trust_score: 550,
        context: {{ domain: "data_access", operation: "write", target: "products_table" }}
    }},
}};

function loadScenario(name) {{
    document.getElementById('request-body').value = JSON.stringify(scenarios[name], null, 2);
    resetSteps();
}}

function resetSteps() {{
    ['intent', 'enforce', 'proof'].forEach(s => {{
        document.getElementById('step-' + s).className = 'pipeline-step';
        document.getElementById('result-' + s).textContent = 'Waiting...';
    }});
    document.getElementById('status').textContent = '';
}}

async function postJSON(url, body) {{
    const resp = await fetch(url, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body),
    }});
    return {{ status: resp.status, data: await resp.json() }};
}}

function showResult(step, data, ok) {{
    const el = document.getElementById('step-' + step);
    el.className = 'pipeline-step ' + (ok ? 'done' : 'error');
    document.getElementById('result-' + step).innerHTML =
        '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
}}

async function runStep(step) {{
    let body;
    try {{ body = JSON.parse(document.getElementById('request-body').value); }}
    catch {{ document.getElementById('status').textContent = 'Invalid JSON'; return; }}

    resetSteps();
    document.getElementById('status').textContent = 'Running ' + step + '...';

    const url = '/v1/' + step;
    const result = await postJSON(url, body);
    showResult(step, result.data, result.status < 400);
    document.getElementById('status').textContent = 'Done (' + result.status + ')';
}}

async function runPipeline() {{
    let body;
    try {{ body = JSON.parse(document.getElementById('request-body').value); }}
    catch {{ document.getElementById('status').textContent = 'Invalid JSON'; return; }}

    resetSteps();

    // Step 1: Intent
    document.getElementById('status').textContent = 'Running INTENT...';
    document.getElementById('step-intent').className = 'pipeline-step active';
    const intentResult = await postJSON('/v1/intent', body);
    showResult('intent', intentResult.data, intentResult.status < 400);

    if (intentResult.status >= 400) {{
        document.getElementById('status').textContent = 'Pipeline stopped at INTENT';
        return;
    }}

    // Step 2: Enforce
    document.getElementById('status').textContent = 'Running ENFORCE...';
    document.getElementById('step-enforce').className = 'pipeline-step active';
    const enforceBody = {{
        intent: intentResult.data.normalized || intentResult.data,
        agent_id: body.agent_id,
        trust_level: Math.floor((body.trust_score || 0) / 200),
        ...body.context,
    }};
    const enforceResult = await postJSON('/v1/enforce', enforceBody);
    showResult('enforce', enforceResult.data, enforceResult.status < 400);

    if (enforceResult.status >= 400) {{
        document.getElementById('status').textContent = 'Pipeline stopped at ENFORCE';
        return;
    }}

    // Step 3: Proof
    document.getElementById('status').textContent = 'Running PROOF...';
    document.getElementById('step-proof').className = 'pipeline-step active';
    const proofBody = {{
        event_type: "intent_enforced",
        entity_id: body.agent_id,
        payload: {{
            intent: intentResult.data,
            enforcement: enforceResult.data,
        }},
    }};
    const proofResult = await postJSON('/v1/proof', proofBody);
    showResult('proof', proofResult.data, proofResult.status < 400);

    document.getElementById('status').textContent = 'Pipeline complete';
}}

// Load default scenario
loadScenario('safe_read');
document.getElementById('nav-playground').classList.add('active');
</script>
</body>
</html>"""


# =============================================================================
# THEME VOTING API
# =============================================================================

from pydantic import BaseModel, Field


class ThemeVoteRequest(BaseModel):
    theme_id: str = Field(..., description="Theme ID to vote for")
    voter: str = Field(default="anonymous", description="Voter name (optional)")


@router.post("/v1/themes/vote", tags=["themes"])
async def vote_for_theme(req: ThemeVoteRequest):
    """Cast a vote for a theme."""
    from app.theme import THEMES
    from app.core.votes import cast_vote, get_vote_counts

    if req.theme_id not in THEMES:
        return {"error": f"Unknown theme: {req.theme_id}", "valid": list(THEMES.keys())}
    record = cast_vote(req.theme_id, req.voter)
    counts = get_vote_counts()
    return {
        "status": "voted",
        "vote": record,
        "totals": counts,
    }


@router.get("/v1/themes/votes", tags=["themes"])
async def get_theme_votes():
    """Get current vote counts and recent voters for all themes."""
    from app.theme import THEMES
    from app.core.votes import get_all_votes

    all_votes = get_all_votes()
    total = len(all_votes)

    breakdown = {}
    for tid in THEMES:
        theme_votes = [v for v in all_votes if v["theme_id"] == tid]
        count = len(theme_votes)
        recent = sorted(theme_votes, key=lambda v: v["timestamp"], reverse=True)[:5]
        breakdown[tid] = {
            "name": THEMES[tid]["name"],
            "count": count,
            "percentage": round(count / total * 100, 1) if total > 0 else 0,
            "recent_voters": [v["voter"] for v in recent],
        }

    ranked = sorted(breakdown.items(), key=lambda x: x[1]["count"], reverse=True)
    return {
        "total_votes": total,
        "leader": ranked[0][0] if ranked and ranked[0][1]["count"] > 0 else None,
        "themes": dict(ranked),
    }


# =============================================================================
# THEME PREVIEW — Compare all 4 themes side-by-side with voting
# =============================================================================

@router.get("/tools/themes", response_class=HTMLResponse, include_in_schema=False)
async def theme_preview():
    """Preview all 4 unified themes side-by-side with live voting."""
    from app.theme import THEMES, ACTIVE_THEME
    from app.core.votes import get_vote_counts

    counts = get_vote_counts()
    total_votes = sum(counts.values())

    # Build preview cards for each theme
    theme_cards = ""
    for tid, t in THEMES.items():
        is_active = tid == ACTIVE_THEME
        active_badge = '<span style="background:var(--success);color:#000;padding:0.15rem 0.5rem;border-radius:99px;font-size:0.7rem;font-weight:700;margin-left:0.5rem;">ACTIVE</span>' if is_active else ''
        vote_count = counts.get(tid, 0)
        pct = round(vote_count / total_votes * 100) if total_votes > 0 else 0
        blur = "backdrop-filter:blur(12px);" if t["card_blur"] else ""

        theme_cards += f"""
        <div class="theme-card" style="--tc-bg:{t['bg_primary']};--tc-surface:{t['bg_surface']};--tc-accent:{t['accent']};--tc-accent-hover:{t['accent_hover']};--tc-text:{t['text_primary']};--tc-heading:{t['text_heading']};--tc-secondary:{t['text_secondary']};--tc-border:{t['border']};--tc-border-input:{t['border_input']};--tc-input:{t['bg_input']};--tc-muted:{t['accent_muted']};--tc-grad-from:{t['gradient_from']};--tc-grad-to:{t['gradient_to']};--tc-layer-basis:{t['layer_basis']};--tc-layer-intent:{t['layer_intent']};--tc-layer-enforce:{t['layer_enforce']};--tc-layer-proof:{t['layer_proof']};">
            <div class="theme-preview" style="background:var(--tc-bg);border:1px solid var(--tc-border);border-radius:12px;overflow:hidden;">
                <!-- Mini nav -->
                <div style="display:flex;gap:0.75rem;padding:0.6rem 1rem;background:var(--tc-surface);border-bottom:1px solid var(--tc-border);align-items:center;{blur}">
                    <span style="font-weight:700;font-size:0.8rem;color:var(--tc-accent);margin-right:auto;">Cognigate</span>
                    <span style="font-size:0.65rem;color:var(--tc-secondary);">API Docs</span>
                    <span style="font-size:0.65rem;color:var(--tc-secondary);">Tools</span>
                </div>
                <!-- Mini hero -->
                <div style="padding:1.5rem 1rem;text-align:center;">
                    <div style="display:inline-flex;align-items:center;gap:0.3rem;padding:0.2rem 0.5rem;border-radius:99px;background:var(--tc-muted);border:1px solid var(--tc-border);font-size:0.55rem;font-weight:600;color:var(--tc-accent);margin-bottom:0.75rem;">
                        <span style="width:4px;height:4px;border-radius:50%;background:var(--tc-accent);"></span>
                        OPEN SOURCE
                    </div>
                    <div style="font-size:1.1rem;font-weight:700;color:var(--tc-heading);margin-bottom:0.3rem;">The <span style="color:var(--tc-accent);">Governance Engine</span></div>
                    <div style="font-size:0.65rem;color:var(--tc-secondary);margin-bottom:0.75rem;">Trust scoring, capability gating, audit trails.</div>
                    <div style="display:flex;gap:0.5rem;justify-content:center;">
                        <span style="padding:0.3rem 0.7rem;border-radius:6px;background:var(--tc-accent);color:{t['button_text']};font-size:0.6rem;font-weight:600;">API Docs</span>
                        <span style="padding:0.3rem 0.7rem;border-radius:6px;background:rgba(255,255,255,0.05);color:var(--tc-heading);font-size:0.6rem;border:1px solid var(--tc-border);">Playground</span>
                    </div>
                </div>
                <!-- Mini pipe -->
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.4rem;padding:0 1rem 1rem;">
                    <div style="background:var(--tc-surface);border:1px solid var(--tc-border);border-radius:6px;padding:0.5rem;text-align:center;{blur}">
                        <div style="font-size:0.45rem;font-weight:700;color:var(--tc-layer-basis);text-transform:uppercase;letter-spacing:0.05em;">Standard</div>
                        <div style="font-size:0.7rem;font-weight:700;color:var(--tc-heading);">BASIS</div>
                    </div>
                    <div style="background:var(--tc-surface);border:1px solid var(--tc-border);border-radius:6px;padding:0.5rem;text-align:center;{blur}">
                        <div style="font-size:0.45rem;font-weight:700;color:var(--tc-layer-intent);text-transform:uppercase;letter-spacing:0.05em;">Reasoning</div>
                        <div style="font-size:0.7rem;font-weight:700;color:var(--tc-heading);">INTENT</div>
                    </div>
                    <div style="background:var(--tc-surface);border:1px solid var(--tc-border);border-radius:6px;padding:0.5rem;text-align:center;{blur}">
                        <div style="font-size:0.45rem;font-weight:700;color:var(--tc-layer-enforce);text-transform:uppercase;letter-spacing:0.05em;">Enforce</div>
                        <div style="font-size:0.7rem;font-weight:700;color:var(--tc-heading);">ENFORCE</div>
                    </div>
                    <div style="background:var(--tc-surface);border:1px solid var(--tc-border);border-radius:6px;padding:0.5rem;text-align:center;{blur}">
                        <div style="font-size:0.45rem;font-weight:700;color:var(--tc-layer-proof);text-transform:uppercase;letter-spacing:0.05em;">Audit</div>
                        <div style="font-size:0.7rem;font-weight:700;color:var(--tc-heading);">PROOF</div>
                    </div>
                </div>
                <!-- Mini gradient bar -->
                <div style="height:3px;background:linear-gradient(to right, var(--tc-grad-from), var(--tc-grad-to));"></div>
            </div>
            <!-- Vote + info row -->
            <div style="padding:0.75rem 0;" id="card-{tid}">
                <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.4rem;">
                    <h3 style="color:#fff;font-size:1rem;margin:0;">{t['name']}</h3>
                    {active_badge}
                </div>
                <p style="color:#888;font-size:0.8rem;margin-bottom:0.75rem;">{t['description']}</p>

                <!-- Vote bar -->
                <div style="display:flex;align-items:center;gap:0.6rem;" class="vote-row">
                    <button class="vote-btn" onclick="castVote('{tid}')" title="Vote for {t['name']}">
                        <span class="vote-heart">&#9829;</span>
                        <span>Vote</span>
                    </button>
                    <span class="vote-count" id="count-{tid}">{vote_count}</span>
                    <div class="vote-bar-track">
                        <div class="vote-bar-fill" id="bar-{tid}" style="width:{pct}%;background:{t['accent']};"></div>
                    </div>
                    <span class="vote-pct" id="pct-{tid}">{pct}%</span>
                </div>

                <!-- Color swatches -->
                <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.5rem;">
                    <div style="width:24px;height:24px;border-radius:4px;background:{t['bg_primary']};border:1px solid #333;" title="Background"></div>
                    <div style="width:24px;height:24px;border-radius:4px;background:{t['bg_surface']};border:1px solid #333;" title="Surface"></div>
                    <div style="width:24px;height:24px;border-radius:4px;background:{t['accent']};" title="Accent"></div>
                    <div style="width:24px;height:24px;border-radius:4px;background:{t['accent_hover']};" title="Accent Hover"></div>
                    <div style="width:24px;height:24px;border-radius:4px;background:{t['gradient_from']};" title="Gradient From"></div>
                    <div style="width:24px;height:24px;border-radius:4px;background:{t['gradient_to']};" title="Gradient To"></div>
                </div>
                <code style="display:block;margin-top:0.5rem;font-size:0.7rem;color:#888;background:rgba(255,255,255,0.05);padding:0.3rem 0.5rem;border-radius:4px;">ACTIVE_THEME = "{tid}"</code>
            </div>
        </div>
        """

    # JS theme maps for client-side updates
    accents_js = ', '.join(f'"{tid}": "{t["accent"]}"' for tid, t in THEMES.items())
    names_js = ', '.join(f'"{tid}": "{t["name"]}"' for tid, t in THEMES.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Theme Preview - Cognigate</title>
    <style>{_BASE_STYLE}
    .theme-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 2rem;
        margin-top: 1.5rem;
    }}
    @media (max-width: 900px) {{ .theme-grid {{ grid-template-columns: 1fr; }} }}
    .theme-card {{ transition: transform 0.2s; }}
    .theme-card:hover {{ transform: translateY(-4px); }}

    /* Vote UI */
    .vote-btn {{
        display: inline-flex !important;
        align-items: center;
        gap: 0.3rem;
        padding: 0.35rem 0.75rem !important;
        border-radius: 99px !important;
        font-size: 0.8rem !important;
        background: var(--accent-muted) !important;
        color: var(--accent) !important;
        border: 1px solid var(--border) !important;
        cursor: pointer;
        transition: all 0.2s;
    }}
    .vote-btn:hover {{
        background: var(--accent) !important;
        color: var(--btn-text) !important;
        transform: scale(1.05);
    }}
    .vote-btn.voted {{
        background: var(--accent) !important;
        color: var(--btn-text) !important;
    }}
    .vote-heart {{ font-size: 0.9rem; transition: transform 0.3s; }}
    .vote-btn:hover .vote-heart,
    .vote-btn.voted .vote-heart {{ transform: scale(1.2); }}
    @keyframes vpop {{
        0% {{ transform: scale(1); }}
        50% {{ transform: scale(1.4); }}
        100% {{ transform: scale(1); }}
    }}
    .vote-pop {{ animation: vpop 0.3s ease-out; }}
    .vote-count {{
        font-weight: 700;
        font-size: 0.95rem;
        color: var(--text-heading);
        min-width: 1.5rem;
    }}
    .vote-bar-track {{
        flex: 1;
        height: 6px;
        border-radius: 3px;
        background: var(--bg-surface);
        border: 1px solid var(--border);
        overflow: hidden;
    }}
    .vote-bar-fill {{
        height: 100%;
        border-radius: 3px;
        transition: width 0.4s ease-out;
    }}
    .vote-pct {{
        font-size: 0.75rem;
        color: var(--text-secondary);
        min-width: 2.5rem;
        text-align: right;
    }}

    /* Leaderboard */
    .leaderboard {{
        background: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
    }}
    .leaderboard h3 {{ color: var(--text-heading); font-size: 1rem; margin-bottom: 0.75rem; }}
    .lb-row {{
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border);
    }}
    .lb-row:last-child {{ border-bottom: none; }}
    .lb-rank {{ font-weight: 700; font-size: 1.1rem; min-width: 1.5rem; text-align: center; }}
    .lb-name {{ font-weight: 600; color: var(--text-heading); flex: 1; }}
    .lb-count {{ font-weight: 700; font-size: 1rem; }}
    .lb-bar {{
        width: 120px; height: 6px; border-radius: 3px;
        background: var(--bg-input); overflow: hidden;
    }}
    .lb-bar-fill {{
        height: 100%; border-radius: 3px;
        transition: width 0.4s ease-out;
    }}

    /* Voter input */
    .voter-section {{
        background: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
    }}
    .voter-section label {{ color: var(--text-secondary); font-size: 0.85rem; font-weight: 600; }}
    .voter-section input {{ flex: 1; min-width: 200px; }}
    .total-badge {{
        display: inline-flex; align-items: center; gap: 0.5rem;
        padding: 0.3rem 0.8rem; border-radius: 99px;
        background: var(--accent-muted); border: 1px solid var(--border);
        color: var(--accent); font-size: 0.8rem; font-weight: 600;
    }}

    .how-to {{
        background: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.5rem;
        margin-top: 2rem;
    }}
    .how-to h3 {{ color: var(--text-heading); margin-bottom: 0.75rem; }}
    .how-to ol {{ padding-left: 1.5rem; color: var(--text-secondary); font-size: 0.85rem; line-height: 2; }}
    .how-to code {{ font-size: 0.8rem; }}
    </style>
</head>
<body>
{_NAV_HTML}
<div class="container">
    <h1>Theme Preview</h1>
    <p class="subtitle">Compare all 4 theme options. Vote for your favorite — results update live.</p>

    <!-- Voter name + total -->
    <div class="voter-section">
        <label for="voter-name">Your Name:</label>
        <input type="text" id="voter-name" placeholder="Enter your name to vote" />
        <div class="total-badge">
            <span id="total-votes">{total_votes}</span> total votes
        </div>
    </div>

    <!-- Leaderboard -->
    <div class="leaderboard">
        <h3>Leaderboard</h3>
        <div id="lb-rows">
            <div style="color:var(--text-tertiary);font-size:0.85rem;">Loading...</div>
        </div>
    </div>

    <div class="theme-grid">
        {theme_cards}
    </div>

    <div class="how-to">
        <h3>How to Switch Themes</h3>
        <ol>
            <li><strong>cognigate.dev</strong> — Edit <code>app/theme.py</code>, change <code>ACTIVE_THEME = "midnight_cyan"</code></li>
            <li><strong>vorion.org</strong> — Edit <code>globals.css</code>, swap the CSS variable values in <code>:root</code></li>
            <li>Deploy both sites. That's it.</li>
        </ol>
        <p style="color:var(--text-tertiary);font-size:0.8rem;margin-top:0.75rem;">
            Source of truth: <code>packages/shared-constants/src/themes.ts</code> (TypeScript) and <code>app/theme.py</code> (Python)
        </p>
    </div>
</div>
<script>
const themeAccents = {{ {accents_js} }};
const themeNames = {{ {names_js} }};

function getVoterName() {{
    return document.getElementById('voter-name').value.trim() || 'anonymous';
}}

async function castVote(themeId) {{
    const btn = document.querySelector('#card-' + themeId + ' .vote-btn');
    const heart = btn.querySelector('.vote-heart');

    heart.classList.remove('vote-pop');
    void heart.offsetWidth;
    heart.classList.add('vote-pop');
    btn.classList.add('voted');

    try {{
        const res = await fetch('/v1/themes/vote', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ theme_id: themeId, voter: getVoterName() }})
        }});
        const data = await res.json();
        if (data.totals) updateVoteCounts(data.totals);
    }} catch (e) {{
        console.error('Vote failed:', e);
    }}

    setTimeout(() => btn.classList.remove('voted'), 1000);
}}

function updateVoteCounts(totals) {{
    const total = Object.values(totals).reduce((a, b) => a + b, 0);
    document.getElementById('total-votes').textContent = total;

    for (const [tid, count] of Object.entries(totals)) {{
        const pct = total > 0 ? Math.round(count / total * 100) : 0;
        const countEl = document.getElementById('count-' + tid);
        const barEl = document.getElementById('bar-' + tid);
        const pctEl = document.getElementById('pct-' + tid);
        if (countEl) countEl.textContent = count;
        if (barEl) barEl.style.width = pct + '%';
        if (pctEl) pctEl.textContent = pct + '%';
    }}

    for (const tid of Object.keys(themeNames)) {{
        if (!(tid in totals)) {{
            const countEl = document.getElementById('count-' + tid);
            const barEl = document.getElementById('bar-' + tid);
            const pctEl = document.getElementById('pct-' + tid);
            if (countEl) countEl.textContent = '0';
            if (barEl) barEl.style.width = '0%';
            if (pctEl) pctEl.textContent = '0%';
        }}
    }}

    updateLeaderboard(totals, total);
}}

function updateLeaderboard(totals, total) {{
    const ranked = Object.entries(themeNames)
        .map(([tid, name]) => ({{ tid, name, count: totals[tid] || 0 }}))
        .sort((a, b) => b.count - a.count);

    const medals = ['\U0001F947', '\U0001F948', '\U0001F949', '4'];
    const maxCount = ranked[0]?.count || 1;

    let html = '';
    ranked.forEach((r, i) => {{
        const pct = total > 0 ? Math.round(r.count / total * 100) : 0;
        const barW = maxCount > 0 ? Math.round(r.count / maxCount * 100) : 0;
        html += '<div class="lb-row">'
            + '<div class="lb-rank">' + medals[i] + '</div>'
            + '<div class="lb-name">' + r.name + '</div>'
            + '<div class="lb-bar"><div class="lb-bar-fill" style="width:' + barW + '%;background:' + themeAccents[r.tid] + ';"></div></div>'
            + '<div class="lb-count" style="color:' + themeAccents[r.tid] + ';">' + r.count + '</div>'
            + '<div class="vote-pct">' + pct + '%</div>'
            + '</div>';
    }});
    document.getElementById('lb-rows').innerHTML = html;
}}

async function loadVotes() {{
    try {{
        const res = await fetch('/v1/themes/votes');
        const data = await res.json();
        const totals = {{}};
        for (const [tid, info] of Object.entries(data.themes)) {{
            totals[tid] = info.count;
        }}
        updateVoteCounts(totals);
    }} catch (e) {{
        console.error('Failed to load votes:', e);
    }}
}}

loadVotes();
setInterval(loadVotes, 10000);
document.getElementById('nav-themes')?.classList.add('active');
</script>
</body>
</html>"""
