"""HTTP server with CORS support and MCP SSE transport.

This module creates a pure ASGI application that properly handles
MCP's SSE transport without Starlette's Route abstraction conflicts.

The server provides:
    - SSE endpoint for MCP communication (/sse)
    - Health check endpoints (/health, /ready, /live)
    - CORS support for cross-origin requests

Example:
    Running with uvicorn::

        $ uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 3000

    Using programmatically::

        from unity_mcp.http_server import create_app
        from unity_mcp.config import load_config

        config = load_config()
        app = create_app(config)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport

from .config import Config, load_config
from .logging_config import get_logger, setup_logging
from .server import UnityMCPServer

logger = get_logger(__name__)

# Type alias for ASGI app
ASGIApp = Callable[[dict, Callable, Callable], Awaitable[None]]


class ServerMetrics:
    """Simple metrics collector for the MCP server.

    Tracks basic operational metrics for monitoring and debugging.

    Attributes:
        start_time: Server start timestamp.
        requests_total: Total number of requests handled.
        requests_by_path: Request count by path.
        errors_total: Total number of errors.
        active_connections: Current number of active SSE connections.
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.start_time: float = time.time()
        self.requests_total: int = 0
        self.requests_by_path: dict[str, int] = {}
        self.errors_total: int = 0
        self.active_connections: int = 0
        self._tool_calls: dict[str, int] = {}

    def record_request(self, path: str) -> None:
        """Record a request.

        Args:
            path: Request path.
        """
        self.requests_total += 1
        self.requests_by_path[path] = self.requests_by_path.get(path, 0) + 1

    def record_error(self) -> None:
        """Record an error."""
        self.errors_total += 1

    def record_tool_call(self, tool_name: str) -> None:
        """Record a tool call.

        Args:
            tool_name: Name of the tool called.
        """
        self._tool_calls[tool_name] = self._tool_calls.get(tool_name, 0) + 1

    def connection_opened(self) -> None:
        """Record a new SSE connection."""
        self.active_connections += 1

    def connection_closed(self) -> None:
        """Record an SSE connection close."""
        self.active_connections = max(0, self.active_connections - 1)

    @property
    def uptime_seconds(self) -> float:
        """Get server uptime in seconds.

        Returns:
            Uptime in seconds.
        """
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary of metrics.
        """
        return {
            "uptime_seconds": round(self.uptime_seconds, 2),
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "active_connections": self.active_connections,
            "requests_by_path": self.requests_by_path,
            "tool_calls": self._tool_calls,
        }


class MCPHttpServer:
    """Pure ASGI HTTP server for MCP with SSE transport.

    This avoids Starlette's Route abstraction which requires returning
    Response objects - incompatible with MCP's SSE transport that
    manages responses directly via ASGI.

    Attributes:
        config: Server configuration.
        mcp_server: Unity MCP server instance.
        sse_transport: SSE transport for MCP communication.
        metrics: Server metrics collector.

    Example:
        >>> config = load_config()
        >>> server = MCPHttpServer(config)
        >>> await server.initialize()
        >>> # Use as ASGI app
    """

    VERSION = "1.0.0"

    def __init__(self, config: Config) -> None:
        """Initialize the HTTP server.

        Args:
            config: Server configuration.
        """
        self.config = config
        self.mcp_server = UnityMCPServer(config)
        self.sse_transport = SseServerTransport("/messages")
        self.metrics = ServerMetrics()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the server has been initialized.

        Returns:
            True if initialized, False otherwise.
        """
        return self._initialized

    async def initialize(self) -> None:
        """Initialize the MCP server."""
        if not self._initialized:
            await self.mcp_server.initialize()
            self._initialized = True
            logger.info(
                "HTTP server initialized",
                extra={"tool_count": len(self.mcp_server.tools)},
            )

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """ASGI entry point - routes requests to appropriate handlers.

        Args:
            scope: ASGI scope dictionary.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        if scope["type"] != "http":
            return

        path = scope["path"]
        method = scope["method"]

        # Record metrics
        self.metrics.record_request(path)

        # Route requests
        try:
            if path == "/health" and method == "GET":
                await self._handle_health(scope, receive, send)
            elif path == "/ready" and method == "GET":
                await self._handle_ready(scope, receive, send)
            elif path == "/live" and method == "GET":
                await self._handle_live(scope, receive, send)
            elif path == "/metrics" and method == "GET":
                await self._handle_metrics(scope, receive, send)
            elif path == "/sse" and method == "GET":
                await self._handle_sse(scope, receive, send)
            elif path == "/messages" and method == "POST":
                await self._handle_messages(scope, receive, send)
            elif path in ("/messages", "/sse") and method == "OPTIONS":
                await self._handle_cors_preflight(scope, receive, send)
            else:
                await self._handle_not_found(scope, receive, send)
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Request handler error: {e}", exc_info=True)
            await self._handle_error(scope, receive, send, e)

    async def _handle_lifespan(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Handle ASGI lifespan events.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    # Set up logging
                    setup_logging(
                        log_level=self.config.server.log_level,
                        json_format=self.config.server.log_json,
                        log_file=self.config.server.log_file,
                    )
                    await self.initialize()
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    logger.error(f"Startup failed: {e}")
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
            elif message["type"] == "lifespan.shutdown":
                logger.info("Shutting down HTTP server")
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _handle_health(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Health check endpoint with detailed status.

        Returns comprehensive health information including:
        - Server status
        - Tool count
        - Uptime
        - Version
        """
        health_data = {
            "status": "healthy" if self._initialized else "starting",
            "version": self.VERSION,
            "mode": "credential-free",
            "transport": "SSE",
            "endpoint": "/sse",
            "tools": len(self.mcp_server.tools) if self._initialized else 0,
            "uptime_seconds": round(self.metrics.uptime_seconds, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self._send_json_response(send, 200, health_data)

    async def _handle_ready(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Kubernetes readiness probe.

        Returns 200 if the server is ready to accept requests,
        503 otherwise.
        """
        if self._initialized and len(self.mcp_server.tools) > 0:
            await self._send_json_response(
                send, 200, {"status": "ready", "tools": len(self.mcp_server.tools)}
            )
        else:
            await self._send_json_response(
                send, 503, {"status": "not_ready", "reason": "Server not initialized"}
            )

    async def _handle_live(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Kubernetes liveness probe.

        Always returns 200 if the process is running.
        """
        await self._send_json_response(send, 200, {"status": "alive"})

    async def _handle_metrics(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Metrics endpoint for monitoring."""
        await self._send_json_response(send, 200, self.metrics.to_dict())

    async def _handle_sse(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Handle SSE connection - MCP transport manages response directly.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        self.metrics.connection_opened()
        logger.info("SSE connection opened")

        try:
            async with self.sse_transport.connect_sse(scope, receive, send) as streams:
                await self.mcp_server.server.run(
                    streams[0],
                    streams[1],
                    InitializationOptions(
                        server_name="dell-unity-mcp-server",
                        server_version=self.VERSION,
                        capabilities=self.mcp_server.server.get_capabilities(
                            NotificationOptions(),
                            {},
                        ),
                    ),
                )
        finally:
            self.metrics.connection_closed()
            logger.info("SSE connection closed")

    async def _handle_messages(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Handle POST messages - MCP transport manages response directly.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        await self.sse_transport.handle_post_message(scope, receive, send)

    async def _handle_cors_preflight(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Handle CORS preflight OPTIONS requests.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [
                [b"access-control-allow-origin", b"*"],
                [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
                [b"access-control-allow-headers", b"*"],
                [b"access-control-max-age", b"86400"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"",
        })

    async def _handle_not_found(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Handle 404 Not Found.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        await self._send_json_response(
            send,
            404,
            {
                "error": "Not Found",
                "path": scope["path"],
                "available_endpoints": ["/health", "/ready", "/live", "/metrics", "/sse"],
            },
        )

    async def _handle_error(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
        error: Exception,
    ) -> None:
        """Handle internal server error.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
            error: The exception that occurred.
        """
        await self._send_json_response(
            send,
            500,
            {
                "error": "Internal Server Error",
                "message": str(error),
            },
        )

    async def _send_json_response(
        self,
        send: Callable[[dict[str, Any]], Awaitable[None]],
        status: int,
        data: dict[str, Any],
    ) -> None:
        """Send a JSON response.

        Args:
            send: ASGI send callable.
            status: HTTP status code.
            data: Response data to JSON encode.
        """
        body = json.dumps(data).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"access-control-allow-origin", b"*"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })


class CORSMiddleware:
    """Simple CORS middleware for ASGI apps.

    Adds CORS headers to all responses to allow cross-origin requests.

    Attributes:
        app: The wrapped ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application to wrap.
        """
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Handle the request.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Wrap send to add CORS headers to all responses
        async def send_with_cors(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Add CORS headers if not already present
                header_names = [h[0].lower() for h in headers]
                if b"access-control-allow-origin" not in header_names:
                    headers.append([b"access-control-allow-origin", b"*"])
                if b"access-control-allow-credentials" not in header_names:
                    headers.append([b"access-control-allow-credentials", b"true"])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cors)


def create_app(config: Optional[Config] = None) -> ASGIApp:
    """Create the ASGI application.

    Args:
        config: Server configuration (loads from env if not provided).

    Returns:
        ASGI application ready to be run with uvicorn.

    Example:
        >>> app = create_app()
        >>> # Run with: uvicorn unity_mcp.http_server:app
    """
    if config is None:
        config = load_config()

    server = MCPHttpServer(config)
    app = CORSMiddleware(server)
    return app


# Create default app instance for uvicorn
app = create_app()
