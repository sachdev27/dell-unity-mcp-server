"""Pytest configuration and shared fixtures.

This module provides common fixtures used across all test modules.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Sample OpenAPI spec for testing
SAMPLE_OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {
        "title": "Test Unity API",
        "version": "5.4.0",
    },
    "servers": [
        {"url": "https://unity.example.com/api/types"}
    ],
    "paths": {
        "/alert/instances": {
            "get": {
                "operationId": "alertCollectionQuery",
                "summary": "Get all alerts",
                "parameters": [
                    {
                        "name": "compact",
                        "in": "query",
                        "schema": {"type": "boolean"},
                        "description": "Compact response",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Success",
                    }
                },
            }
        },
        "/alert/instances/{id}": {
            "get": {
                "operationId": "alertInstanceQuery",
                "summary": "Get alert by ID",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Alert ID",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Success",
                    }
                },
            }
        },
        "/lun/instances": {
            "get": {
                "summary": "Get all LUNs",
                "responses": {
                    "200": {
                        "description": "Success",
                    }
                },
            }
        },
        "/storageResource/instances": {
            "get": {
                "operationId": "storageResourceCollectionQuery",
                "summary": "Get all storage resources",
                "responses": {
                    "200": {
                        "description": "Success",
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "alert": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique identifier"},
                    "message": {"type": "string", "description": "Alert message"},
                    "severity": {"type": "integer", "description": "Alert severity"},
                    "state": {"type": "integer", "description": "Alert state"},
                    "description": {"type": "string", "description": "Alert description"},
                },
            },
            "lun": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique identifier"},
                    "name": {"type": "string", "description": "LUN name"},
                    "sizeTotal": {"type": "integer", "description": "Total LUN size"},
                },
            },
        },
    },
}


@pytest.fixture
def sample_openapi_spec() -> dict[str, Any]:
    """Provide a sample OpenAPI specification for testing.

    Returns:
        A minimal OpenAPI spec dictionary for Unity.
    """
    return SAMPLE_OPENAPI_SPEC.copy()


@pytest.fixture
def temp_openapi_file(tmp_path: Path, sample_openapi_spec: dict[str, Any]) -> Path:
    """Create a temporary OpenAPI spec file.

    Args:
        tmp_path: Pytest temporary path fixture.
        sample_openapi_spec: Sample OpenAPI spec fixture.

    Returns:
        Path to the temporary OpenAPI spec file.
    """
    spec_file = tmp_path / "openapi.json"
    spec_file.write_text(json.dumps(sample_openapi_spec))
    return spec_file


@pytest.fixture
def mock_env_vars(temp_openapi_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables for testing.

    Args:
        temp_openapi_file: Temporary OpenAPI spec file fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setenv("LOCAL_OPENAPI_SPEC_PATH", str(temp_openapi_file))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("HTTP_SERVER_PORT", "3001")


@pytest.fixture
def sample_alert_response() -> list[dict[str, Any]]:
    """Provide a sample alert API response.

    Returns:
        List of sample alert dictionaries.
    """
    return [
        {
            "id": "alert-001",
            "name": "Test Alert 1",
            "state": "ACTIVE",
            "severity": "Critical",
            "description": "Test critical alert",
        },
        {
            "id": "alert-002",
            "name": "Test Alert 2",
            "state": "ACTIVE",
            "severity": "Info",
            "description": "Test info alert",
        },
    ]


@pytest.fixture
def sample_lun_response() -> list[dict[str, Any]]:
    """Provide a sample LUN API response.

    Returns:
        List of sample LUN dictionaries.
    """
    return [
        {
            "id": "sv_1",
            "name": "production-lun",
            "sizeTotal": 1073741824,
        },
        {
            "id": "sv_2",
            "name": "backup-lun",
            "sizeTotal": 2147483648,
        },
    ]


@pytest.fixture
def mock_httpx_client(sample_alert_response: list[dict[str, Any]]) -> Generator[MagicMock, None, None]:
    """Create a mock httpx client.

    Args:
        sample_alert_response: Sample alert data fixture.

    Yields:
        Mock httpx.AsyncClient instance.
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": []}'
        mock_response.json.return_value = sample_alert_response
        mock_response.raise_for_status = MagicMock()

        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_client_class.return_value = mock_client
        yield mock_client


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
