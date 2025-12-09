"""Tests for the API client module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from unity_mcp.api_client import UnityAPIClient
from unity_mcp.exceptions import (
    APIResponseError,
    AuthenticationError,
    ConnectionError,
    RateLimitError,
)


class TestUnityAPIClient:
    """Tests for the UnityAPIClient class."""

    def test_client_initialization(self) -> None:
        """Test client initialization with valid parameters."""
        client = UnityAPIClient(
            host="unity.example.com",
            username="admin",
            password="secret",
        )

        assert client.host == "unity.example.com"
        assert client.username == "admin"
        assert client.base_url == "https://unity.example.com"

    def test_client_initialization_with_custom_params(self) -> None:
        """Test client initialization with custom parameters."""
        client = UnityAPIClient(
            host="unity.example.com",
            username="admin",
            password="secret",
            tls_verify=True,
            timeout=60,
            max_retries=5,
        )

        assert client.tls_verify is True
        assert client.timeout == 60
        assert client.max_retries == 5

    def test_client_requires_host(self) -> None:
        """Test that host is required."""
        with pytest.raises(ValueError, match="host is required"):
            UnityAPIClient(host="", username="admin", password="secret")

    def test_client_requires_username(self) -> None:
        """Test that username is required."""
        with pytest.raises(ValueError, match="username is required"):
            UnityAPIClient(host="example.com", username="", password="secret")

    def test_client_requires_password(self) -> None:
        """Test that password is required."""
        with pytest.raises(ValueError, match="password is required"):
            UnityAPIClient(host="example.com", username="admin", password="")


class TestAPIClientOperations:
    """Tests for API client operations."""

    @pytest.mark.asyncio
    async def test_execute_operation_success(
        self, sample_alert_response: list[dict[str, Any]]
    ) -> None:
        """Test successful API operation."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b'{"entries": [{"content": {"id": "1"}}]}'
            mock_response.json.return_value = sample_alert_response

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="example.com",
                username="admin",
                password="secret",
            ) as client:
                result = await client.execute_operation("/alert/instances", "GET")

            assert result == sample_alert_response

    @pytest.mark.asyncio
    async def test_execute_operation_with_params(self) -> None:
        """Test API operation with query parameters."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b'{"entries": []}'
            mock_response.json.return_value = []

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="example.com",
                username="admin",
                password="secret",
            ) as client:
                await client.execute_operation(
                    "/alert/instances",
                    "GET",
                    params={"compact": "true"},
                )

            # Verify the request was made with correct params
            mock_client.request.assert_called_once()
            call_kwargs = mock_client.request.call_args[1]
            assert call_kwargs["params"] == {"compact": "true"}

    @pytest.mark.asyncio
    async def test_authentication_error(self) -> None:
        """Test handling of 401 authentication error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="example.com",
                username="admin",
                password="wrong",
            ) as client:
                with pytest.raises(AuthenticationError):
                    await client.execute_operation("/alert/instances", "GET")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self) -> None:
        """Test handling of 429 rate limit error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="example.com",
                username="admin",
                password="secret",
            ) as client:
                with pytest.raises(RateLimitError) as exc_info:
                    await client.execute_operation("/alert/instances", "GET")

            assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_api_response_error(self) -> None:
        """Test handling of API error response."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="example.com",
                username="admin",
                password="secret",
            ) as client:
                with pytest.raises(APIResponseError) as exc_info:
                    await client.execute_operation("/alert/instances", "GET")

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        """Test handling of connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="unreachable.example.com",
                username="admin",
                password="secret",
            ) as client:
                with pytest.raises(ConnectionError):
                    await client.execute_operation("/alert/instances", "GET")


class TestAPIClientContextManager:
    """Tests for API client context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        """Test that context manager closes the client properly."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnityAPIClient(
                host="example.com",
                username="admin",
                password="secret",
            ) as client:
                # Trigger client initialization
                await client._ensure_client()

            mock_client.aclose.assert_called_once()


class TestAPIClientHealthCheck:
    """Tests for API client health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b'{"entries": [{"content": {"id": "1"}}]}'
            mock_response.json.return_value = [{"id": "0", "model": "Unity 480"}]

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            client = UnityAPIClient(
                host="example.com",
                username="admin",
                password="secret",
            )
            result = await client.health_check()
            await client.close()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Test failed health check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            client = UnityAPIClient(
                host="example.com",
                username="admin",
                password="wrong",
            )
            result = await client.health_check()
            await client.close()

            assert result is False
