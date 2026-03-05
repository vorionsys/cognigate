"""
Gateway Router

Proxies requests to the Vorion API, making cognigate.dev the single
developer entry point for the entire governance platform.

Routes are grouped by domain:
- /v1/gateway/compliance/*    -> Vorion compliance routes
- /v1/gateway/council/*       -> Council governance
- /v1/gateway/observer/*      -> Behavioral monitoring
- /v1/gateway/truth-chain/*   -> Immutable audit trail
- /v1/gateway/academy/*       -> Agent training
- /v1/gateway/orchestrator/*  -> Multi-agent coordination
- /v1/gateway/webhooks/*      -> Event notifications
- /v1/gateway/dashboard/*     -> Analytics and metrics
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.upstream_client import forward_request, get_circuit_breaker_status

logger = logging.getLogger(__name__)

router = APIRouter()

# All gateway domain prefixes
GATEWAY_DOMAINS = [
    "compliance",
    "council",
    "observer",
    "truth-chain",
    "academy",
    "orchestrator",
    "webhooks",
    "dashboard",
]


@router.get("/gateway/status", summary="Gateway health and circuit breaker status")
async def gateway_status() -> dict:
    """
    Check the gateway's connection status to the Vorion upstream API,
    including circuit breaker state.
    """
    cb = get_circuit_breaker_status()
    return {
        "gateway": "operational",
        "circuitBreaker": cb,
        "domains": GATEWAY_DOMAINS,
    }


@router.api_route(
    "/gateway/{domain}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    summary="Proxy to Vorion API",
)
async def gateway_proxy(domain: str, path: str, request: Request) -> JSONResponse:
    """
    Forward requests to the Vorion upstream API.

    The domain must be one of: compliance, council, observer, truth-chain,
    academy, orchestrator, webhooks, dashboard.

    All request headers, query parameters, and body are forwarded.
    API key authentication is propagated via the Authorization header.
    """
    if domain not in GATEWAY_DOMAINS:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Unknown gateway domain: {domain}",
                "availableDomains": GATEWAY_DOMAINS,
            },
        )

    # Extract API key from request
    api_key = (
        request.headers.get("Authorization", "").replace("Bearer ", "")
        or request.headers.get("X-API-Key")
    )

    # Read body for POST/PUT/PATCH
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            logger.warning(
                "gateway_request_body_parse_failed",
                extra={"method": request.method, "domain": domain, "path": path},
            )
            body = None

    # Build upstream path
    upstream_path = f"/v1/{domain}/{path}" if path else f"/v1/{domain}"

    # Forward headers (filter out host/connection)
    forward_headers = {}
    for key, value in request.headers.items():
        if key.lower() not in ("host", "connection", "content-length", "transfer-encoding"):
            forward_headers[key] = value

    result = await forward_request(
        method=request.method,
        path=upstream_path,
        headers=forward_headers,
        body=body,
        params=dict(request.query_params),
        api_key=api_key,
    )

    return JSONResponse(
        status_code=result["status"],
        content=result["data"],
    )
