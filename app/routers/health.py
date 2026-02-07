"""
Health check endpoints.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check if the Cognigate Engine is healthy.
    """
    return HealthResponse(
        status="healthy",
        service="cognigate-engine",
        version="0.1.0",
        timestamp=datetime.utcnow(),
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """
    Check if the service is ready to accept requests.
    """
    return {"status": "ready"}


@router.get("/status", response_class=HTMLResponse)
async def status_page() -> str:
    """
    Public status dashboard with real-time metrics.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognigate Status | Governance Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🛡️</text></svg>">
    <style>
        body { background: #0a0a0a; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse { animation: pulse 2s infinite; }
    </style>
</head>
<body class="min-h-screen text-white font-sans">
    <div class="max-w-4xl mx-auto px-4 py-12">
        <!-- Header -->
        <div class="flex items-center gap-4 mb-8">
            <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-2xl">
                🛡️
            </div>
            <div>
                <h1 class="text-2xl font-bold">Cognigate Engine</h1>
                <p class="text-zinc-400 text-sm">Trust-Enforced Cognition Runtime</p>
            </div>
        </div>

        <!-- Overall Status -->
        <div id="overall-status" class="flex items-center gap-3 px-5 py-4 rounded-xl bg-zinc-900 border border-zinc-800 mb-8">
            <span id="status-dot" class="w-3 h-3 rounded-full bg-zinc-600"></span>
            <span id="status-text" class="font-medium text-zinc-400">Loading...</span>
            <span class="text-zinc-600 text-sm ml-auto">Last updated: <span id="last-update">—</span></span>
            <button onclick="refresh()" class="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
                <svg id="refresh-icon" class="w-4 h-4 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
            </button>
        </div>

        <!-- Stats Grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-1">Circuit Breaker</div>
                <div id="circuit-state" class="text-xl font-bold">—</div>
            </div>
            <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-1">Total Requests</div>
                <div id="total-requests" class="text-xl font-bold">—</div>
            </div>
            <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-1">Blocked</div>
                <div id="blocked-requests" class="text-xl font-bold">—</div>
            </div>
            <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-1">High Risk Ratio</div>
                <div id="high-risk" class="text-xl font-bold">—</div>
            </div>
        </div>

        <!-- Security Layers -->
        <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">Security Layers</h2>
            <div id="security-layers" class="space-y-3">
                <div class="text-zinc-500">Loading...</div>
            </div>
        </div>

        <!-- Proof Chain Stats -->
        <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">Proof Chain</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <div class="text-xs text-zinc-500 uppercase mb-1">Total Records</div>
                    <div id="proof-total" class="text-2xl font-bold">—</div>
                </div>
                <div>
                    <div class="text-xs text-zinc-500 uppercase mb-1">Chain Length</div>
                    <div id="proof-length" class="text-2xl font-bold">—</div>
                </div>
                <div>
                    <div class="text-xs text-zinc-500 uppercase mb-1">Integrity</div>
                    <div id="proof-integrity" class="text-2xl font-bold">—</div>
                </div>
                <div>
                    <div class="text-xs text-zinc-500 uppercase mb-1">Last Record</div>
                    <div id="proof-last" class="text-sm text-zinc-400">—</div>
                </div>
            </div>
        </div>

        <!-- Decision Breakdown -->
        <div class="bg-zinc-900 rounded-xl border border-zinc-800 p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">Decisions by Type</h2>
            <div id="decisions" class="flex flex-wrap gap-3">
                <div class="text-zinc-500">Loading...</div>
            </div>
        </div>

        <!-- Footer -->
        <div class="text-center text-zinc-600 text-sm">
            <p>Cognigate Engine v0.1.0 | <a href="https://vorion.org" class="text-cyan-500 hover:underline">VORION</a></p>
            <p class="mt-1">Part of the <a href="https://vorion.org/basis" class="text-cyan-500 hover:underline">BASIS</a> governance standard</p>
        </div>
    </div>

    <script>
        async function refresh() {
            document.getElementById('refresh-icon').classList.add('animate-spin');
            await Promise.all([fetchStatus(), fetchProofStats()]);
            document.getElementById('refresh-icon').classList.remove('animate-spin');
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }

        async function fetchStatus() {
            try {
                const res = await fetch('/v1/admin/status');
                const data = await res.json();

                // Overall status
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                if (data.health === 'healthy') {
                    dot.className = 'w-3 h-3 rounded-full bg-emerald-400';
                    text.className = 'font-medium text-emerald-400';
                    text.textContent = data.health_message;
                } else if (data.health === 'warning' || data.health === 'degraded') {
                    dot.className = 'w-3 h-3 rounded-full bg-amber-400 pulse';
                    text.className = 'font-medium text-amber-400';
                    text.textContent = data.health_message;
                } else {
                    dot.className = 'w-3 h-3 rounded-full bg-red-400 pulse';
                    text.className = 'font-medium text-red-400';
                    text.textContent = data.health_message;
                }

                // Circuit breaker
                const cb = data.circuit_breaker || {};
                const state = document.getElementById('circuit-state');
                state.textContent = cb.state || '—';
                state.className = cb.state === 'CLOSED' ? 'text-xl font-bold text-emerald-400' :
                                  cb.state === 'HALF_OPEN' ? 'text-xl font-bold text-amber-400' :
                                  'text-xl font-bold text-red-400';

                // Metrics
                const metrics = cb.metrics || {};
                document.getElementById('total-requests').textContent = (metrics.total_requests || 0).toLocaleString();
                document.getElementById('blocked-requests').textContent = (metrics.blocked_requests || 0).toLocaleString();
                document.getElementById('high-risk').textContent = ((metrics.high_risk_ratio || 0) * 100).toFixed(1) + '%';

                // Security layers
                const layers = data.security_layers || {};
                const layersHtml = Object.entries(layers).map(([name, status]) => `
                    <div class="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0">
                        <span class="text-zinc-300">${name}</span>
                        <span class="${status.includes('active') ? 'text-emerald-400' : 'text-zinc-500'}">${status}</span>
                    </div>
                `).join('');
                document.getElementById('security-layers').innerHTML = layersHtml || '<div class="text-zinc-500">No layers data</div>';

            } catch (e) {
                console.error('Failed to fetch status:', e);
            }
        }

        async function fetchProofStats() {
            try {
                const res = await fetch('/v1/proof/stats');
                const data = await res.json();

                document.getElementById('proof-total').textContent = (data.total_records || 0).toLocaleString();
                document.getElementById('proof-length').textContent = (data.chain_length || 0).toLocaleString();

                const integrity = document.getElementById('proof-integrity');
                if (data.chain_integrity === true) {
                    integrity.textContent = 'Valid';
                    integrity.className = 'text-2xl font-bold text-emerald-400';
                } else if (data.chain_integrity === false) {
                    integrity.textContent = 'Invalid';
                    integrity.className = 'text-2xl font-bold text-red-400';
                } else {
                    integrity.textContent = '—';
                }

                if (data.last_record_at) {
                    document.getElementById('proof-last').textContent = new Date(data.last_record_at).toLocaleString();
                }

                // Decisions
                const decisions = data.records_by_decision || {};
                const decisionsHtml = Object.entries(decisions).map(([decision, count]) => {
                    const colors = {
                        allowed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
                        denied: 'bg-red-500/20 text-red-400 border-red-500/30',
                        escalated: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
                        modified: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
                    };
                    const color = colors[decision] || 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
                    return `<div class="px-4 py-2 rounded-lg border ${color}">
                        <span class="font-semibold">${count}</span>
                        <span class="text-xs ml-1 opacity-75">${decision}</span>
                    </div>`;
                }).join('');
                document.getElementById('decisions').innerHTML = decisionsHtml || '<div class="text-zinc-500">No decisions recorded</div>';

            } catch (e) {
                console.error('Failed to fetch proof stats:', e);
            }
        }

        // Initial load
        refresh();
        // Auto-refresh every 30 seconds
        setInterval(refresh, 30000);
    </script>
</body>
</html>"""
