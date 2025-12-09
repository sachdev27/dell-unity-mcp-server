"""MCP server implementation for Unity - Credential-free mode.

This module provides the core MCP server that handles tool registration
and execution for Unity operations.

Example:
    >>> from unity_mcp.config import load_config
    >>> from unity_mcp.server import UnityMCPServer
    >>>
    >>> config = load_config()
    >>> server = UnityMCPServer(config)
    >>> await server.initialize()
    >>> print(f"Server ready with {len(server.tools)} tools")
"""

from __future__ import annotations

import json
from typing import Any, Optional

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions

from .api_client import UnityAPIClient
from .config import Config
from .exceptions import (
    InvalidToolArgumentsError,
    OpenAPILoadError,
    UnityAPIError,
    ToolExecutionError,
    ToolNotFoundError,
)
from .logging_config import get_logger
from .tool_generator import ToolGenerator, load_openapi_spec

logger = get_logger(__name__)

# Parameters to exclude from API calls (MCP/n8n metadata)
EXCLUDED_PARAMS: frozenset[str] = frozenset({
    # Credentials (handled separately)
    "host",
    "username",
    "password",
    # Our custom query params wrapper
    "queryParams",
    # n8n/MCP metadata that should never go to Unity
    "sessionId",
    "session_id",
    "action",
    "chatInput",
    "chat_input",
    "toolCallId",
    "tool_call_id",
    "tool",
    "toolName",
    "tool_name",
    # Other potential metadata
    "requestId",
    "request_id",
    "messageId",
    "message_id",
})


class UnityMCPServer:
    """Unity MCP Server with credential-free initialization.

    This server loads tool definitions from an OpenAPI spec at startup
    but doesn't connect to any Unity system. Authentication
    happens per-request when tools are called.

    Attributes:
        config: Server configuration.
        server: Underlying MCP server instance.
        tools: List of generated tool definitions.
        tool_generator: Tool generator instance.

    Example:
        >>> server = UnityMCPServer(config)
        >>> await server.initialize()
        >>> # Server is now ready to handle tool calls
    """

    def __init__(self, config: Config) -> None:
        """Initialize Unity MCP Server.

        Args:
            config: Server configuration object.
        """
        self.config = config
        self.server = Server("dell-unity-mcp-server")

        self.tools: list[dict[str, Any]] = []
        self.tool_generator: Optional[ToolGenerator] = None
        self._initialized = False

        # Register handlers
        self._setup_handlers()

    @property
    def is_initialized(self) -> bool:
        """Check if the server has been initialized.

        Returns:
            True if initialized, False otherwise.
        """
        return self._initialized

    async def initialize(self) -> None:
        """Initialize server by loading OpenAPI spec and generating tools.

        This method loads the OpenAPI specification and generates MCP tools.
        It does NOT connect to Unity - authentication happens per-request.

        Raises:
            OpenAPILoadError: If the OpenAPI spec cannot be loaded.
            ConfigurationError: If required configuration is missing.
        """
        if self._initialized:
            logger.debug("Server already initialized, skipping")
            return

        logger.info("Initializing MCP server (credential-free mode)")

        # Load OpenAPI spec from local file
        spec_path = self.config.unity.local_spec_path
        if not spec_path:
            raise OpenAPILoadError(
                "unknown",
                message="LOCAL_OPENAPI_SPEC_PATH not configured",
            )

        logger.info(f"Loading OpenAPI spec from {spec_path}")
        try:
            spec = load_openapi_spec(spec_path)
        except Exception as e:
            raise OpenAPILoadError(spec_path, e) from e

        # Generate tools (only for configured HTTP methods)
        logger.info("Generating MCP tools from OpenAPI spec")
        allowed_methods = self.config.server.allowed_http_methods
        self.tool_generator = ToolGenerator(spec, allowed_methods=allowed_methods)
        self.tools = self.tool_generator.generate_tools()

        self._initialized = True
        logger.info(
            "MCP server initialized successfully",
            extra={
                "mode": "credential-free",
                "tool_count": len(self.tools),
            },
        )

    def _setup_handlers(self) -> None:
        """Set up MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List all available tools.

            Returns:
                List of MCP tool definitions.
            """
            logger.debug(f"Listing {len(self.tools)} tools")
            return [
                types.Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"],
                )
                for tool in self.tools
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str,
            arguments: dict[str, Any] | None,
        ) -> types.CallToolResult:
            """Execute a tool with per-request credentials.

            Per MCP spec, tool execution errors are returned with isError=True
            rather than raised as exceptions. This allows the LLM to understand
            the error and potentially self-correct.

            Args:
                name: Tool name.
                arguments: Tool arguments including host, username, password.

            Returns:
                CallToolResult with content and isError flag.

            Note:
                Protocol errors (invalid params, unknown tool) are still raised
                as exceptions per MCP spec. Tool execution errors return isError=True.
            """
            return await self._execute_tool(name, arguments)

    async def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None,
    ) -> types.CallToolResult:
        """Execute a tool with the given arguments.

        Per MCP spec, this method distinguishes between:
        - Protocol errors (invalid params, unknown tool): Raised as exceptions
        - Tool execution errors (API failures): Returned with isError=True

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            CallToolResult with content and isError flag.

        Raises:
            InvalidToolArgumentsError: If required arguments are missing (protocol error).
            ToolNotFoundError: If the tool doesn't exist (protocol error).
        """
        if not arguments:
            raise InvalidToolArgumentsError(
                name,
                missing_args=["host", "username", "password"],
            )

        # Extract and validate credentials
        host = arguments.get("host")
        username = arguments.get("username")
        password = arguments.get("password")

        missing_creds = []
        if not host:
            missing_creds.append("host")
        if not username:
            missing_creds.append("username")
        if not password:
            missing_creds.append("password")

        if missing_creds:
            raise InvalidToolArgumentsError(
                name,
                missing_args=missing_creds,
                message="Missing required credentials",
            )

        # Find the tool definition
        tool = next((t for t in self.tools if t["name"] == name), None)
        if not tool:
            raise ToolNotFoundError(name)

        # Get API path for tool
        path = self._get_path_for_tool(name)
        if not path:
            raise ToolNotFoundError(
                name,
                message=f"Could not determine API path for tool: {name}",
            )

        # Build API parameters, filtering out metadata
        api_params = self._build_api_params(arguments)

        logger.info(
            f"Executing tool: {name}",
            extra={"host": host, "path": path, "param_count": len(api_params)},
        )

        try:
            # Create API client with per-request credentials
            # Type assertions are safe because we validated these above
            async with UnityAPIClient(
                host=str(host),
                username=str(username),
                password=str(password),
                tls_verify=self.config.unity.tls_verify,
                timeout=self.config.server.request_timeout // 1000,
                max_retries=self.config.server.max_retries,
            ) as client:
                # Execute the API call
                result = await client.execute_operation(
                    path=path,
                    method="GET",
                    params=api_params if api_params else None,
                )

                logger.info(f"Successfully executed tool: {name}")

                # Return success result per MCP spec
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=json.dumps(result, indent=2),
                        )
                    ],
                    isError=False,
                )

        except UnityAPIError as e:
            # Per MCP spec: Tool execution errors return isError=True
            # This allows the LLM to understand and potentially self-correct
            logger.error(
                f"API error executing tool {name}: {e}",
                extra={"tool": name, "error_type": type(e).__name__},
            )
            error_details: dict[str, Any] = {
                "error": type(e).__name__,
                "message": str(e),
                "tool": name,
            }
            if hasattr(e, "status_code") and e.status_code:
                error_details["status_code"] = e.status_code
            if hasattr(e, "details") and e.details:
                error_details["details"] = e.details

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(error_details, indent=2),
                    )
                ],
                isError=True,
            )
        except Exception as e:
            # Per MCP spec: Unexpected errors also return isError=True
            logger.error(
                f"Unexpected error executing tool {name}: {e}",
                extra={"tool": name, "error_type": type(e).__name__},
            )
            error_details: dict[str, Any] = {
                "error": type(e).__name__,
                "message": str(e),
                "tool": name,
            }
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(error_details, indent=2),
                    )
                ],
                isError=True,
            )

    def _build_api_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Build API parameters from tool arguments.

        Filters out credentials, metadata, and merges queryParams.

        Args:
            arguments: Raw tool arguments.

        Returns:
            Cleaned parameters for the API call.
        """
        api_params: dict[str, Any] = {}
        query_params = arguments.get("queryParams", {})

        # Only include valid Unity API parameters
        for key, value in arguments.items():
            if key not in EXCLUDED_PARAMS and value is not None:
                api_params[key] = value

        # Merge queryParams object (for filters like filter=severity eq 4)
        if isinstance(query_params, dict):
            api_params.update(query_params)

        return api_params

    def _get_path_for_tool(self, tool_name: str) -> Optional[str]:
        """Get API path for a tool by matching against OpenAPI spec.

        Args:
            tool_name: Name of the tool.

        Returns:
            API path or None if not found.
        """
        if not self.tool_generator:
            return None

        # First pass: look for exact operationId match
        for path, path_item in self.tool_generator.spec.get("paths", {}).items():
            if "get" in path_item:
                operation = path_item["get"]
                operation_id = operation.get("operationId")

                # Check for exact operationId match
                if operation_id == tool_name:
                    return path

        # Second pass: look for prefix match or generated name match
        for path, path_item in self.tool_generator.spec.get("paths", {}).items():
            if "get" in path_item:
                operation = path_item["get"]
                operation_id = operation.get("operationId")

                # Check if operationId is a prefix of tool name (e.g., getAlert_collection_query)
                if operation_id and tool_name.startswith(operation_id + "_"):
                    return path

                # If no operationId, try to match generated name from path
                if not operation_id:
                    generated_name = self.tool_generator._generate_tool_name_from_path(
                        path, "get"
                    )
                    if tool_name == generated_name or tool_name.startswith(
                        generated_name + "_"
                    ):
                        return path

        return None
