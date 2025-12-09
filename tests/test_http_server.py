"""Tests for the HTTP server module."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from unity_mcp.config import Config, ServerConfig, UnityConfig
from unity_mcp.http_server import (
    CORSMiddleware,
    MCPHttpServer,
    ServerMetrics,
    create_app,
)


@pytest.fixture
def mock_config(temp_openapi_file) -> Config:
    """Create a mock configuration.

    Args:
        temp_openapi_file: Temporary OpenAPI spec file fixture.

    Returns:
        Mock configuration object.
    """
    return Config(
        unity=UnityConfig(
            host="example.com",
            local_spec_path=str(temp_openapi_file),
        ),
        server=ServerConfig(
            port=3000,
            log_level="DEBUG",
        ),
    )


class TestServerMetrics:
    """Tests for the ServerMetrics class."""

    def test_metrics_initialization(self) -> None:
        """Test metrics initialization."""
        metrics = ServerMetrics()

        assert metrics.requests_total == 0
        assert metrics.errors_total == 0
        assert metrics.active_connections == 0
        assert metrics.uptime_seconds >= 0

    def test_record_request(self) -> None:
        """Test recording requests."""
        metrics = ServerMetrics()

        metrics.record_request("/health")
        metrics.record_request("/health")
        metrics.record_request("/sse")

        assert metrics.requests_total == 3
        assert metrics.requests_by_path["/health"] == 2
        assert metrics.requests_by_path["/sse"] == 1

    def test_record_error(self) -> None:
        """Test recording errors."""
        metrics = ServerMetrics()

        metrics.record_error()
        metrics.record_error()

        assert metrics.errors_total == 2

    def test_connection_tracking(self) -> None:
        """Test connection tracking."""
        metrics = ServerMetrics()

        metrics.connection_opened()
        metrics.connection_opened()
        assert metrics.active_connections == 2

        metrics.connection_closed()
        assert metrics.active_connections == 1

        metrics.connection_closed()
        metrics.connection_closed()  # Should not go negative
        assert metrics.active_connections == 0

    def test_to_dict(self) -> None:
        """Test metrics serialization."""
        metrics = ServerMetrics()
        metrics.record_request("/health")
        metrics.record_error()

        data = metrics.to_dict()

        assert "uptime_seconds" in data
        assert data["requests_total"] == 1
        assert data["errors_total"] == 1


class TestMCPHttpServer:
    """Tests for the MCPHttpServer class."""

    @pytest.mark.asyncio
    async def test_server_initialization(self, mock_config: Config) -> None:
        """Test HTTP server initialization."""
        server = MCPHttpServer(mock_config)

        assert not server.is_initialized

        await server.initialize()

        assert server.is_initialized
        assert len(server.mcp_server.tools) > 0

    @pytest.mark.asyncio
    async def test_health_endpoint(self, mock_config: Config) -> None:
        """Test the health endpoint."""
        server = MCPHttpServer(mock_config)
        await server.initialize()

        # Mock ASGI components
        scope = {"type": "http", "path": "/health", "method": "GET"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        # Check that response was sent
        calls = send.call_args_list
        assert len(calls) >= 2

        # First call should be response.start
        start_call = calls[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 200

        # Second call should be response.body
        body_call = calls[1][0][0]
        assert body_call["type"] == "http.response.body"

        response_data = json.loads(body_call["body"])
        assert response_data["status"] == "healthy"
        assert "tools" in response_data
        assert "uptime_seconds" in response_data

    @pytest.mark.asyncio
    async def test_ready_endpoint_when_ready(self, mock_config: Config) -> None:
        """Test the ready endpoint when server is ready."""
        server = MCPHttpServer(mock_config)
        await server.initialize()

        scope = {"type": "http", "path": "/ready", "method": "GET"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        start_call = send.call_args_list[0][0][0]
        assert start_call["status"] == 200

    @pytest.mark.asyncio
    async def test_ready_endpoint_when_not_ready(self, mock_config: Config) -> None:
        """Test the ready endpoint when server is not ready."""
        server = MCPHttpServer(mock_config)
        # Don't initialize

        scope = {"type": "http", "path": "/ready", "method": "GET"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        start_call = send.call_args_list[0][0][0]
        assert start_call["status"] == 503

    @pytest.mark.asyncio
    async def test_live_endpoint(self, mock_config: Config) -> None:
        """Test the liveness endpoint."""
        server = MCPHttpServer(mock_config)

        scope = {"type": "http", "path": "/live", "method": "GET"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        start_call = send.call_args_list[0][0][0]
        assert start_call["status"] == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, mock_config: Config) -> None:
        """Test the metrics endpoint."""
        server = MCPHttpServer(mock_config)
        await server.initialize()

        scope = {"type": "http", "path": "/metrics", "method": "GET"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        body_call = send.call_args_list[1][0][0]
        response_data = json.loads(body_call["body"])

        assert "uptime_seconds" in response_data
        assert "requests_total" in response_data

    @pytest.mark.asyncio
    async def test_not_found_endpoint(self, mock_config: Config) -> None:
        """Test 404 for unknown endpoints."""
        server = MCPHttpServer(mock_config)
        await server.initialize()

        scope = {"type": "http", "path": "/unknown", "method": "GET"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        start_call = send.call_args_list[0][0][0]
        assert start_call["status"] == 404

        body_call = send.call_args_list[1][0][0]
        response_data = json.loads(body_call["body"])
        assert "available_endpoints" in response_data

    @pytest.mark.asyncio
    async def test_cors_preflight(self, mock_config: Config) -> None:
        """Test CORS preflight handling."""
        server = MCPHttpServer(mock_config)

        scope = {"type": "http", "path": "/sse", "method": "OPTIONS"}
        receive = AsyncMock()
        send = AsyncMock()

        await server(scope, receive, send)

        start_call = send.call_args_list[0][0][0]
        assert start_call["status"] == 204

        headers = dict(start_call["headers"])
        assert b"access-control-allow-origin" in headers


class TestCORSMiddleware:
    """Tests for the CORSMiddleware class."""

    @pytest.mark.asyncio
    async def test_cors_headers_added(self) -> None:
        """Test that CORS headers are added to responses."""
        # Create a simple app that sends a response
        async def test_app(
            scope: dict[str, Any],
            receive: Callable[[], Awaitable[dict[str, Any]]],
            send: Callable[[dict[str, Any]], Awaitable[None]],
        ) -> None:
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"OK",
            })

        middleware = CORSMiddleware(test_app)

        scope = {"type": "http"}
        receive = AsyncMock()
        sent_messages: list[dict[str, Any]] = []

        async def capture_send(message: dict[str, Any]) -> None:
            sent_messages.append(message)

        await middleware(scope, receive, capture_send)

        # Check that CORS headers were added
        start_message = sent_messages[0]
        headers = dict(start_message["headers"])
        assert b"access-control-allow-origin" in headers

    @pytest.mark.asyncio
    async def test_cors_passthrough_for_non_http(self) -> None:
        """Test that non-HTTP requests pass through unchanged."""
        call_count = {"value": 0}

        async def test_app(
            scope: dict[str, Any],
            receive: Callable[[], Awaitable[dict[str, Any]]],
            send: Callable[[dict[str, Any]], Awaitable[None]],
        ) -> None:
            call_count["value"] += 1

        middleware = CORSMiddleware(test_app)

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        assert call_count["value"] == 1


class TestCreateApp:
    """Tests for the create_app function."""

    def test_create_app_with_config(self, mock_config: Config) -> None:
        """Test creating app with explicit config."""
        app = create_app(mock_config)
        assert app is not None

    def test_create_app_without_config(self, mock_env_vars: None) -> None:
        """Test creating app without config (loads from env)."""
        app = create_app()
        assert app is not None
