"""Main entry point for Unity MCP Server (stdio transport).

This module provides the command-line entry point for running the
MCP server with stdio transport, suitable for Claude Desktop and
other MCP clients.

Example:
    Running as a module::

        $ python -m unity_mcp

    Running with the entry point::

        $ unity-mcp

Usage with Claude Desktop:
    Add to your Claude Desktop config::

        {
            "mcpServers": {
                "dell-unity": {
                    "command": "python",
                    "args": ["-m", "unity_mcp"]
                }
            }
        }
"""

from __future__ import annotations

import asyncio
import sys

import mcp.server.stdio
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions

from .config import load_config
from .exceptions import ConfigurationError, UnityMCPError
from .logging_config import get_logger, setup_logging
from .server import UnityMCPServer


async def main() -> int:
    """Main entry point for stdio transport.

    Initializes the MCP server and runs it with stdio transport
    for communication with MCP clients.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Load configuration
        config = load_config()

        # Setup logging (to stderr so it doesn't interfere with stdio)
        setup_logging(
            log_level=config.server.log_level,
            json_format=config.server.log_json,
            log_file=config.server.log_file,
        )
        logger = get_logger(__name__)

        logger.info(
            "Starting Dell Unity MCP Server",
            extra={"transport": "stdio", "mode": "credential-free"},
        )

        # Create MCP server
        mcp_server = UnityMCPServer(config)

        # Initialize server (load OpenAPI spec and generate tools)
        await mcp_server.initialize()

        logger.info(
            "Server ready",
            extra={"tool_count": len(mcp_server.tools)},
        )
        logger.info("Waiting for MCP client connection via stdio...")

        # Run server with stdio transport
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="dell-unity-mcp-server",
                    server_version="1.0.0",
                    capabilities=mcp_server.server.get_capabilities(
                        NotificationOptions(),
                        {},
                    ),
                ),
            )

        return 0

    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except UnityMCPError as e:
        print(f"Server error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        return 0
    except Exception as e:
        import traceback
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


def run() -> None:
    """Entry point wrapper for console_scripts.

    This function is the entry point specified in pyproject.toml
    for the unity-mcp command.
    """
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()
