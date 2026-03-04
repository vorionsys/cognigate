"""
Upstream Client for Gateway Bridge

HTTP client (httpx) for forwarding requests to Vorion API.
Includes circuit breaker, retry logic, and auth propagation.
"""

from __future__ import annotations

import time
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitBreaker:
    """Simple circuit breaker to protect against upstream failures."""

    def __init__(self, threshold: int = 5, reset_timeout: float = 60.0):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.state = "closed"  # closed = healthy, open = tripped, half_open = testing

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.threshold:
            self.state = "open"
            logger.warning(
                "Circuit breaker OPEN after %d failures", self.failure_count
            )

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.reset_timeout:
                self.state = "half_open"
                return True
            return False
        # half_open — allow one test request
        return True


# =============================================================================
# UPSTREAM CLIENT
# =============================================================================

_circuit_breaker = CircuitBreaker()


async def forward_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: Any = None,
    params: dict[str, str] | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """
    Forward a request to the Vorion upstream API.

    Returns a dict with:
    - status: HTTP status code
    - data: Response JSON (or error dict)
    - headers: Response headers
    """
    settings = get_settings()

    if not _circuit_breaker.allow_request():
        return {
            "status": 503,
            "data": {
                "error": "Circuit breaker is open. Upstream service may be down.",
                "code": "E7002",
            },
            "headers": {},
        }

    url = f"{settings.vorion_api_url}{path}"
    req_headers = dict(headers or {})

    # Propagate API key
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"

    req_timeout = timeout or (settings.gateway_timeout_ms / 1000.0)

    try:
        async with httpx.AsyncClient(timeout=req_timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=req_headers,
                json=body if method.upper() in ("POST", "PUT", "PATCH") else None,
                params=params,
            )

        _circuit_breaker.record_success()

        try:
            data = response.json()
        except (ValueError, KeyError) as exc:
            logger.warning("upstream_response_parse_error: %s", str(exc))
            data = {"raw": response.text}

        return {
            "status": response.status_code,
            "data": data,
            "headers": dict(response.headers),
        }

    except httpx.TimeoutException:
        _circuit_breaker.record_failure()
        logger.error("Gateway timeout for %s %s", method, path)
        return {
            "status": 504,
            "data": {"error": "Gateway timeout", "code": "E7002"},
            "headers": {},
        }
    except httpx.ConnectError:
        _circuit_breaker.record_failure()
        logger.error("Gateway connection error for %s %s", method, path)
        return {
            "status": 502,
            "data": {"error": "Upstream connection failed", "code": "E7003"},
            "headers": {},
        }
    except Exception as exc:
        _circuit_breaker.record_failure()
        logger.error("Gateway error for %s %s: %s", method, path, exc)
        return {
            "status": 502,
            "data": {"error": f"Gateway error: {type(exc).__name__}", "code": "E7003"},
            "headers": {},
        }


def get_circuit_breaker_status() -> dict[str, Any]:
    """Get current circuit breaker status."""
    return {
        "state": _circuit_breaker.state,
        "failureCount": _circuit_breaker.failure_count,
        "threshold": _circuit_breaker.threshold,
    }
