"""Dell Unity MCP Server - Credential-free mode with per-request authentication.

This package provides a Model Context Protocol (MCP) server for Dell Unity
storage systems. It automatically generates tools from OpenAPI specifications
and supports both stdio and HTTP/SSE transports.

Features:
    - Automatic tool generation from OpenAPI specs
    - Credential-free architecture with per-request authentication
    - Multi-host support for managing multiple Unity arrays
    - Read-only GET operations for safe diagnostics
    - SSE transport for n8n and web clients
    - stdio transport for Claude Desktop

Example:
    Using as a CLI tool (stdio transport)::

        $ python -m unity_mcp

    Using as HTTP server (SSE transport)::

        $ uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 3000

    Using as a library::

        from unity_mcp.config import load_config
        from unity_mcp.server import UnityMCPServer

        config = load_config()
        server = UnityMCPServer(config)
        await server.initialize()

Attributes:
    __version__: Package version following semantic versioning.
    __author__: Package author/maintainer.
"""

__version__ = "1.0.0"
__author__ = "sachdev27"
__all__ = [
    "__version__",
    "__author__",
    "UnityMCPServer",
    "UnityAPIClient",
    "Config",
    "load_config",
]

# Lazy imports to avoid circular dependencies
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api_client import UnityAPIClient
    from .config import Config, load_config
    from .server import UnityMCPServer
