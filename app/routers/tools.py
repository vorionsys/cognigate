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

router = APIRouter()

# =============================================================================
# SHARED STYLES
# =============================================================================

_BASE_STYLE = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
        background: #0a0a0f;
        color: #e0e0e6;
        min-height: 100vh;
    }
    a { color: #06b6d4; text-decoration: none; }
    a:hover { text-decoration: underline; }

    .nav {
        display: flex;
        gap: 1.5rem;
        padding: 1rem 2rem;
        background: #111118;
        border-bottom: 1px solid #1e1e2e;
        align-items: center;
        flex-wrap: wrap;
    }
    .nav-brand {
        font-weight: 700;
        font-size: 1.1rem;
        color: #06b6d4;
        margin-right: auto;
    }
    .nav a {
        color: #888;
        font-size: 0.85rem;
        padding: 0.3rem 0.6rem;
        border-radius: 4px;
        transition: all 0.2s;
    }
    .nav a:hover, .nav a.active {
        color: #06b6d4;
        background: rgba(6,182,212,0.1);
        text-decoration: none;
    }

    .container { max-width: 1100px; margin: 0 auto; padding: 2rem; }
    h1 { font-size: 1.8rem; margin-bottom: 0.5rem; color: #fff; }
    h2 { font-size: 1.3rem; margin: 1.5rem 0 0.75rem; color: #ccc; }
    .subtitle { color: #888; margin-bottom: 2rem; }

    .card {
        background: #111118;
        border: 1px solid #1e1e2e;
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    input, select, button {
        font-family: inherit;
        font-size: 0.9rem;
        border: 1px solid #2a2a3a;
        background: #0d0d14;
        color: #e0e0e6;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
    }
    input:focus, select:focus { outline: none; border-color: #06b6d4; }
    button {
        background: #06b6d4;
        color: #000;
        border: none;
        cursor: pointer;
        font-weight: 600;
        transition: background 0.2s;
    }
    button:hover { background: #22d3ee; }

    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }
    th, td {
        text-align: left;
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid #1e1e2e;
    }
    th { color: #888; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }
    tr:hover td { background: rgba(6,182,212,0.03); }

    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }

    code {
        background: #1a1a24;
        padding: 0.15rem 0.4rem;
        border-radius: 3px;
        font-size: 0.85rem;
    }
    pre {
        background: #0d0d14;
        border: 1px solid #1e1e2e;
        border-radius: 6px;
        padding: 1rem;
        overflow-x: auto;
        font-size: 0.8rem;
        line-height: 1.5;
        margin: 0.75rem 0;
    }
    pre code { background: none; padding: 0; }
    .copy-btn {
        float: right;
        font-size: 0.7rem;
        padding: 0.2rem 0.5rem;
        background: #2a2a3a;
        color: #888;
    }
    .copy-btn:hover { background: #3a3a4a; color: #fff; }
"""

_NAV_HTML = """
<nav class="nav">
    <span class="nav-brand">Cognigate</span>
    <a href="/docs">API Docs</a>
    <a href="/tools/calculator" id="nav-calc">Trust Calculator</a>
    <a href="/tools/errors" id="nav-errors">Error Codes</a>
    <a href="/tools/sdks" id="nav-sdks">SDKs</a>
    <a href="/tools/playground" id="nav-playground">Playground</a>
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
