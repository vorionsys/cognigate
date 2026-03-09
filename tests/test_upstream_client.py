# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the upstream HTTP client and circuit breaker.
"""

import time
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.core.upstream_client import (
    CircuitBreaker,
    forward_request,
    get_circuit_breaker_status,
    _circuit_breaker,
)


class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    def setup_method(self):
        self.cb = CircuitBreaker(threshold=3, reset_timeout=1.0)

    def test_initial_state_closed(self):
        assert self.cb.state == "closed"
        assert self.cb.failure_count == 0

    def test_allow_request_when_closed(self):
        assert self.cb.allow_request() is True

    def test_record_success_resets(self):
        self.cb.failure_count = 2
        self.cb.state = "half_open"
        self.cb.record_success()
        assert self.cb.failure_count == 0
        assert self.cb.state == "closed"

    def test_record_failure_increments(self):
        self.cb.record_failure()
        assert self.cb.failure_count == 1
        assert self.cb.state == "closed"

    def test_record_failure_opens_at_threshold(self):
        for _ in range(3):
            self.cb.record_failure()
        assert self.cb.state == "open"
        assert self.cb.failure_count == 3

    def test_open_blocks_requests(self):
        for _ in range(3):
            self.cb.record_failure()
        assert self.cb.allow_request() is False

    def test_open_transitions_to_half_open_after_timeout(self):
        for _ in range(3):
            self.cb.record_failure()
        # Manually set last_failure_time to the past
        self.cb.last_failure_time = time.time() - 2.0
        assert self.cb.allow_request() is True
        assert self.cb.state == "half_open"

    def test_half_open_allows_one_request(self):
        self.cb.state = "half_open"
        assert self.cb.allow_request() is True


@pytest.mark.anyio
class TestForwardRequest:
    """Test upstream HTTP forwarding."""

    def setup_method(self):
        # Reset the global circuit breaker before each test
        _circuit_breaker.failure_count = 0
        _circuit_breaker.state = "closed"

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_successful_get(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await forward_request("GET", "/v1/test")
        assert result["status"] == 200
        assert result["data"] == {"ok": True}

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_post_with_body(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"created": True}
        mock_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await forward_request("POST", "/v1/create", body={"name": "test"})
        assert result["status"] == 201

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_api_key_propagation(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_resp.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await forward_request("GET", "/v1/test", api_key="sk-test")
        call_kwargs = mock_client.request.call_args
        assert "Authorization" in call_kwargs.kwargs["headers"]
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer sk-test"

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_timeout_returns_504(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await forward_request("GET", "/v1/slow")
        assert result["status"] == 504
        assert "timeout" in result["data"]["error"].lower()

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_connect_error_returns_502(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await forward_request("GET", "/v1/down")
        assert result["status"] == 502
        assert "connection" in result["data"]["error"].lower()

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_generic_error_returns_502(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.request.side_effect = RuntimeError("boom")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await forward_request("GET", "/v1/broken")
        assert result["status"] == 502
        assert "RuntimeError" in result["data"]["error"]

    @patch("app.core.upstream_client.httpx.AsyncClient")
    async def test_non_json_response(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("not json")
        mock_resp.text = "plain text response"
        mock_resp.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await forward_request("GET", "/v1/text")
        assert result["status"] == 200
        assert result["data"]["raw"] == "plain text response"

    async def test_circuit_breaker_open_returns_503(self):
        _circuit_breaker.state = "open"
        _circuit_breaker.last_failure_time = time.time()  # recent failure
        result = await forward_request("GET", "/v1/anything")
        assert result["status"] == 503
        assert "circuit breaker" in result["data"]["error"].lower()
        # Reset
        _circuit_breaker.state = "closed"
        _circuit_breaker.failure_count = 0


def test_get_circuit_breaker_status():
    _circuit_breaker.state = "closed"
    _circuit_breaker.failure_count = 0
    status = get_circuit_breaker_status()
    assert status["state"] == "closed"
    assert status["failureCount"] == 0
    assert status["threshold"] == _circuit_breaker.threshold
