"""Tests for the MCP server module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from unity_mcp.config import Config, UnityConfig, ServerConfig
from unity_mcp.server import UnityMCPServer, EXCLUDED_PARAMS
from unity_mcp.exceptions import (
    InvalidToolArgumentsError,
    ToolNotFoundError,
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


class TestUnityMCPServer:
    """Tests for the UnityMCPServer class."""

    @pytest.mark.asyncio
    async def test_server_initialization(self, mock_config: Config) -> None:
        """Test server initialization."""
        server = UnityMCPServer(mock_config)

        assert not server.is_initialized
        assert len(server.tools) == 0

        await server.initialize()

        assert server.is_initialized
        assert len(server.tools) > 0

    @pytest.mark.asyncio
    async def test_server_double_initialization(self, mock_config: Config) -> None:
        """Test that double initialization is handled."""
        server = UnityMCPServer(mock_config)

        await server.initialize()
        tool_count = len(server.tools)

        # Second initialization should be a no-op
        await server.initialize()
        assert len(server.tools) == tool_count

    @pytest.mark.asyncio
    async def test_tool_list_generation(self, mock_config: Config) -> None:
        """Test that tools are generated correctly."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        # Should have tools from the sample spec
        tool_names = [t["name"] for t in server.tools]
        assert "alertCollectionQuery" in tool_names
        assert "storageResourceCollectionQuery" in tool_names


class TestToolExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_tool_missing_arguments(self, mock_config: Config) -> None:
        """Test tool execution with missing arguments."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        with pytest.raises(InvalidToolArgumentsError):
            await server._execute_tool("alertCollectionQuery", None)

    @pytest.mark.asyncio
    async def test_execute_tool_missing_credentials(self, mock_config: Config) -> None:
        """Test tool execution with missing credentials."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        with pytest.raises(InvalidToolArgumentsError) as exc_info:
            await server._execute_tool("alertCollectionQuery", {"host": "example.com"})

        assert "username" in exc_info.value.missing_args
        assert "password" in exc_info.value.missing_args

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, mock_config: Config) -> None:
        """Test executing an unknown tool."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        with pytest.raises(ToolNotFoundError):
            await server._execute_tool(
                "nonExistentTool",
                {
                    "host": "example.com",
                    "username": "admin",
                    "password": "secret",
                },
            )

    @pytest.mark.asyncio
    async def test_execute_tool_success(
        self,
        mock_config: Config,
        sample_alert_response: list[dict[str, Any]],
    ) -> None:
        """Test successful tool execution returns CallToolResult with isError=False."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        with patch("unity_mcp.server.UnityAPIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.execute_operation = AsyncMock(return_value=sample_alert_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await server._execute_tool(
                "alertCollectionQuery",
                {
                    "host": "example.com",
                    "username": "admin",
                    "password": "secret",
                },
            )

        # Per MCP spec, result is now CallToolResult with content and isError
        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "alert-001" in result.content[0].text

    @pytest.mark.asyncio
    async def test_execute_tool_api_error_returns_isError_true(
        self,
        mock_config: Config,
    ) -> None:
        """Test that API errors return CallToolResult with isError=True per MCP spec."""
        from unity_mcp.exceptions import UnityAPIError

        server = UnityMCPServer(mock_config)
        await server.initialize()

        with patch("unity_mcp.server.UnityAPIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.execute_operation = AsyncMock(
                side_effect=UnityAPIError("Connection failed", status_code=500)
            )
            # Set up proper async context manager behavior
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await server._execute_tool(
                "alertCollectionQuery",
                {
                    "host": "example.com",
                    "username": "admin",
                    "password": "secret",
                },
            )

        # Per MCP spec, tool execution errors return isError=True (not raised as exceptions)
        assert result.isError is True
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "UnityAPIError" in result.content[0].text
        assert "Connection failed" in result.content[0].text


class TestParameterFiltering:
    """Tests for parameter filtering."""

    def test_excluded_params_contains_metadata(self) -> None:
        """Test that excluded params contains expected metadata fields."""
        assert "sessionId" in EXCLUDED_PARAMS
        assert "chatInput" in EXCLUDED_PARAMS
        assert "toolCallId" in EXCLUDED_PARAMS
        assert "action" in EXCLUDED_PARAMS

    def test_excluded_params_contains_credentials(self) -> None:
        """Test that excluded params contains credential fields."""
        assert "host" in EXCLUDED_PARAMS
        assert "username" in EXCLUDED_PARAMS
        assert "password" in EXCLUDED_PARAMS

    @pytest.mark.asyncio
    async def test_build_api_params_filters_metadata(self, mock_config: Config) -> None:
        """Test that API params builder filters metadata."""
        server = UnityMCPServer(mock_config)

        arguments = {
            "host": "example.com",
            "username": "admin",
            "password": "secret",
            "sessionId": "sess-123",
            "chatInput": "test",
            "compact": "true",
            "fields": "id,name",
        }

        params = server._build_api_params(arguments)

        # Should include valid API params
        assert params.get("compact") == "true"
        assert params.get("fields") == "id,name"

        # Should exclude metadata and credentials
        assert "host" not in params
        assert "username" not in params
        assert "password" not in params
        assert "sessionId" not in params
        assert "chatInput" not in params

    @pytest.mark.asyncio
    async def test_build_api_params_merges_query_params(
        self, mock_config: Config
    ) -> None:
        """Test that queryParams are merged correctly."""
        server = UnityMCPServer(mock_config)

        arguments = {
            "host": "example.com",
            "username": "admin",
            "password": "secret",
            "queryParams": {
                "compact": "true",
                "fields": "id,name,severity",
            },
        }

        params = server._build_api_params(arguments)

        assert params.get("compact") == "true"
        assert params.get("fields") == "id,name,severity"


class TestPathResolution:
    """Tests for API path resolution."""

    @pytest.mark.asyncio
    async def test_get_path_for_tool_with_operationId(
        self, mock_config: Config
    ) -> None:
        """Test path resolution for tools with operationId."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        path = server._get_path_for_tool("alertCollectionQuery")
        assert path == "/alert/instances"

        path = server._get_path_for_tool("alertInstanceQuery")
        assert path == "/alert/instances/{id}"

    @pytest.mark.asyncio
    async def test_get_path_for_tool_without_operationId(
        self, mock_config: Config
    ) -> None:
        """Test path resolution for tools without operationId."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        # The /lun/instances endpoint has no operationId in sample spec
        path = server._get_path_for_tool("getLunInstances")
        assert path == "/lun/instances"

    @pytest.mark.asyncio
    async def test_get_path_for_unknown_tool(self, mock_config: Config) -> None:
        """Test path resolution for unknown tool returns None."""
        server = UnityMCPServer(mock_config)
        await server.initialize()

        path = server._get_path_for_tool("unknownTool")
        assert path is None
