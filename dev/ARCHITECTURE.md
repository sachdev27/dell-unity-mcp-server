# MCP Server Architecture Guide

## Building a Dell Device MCP Server from OpenAPI Specifications

This document provides a comprehensive guide to replicating this MCP server architecture for any Dell device (PowerScale, VxRail, Data Domain, etc.) that exposes a REST API with an OpenAPI specification.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Concepts](#core-concepts)
4. [Project Structure](#project-structure)
5. [Core Components](#core-components)
6. [Implementation Guide](#implementation-guide)
7. [Tool Generation](#tool-generation)
8. [Error Handling](#error-handling)
9. [Transport Layers](#transport-layers)
10. [Configuration](#configuration)
11. [Testing Strategy](#testing-strategy)
12. [Customization Points](#customization-points)
13. [MCP Protocol Compliance](#mcp-protocol-compliance)
14. [Deployment](#deployment)

---

## Overview

This MCP (Model Context Protocol) server architecture enables AI assistants (Claude, ChatGPT via n8n, etc.) to interact with Dell infrastructure devices through automatically generated tools from OpenAPI specifications.

### Key Features

| Feature | Description |
|---------|-------------|
| **Automatic Tool Generation** | Parses OpenAPI specs and generates MCP tools dynamically |
| **Credential-Free Architecture** | No stored credentials - pass host/user/pass with each tool call |
| **Multi-Host Support** | Single server instance can query multiple device instances |
| **Safe Operations** | GET-only by default for read-only operations |
| **Dual Transport** | HTTP/SSE for web clients (n8n), stdio for Claude Desktop |
| **LLM-Optimized Descriptions** | Enhanced tool descriptions with field info for better AI understanding |

### What You Need

1. **OpenAPI Specification** (JSON or YAML) from your Dell device
2. **Python 3.10+** with async support
3. **MCP SDK** (`mcp` package)
4. **HTTP Client** (`httpx` for async requests)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI Client Layer                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Claude Desktop  │  │      n8n        │  │    Other MCP Clients        │  │
│  │    (stdio)      │  │   (HTTP/SSE)    │  │                             │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────────┬──────────────┘  │
│           │                    │                          │                  │
└───────────┼────────────────────┼──────────────────────────┼──────────────────┘
            │                    │                          │
            ▼                    ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Transport Layer                                    │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────┐   │
│  │      STDIO Transport        │  │        HTTP/SSE Transport           │   │
│  │   (main.py / run())         │  │   (http_server.py / MCPHttpServer)  │   │
│  └──────────────┬──────────────┘  └──────────────────┬──────────────────┘   │
│                 │                                    │                       │
│                 └────────────────┬───────────────────┘                       │
│                                  │                                           │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MCP Server Core                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     PowerStoreMCPServer (server.py)                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │ │
│  │  │   list_tools()   │  │   call_tool()    │  │  _execute_tool()     │  │ │
│  │  │   Handler        │  │   Handler        │  │  (with credentials)  │  │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
│                                  │ Uses                                      │
│                                  ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     ToolGenerator (tool_generator.py)                  │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │ │
│  │  │ generate_tools() │  │ _generate_input  │  │ _build_enhanced      │  │ │
│  │  │                  │  │ _schema()        │  │ _description()       │  │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API Client Layer                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                   PowerStoreAPIClient (api_client.py)                  │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │ │
│  │  │ execute_operation│  │   Retry Logic    │  │   Error Handling     │  │ │
│  │  │ (path, method,   │  │   (exponential   │  │   (auth, rate limit, │  │ │
│  │  │  params)         │  │    backoff)      │  │    connection)       │  │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Dell Device REST API                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │          PowerStore / PowerScale / VxRail / Data Domain                │ │
│  │                     https://device.example.com/api/rest                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### 1. Credential-Free Architecture

Unlike traditional API clients that store credentials, this architecture passes credentials with **every tool call**:

```python
# Tool call from AI client includes credentials
{
    "tool_name": "getVolume",
    "arguments": {
        "host": "powerstore.example.com",    # ← Per-request
        "username": "admin",                  # ← Per-request
        "password": "secret",                 # ← Per-request
        "select": "id,name,state"
    }
}
```

**Benefits:**
- Single server can manage multiple device instances
- No credential storage security concerns
- Stateless operation

### 2. OpenAPI-Driven Tool Generation

Tools are generated automatically from OpenAPI specifications:

```
OpenAPI Spec              MCP Tool
─────────────            ─────────
GET /volume        →     getVolume
GET /volume/{id}   →     getVolumeById
GET /alert         →     getAlert
GET /host          →     getHost
```

### 3. LLM-Optimized Descriptions

Tool descriptions are enhanced with schema information:

```python
# Original OpenAPI description:
"Get all volumes"

# Enhanced description for LLM:
"""Get all volumes

Available fields for 'select': id, name, size, state, type, wwn...

Key fields:
- id: Unique volume identifier
- name: Volume name
- state: Volume state (values: Ready, Initializing, Offline)
- size: Volume size in bytes

Filter examples (queryParams):
- {"state": "eq.Ready"} - Ready volumes only
- {"type": "neq.Snapshot"} - Exclude snapshots
"""
```

---

## Project Structure

```
your-device-mcp/
├── pyproject.toml              # Project configuration and dependencies
├── README.md                   # User documentation
├── ARCHITECTURE.md             # This file
├── openapi.json                # OpenAPI spec from your device
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
├── Dockerfile                  # Container image
├── docker-compose.yml          # Container orchestration
├── Makefile                    # Development commands
│
├── your_device_mcp/            # Main package
│   ├── __init__.py             # Package initialization
│   ├── server.py               # Core MCP server implementation
│   ├── tool_generator.py       # OpenAPI → MCP tool conversion
│   ├── api_client.py           # Device API HTTP client
│   ├── http_server.py          # HTTP/SSE transport server
│   ├── main.py                 # stdio transport entry point
│   ├── config.py               # Configuration management
│   ├── exceptions.py           # Custom exception hierarchy
│   └── logging_config.py       # Structured logging
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_server.py
│   ├── test_tool_generator.py
│   ├── test_api_client.py
│   ├── test_http_server.py
│   └── test_config.py
│
└── logs/                       # Log output directory
```

---

## Core Components

### 1. Server (`server.py`)

The main MCP server that handles tool registration and execution.

```python
"""MCP server implementation - Credential-free mode."""

from __future__ import annotations

import json
from typing import Any, Optional

import mcp.types as types
from mcp.server.lowlevel import Server

from .api_client import YourDeviceAPIClient
from .config import Config
from .exceptions import (
    InvalidToolArgumentsError,
    PowerStoreAPIError,  # Rename to YourDeviceAPIError
    ToolNotFoundError,
)
from .tool_generator import ToolGenerator, load_openapi_spec

# Parameters to exclude from API calls
EXCLUDED_PARAMS: frozenset[str] = frozenset({
    # Credentials
    "host", "username", "password",
    # Custom query wrapper
    "queryParams",
    # AI/MCP metadata that should never go to the API
    "sessionId", "session_id", "action", "chatInput", "chat_input",
    "toolCallId", "tool_call_id", "tool", "toolName", "tool_name",
    "requestId", "request_id", "messageId", "message_id",
})


class YourDeviceMCPServer:
    """MCP Server with credential-free initialization."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.server = Server("your-device-mcp-server")
        self.tools: list[dict[str, Any]] = []
        self.tool_generator: Optional[ToolGenerator] = None
        self._initialized = False
        self._setup_handlers()

    async def initialize(self) -> None:
        """Load OpenAPI spec and generate tools."""
        if self._initialized:
            return

        # Load OpenAPI spec
        spec_path = self.config.device.local_spec_path
        spec = load_openapi_spec(spec_path)

        # Generate tools
        self.tool_generator = ToolGenerator(spec)
        self.tools = self.tool_generator.generate_tools()
        self._initialized = True

    def _setup_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
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
            return await self._execute_tool(name, arguments)

    async def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None,
    ) -> types.CallToolResult:
        """Execute tool with per-request credentials."""

        # Validate credentials (protocol error if missing)
        if not arguments:
            raise InvalidToolArgumentsError(name, missing_args=["host", "username", "password"])

        host = arguments.get("host")
        username = arguments.get("username")
        password = arguments.get("password")

        missing = [k for k in ["host", "username", "password"] if not arguments.get(k)]
        if missing:
            raise InvalidToolArgumentsError(name, missing_args=missing)

        # Find tool and get API path
        tool = next((t for t in self.tools if t["name"] == name), None)
        if not tool:
            raise ToolNotFoundError(name)

        path = self._get_path_for_tool(name)
        if not path:
            raise ToolNotFoundError(name, message=f"No API path for tool: {name}")

        # Build API parameters
        api_params = self._build_api_params(arguments)

        try:
            # Execute with per-request credentials
            async with YourDeviceAPIClient(
                host=host,
                username=username,
                password=password,
                tls_verify=self.config.device.tls_verify,
            ) as client:
                result = await client.execute_operation(path=path, method="GET", params=api_params)

                # Return success (MCP spec compliant)
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=json.dumps(result, indent=2))],
                    isError=False,
                )

        except Exception as e:
            # Return error with isError=True (MCP spec compliant)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({
                    "error": type(e).__name__,
                    "message": str(e),
                    "tool": name,
                }, indent=2))],
                isError=True,
            )

    def _build_api_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Filter out metadata and merge queryParams."""
        api_params = {}
        query_params = arguments.get("queryParams", {})

        for key, value in arguments.items():
            if key not in EXCLUDED_PARAMS and value is not None:
                api_params[key] = value

        if isinstance(query_params, dict):
            api_params.update(query_params)

        return api_params

    def _get_path_for_tool(self, tool_name: str) -> Optional[str]:
        """Map tool name back to API path."""
        if not self.tool_generator:
            return None

        for path, path_item in self.tool_generator.spec.get("paths", {}).items():
            if "get" in path_item:
                operation = path_item["get"]
                op_id = operation.get("operationId")

                # Match by operationId
                if op_id == tool_name:
                    return path

                # Match by generated name
                if not op_id:
                    generated = self.tool_generator._generate_tool_name_from_path(path, "get")
                    if tool_name == generated or tool_name.startswith(generated + "_"):
                        return path

        return None
```

### 2. Tool Generator (`tool_generator.py`)

Converts OpenAPI specifications into MCP tool definitions.

```python
"""OpenAPI to MCP tool generator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from .exceptions import OpenAPILoadError, OpenAPIParseError

# Configuration constants
MAX_FIELDS_DISPLAY = 20
MAX_KEY_FIELDS = 10
MAX_ENUM_VALUES = 5


class ToolGenerator:
    """Generate MCP tools from OpenAPI specification."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.tool_names: dict[str, int] = {}

    def generate_tools(self) -> list[dict[str, Any]]:
        """Generate all MCP tools (GET methods only for safety)."""
        tools = []
        paths = self.spec.get("paths", {})

        for path, path_item in paths.items():
            if "get" in path_item:
                operation = path_item["get"]
                tool = self._generate_tool_from_operation(path, "get", operation)
                if tool:
                    tools.append(tool)

        return tools

    def _generate_tool_from_operation(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Generate a single MCP tool from an OpenAPI operation."""
        try:
            # Generate tool name
            tool_name = operation.get("operationId") or self._generate_tool_name_from_path(path, method)
            tool_name = self._make_unique_name(tool_name, path)

            # Generate description
            base_description = operation.get("summary") or operation.get("description") or f"{method.upper()} {path}"
            is_collection = "{id}" not in path
            resource_name = self._get_resource_name_from_path(path)
            description = self._build_enhanced_description(base_description, resource_name, is_collection)

            # Generate input schema
            input_schema = self._generate_input_schema(operation, is_collection)

            return {
                "name": tool_name,
                "description": description,
                "inputSchema": input_schema,
            }
        except Exception:
            return None

    def _generate_tool_name_from_path(self, path: str, method: str) -> str:
        """Generate tool name from path and method.

        Examples:
            /volume → getVolume
            /eth_port → getEth_port
            /volume/{id} → getVolumeById
        """
        path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
        parts = [method] + path_parts

        name = ""
        for i, part in enumerate(parts):
            cleaned = "".join(c if c.isalnum() else "_" for c in part)
            if i == 0:
                name = cleaned.lower()
            else:
                name += cleaned.capitalize()

        return name

    def _get_resource_name_from_path(self, path: str) -> str:
        """Extract resource name from path (e.g., /volume → volume)."""
        parts = [p for p in path.split("/") if p and not p.startswith("{")]
        return parts[0] if parts else ""

    def _make_unique_name(self, tool_name: str, path: str) -> str:
        """Ensure tool names are unique."""
        if tool_name in self.tool_names:
            count = self.tool_names[tool_name] + 1
            self.tool_names[tool_name] = count
            path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
            suffix = "_".join(path_parts) if path_parts else str(count)
            tool_name = f"{tool_name}_{suffix}"
        else:
            self.tool_names[tool_name] = 0
        return tool_name

    def _build_enhanced_description(
        self,
        base_description: str,
        resource_name: str,
        is_collection_query: bool,
    ) -> str:
        """Enhance description with schema info for LLMs."""
        description = base_description

        # Find schema definition for this resource
        definitions = self.spec.get("definitions", {})
        instance_def = definitions.get(f"{resource_name}_instance", {})
        properties = instance_def.get("properties", {})

        if properties and is_collection_query:
            # Add available fields
            field_names = sorted(properties.keys())
            fields_summary = ", ".join(field_names[:MAX_FIELDS_DISPLAY])
            if len(field_names) > MAX_FIELDS_DISPLAY:
                fields_summary += f", ... ({len(field_names)} total)"
            description += f"\n\nAvailable fields for 'select': {fields_summary}"

            # Add key fields with descriptions
            key_fields = self._get_key_fields(properties, resource_name)
            if key_fields:
                description += f"\n\nKey fields:\n{key_fields}"

            # Add filter examples
            filter_examples = self._get_filter_examples(resource_name, properties)
            if filter_examples:
                description += f"\n\nFilter examples (queryParams):\n{filter_examples}"

        return description

    def _get_key_fields(self, properties: dict[str, Any], resource_name: str) -> str:
        """Get formatted list of priority fields."""
        priority_fields = [
            "id", "name", "state", "status", "severity", "type",
            "description", "description_l10n", "is_acknowledged",
            "resource_name", "resource_type", "generated_timestamp",
            "size", "logical_used",
        ]

        lines = []
        for field in priority_fields:
            if field in properties:
                prop = properties[field]
                desc = prop.get("description", "")[:80]
                enum = prop.get("enum")

                field_info = f"- {field}"
                if desc:
                    field_info += f": {desc}"
                if enum:
                    enum_str = ", ".join(str(e) for e in enum[:MAX_ENUM_VALUES])
                    field_info += f" (values: {enum_str})"

                lines.append(field_info)

        return "\n".join(lines[:MAX_KEY_FIELDS])

    def _get_filter_examples(self, resource_name: str, properties: dict[str, Any]) -> str:
        """Generate filter examples based on resource type."""
        # Customize these for your device's resources
        examples = []

        if resource_name == "alert":
            examples = [
                '{"state": "eq.ACTIVE"} - Active alerts only',
                '{"severity": "eq.Critical"} - Critical severity only',
            ]
        elif resource_name == "volume":
            examples = [
                '{"state": "eq.Ready"} - Ready volumes only',
            ]
        elif "state" in properties:
            examples = ['{"state": "eq.<value>"} - Filter by state']

        return "\n".join(f"- {ex}" for ex in examples)

    def _generate_input_schema(
        self,
        operation: dict[str, Any],
        is_collection_query: bool = False,
    ) -> dict[str, Any]:
        """Generate JSON Schema for tool input."""
        properties = {
            "host": {
                "type": "string",
                "description": "Device host (e.g., device.example.com)",
            },
            "username": {
                "type": "string",
                "description": "Device username",
            },
            "password": {
                "type": "string",
                "description": "Device password",
            },
        }
        required = ["host", "username", "password"]

        # Add OpenAPI parameters
        for param in operation.get("parameters", []):
            param_name = param.get("name")
            if not param_name or param.get("in") not in ["query", "path"]:
                continue

            param_schema = {
                "type": self._convert_openapi_type(param.get("type", "string")),
                "description": param.get("description", ""),
            }
            if "enum" in param:
                param_schema["enum"] = param["enum"]

            properties[param_name] = param_schema
            if param.get("required"):
                required.append(param_name)

        # Add standard query parameters for collections
        if is_collection_query:
            properties["select"] = {
                "type": "string",
                "description": "Comma-separated fields to return (e.g., 'id,name,state')",
            }
            properties["limit"] = {
                "type": "integer",
                "description": "Maximum number of results",
            }
            properties["offset"] = {
                "type": "integer",
                "description": "Number of results to skip",
            }
            properties["queryParams"] = {
                "type": "object",
                "description": "Additional filters (e.g., {'state': 'eq.ACTIVE'})",
                "additionalProperties": {"type": "string"},
            }

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,  # MCP spec compliance
        }

    def _convert_openapi_type(self, openapi_type: str) -> str:
        """Convert OpenAPI type to JSON Schema type."""
        mapping = {
            "integer": "number",
            "number": "number",
            "string": "string",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
        }
        return mapping.get(openapi_type, "string")


def load_openapi_spec(file_path: str) -> dict[str, Any]:
    """Load OpenAPI specification from JSON or YAML file."""
    path = Path(file_path)

    if not path.exists():
        raise OpenAPILoadError(file_path, message=f"File not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        if path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(f)
        else:
            return json.load(f)
```

### 3. API Client (`api_client.py`)

HTTP client for communicating with the device REST API.

```python
"""Device API client with Basic Auth."""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from .exceptions import (
    APIResponseError,
    AuthenticationError,
    ConnectionError,
    RateLimitError,
)


class YourDeviceAPIClient:
    """API client using Basic Auth on each request."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        api_version: str = "v1",
        tls_verify: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        if not all([host, username, password]):
            raise ValueError("host, username, and password are required")

        self.host = host
        self.username = username
        self.password = password
        self.api_version = api_version
        self.tls_verify = tls_verify
        self.timeout = timeout
        self.max_retries = max_retries

        # Customize base URL for your device
        self.base_url = f"https://{host}/api/rest"
        self.client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                verify=self.tls_verify,
                timeout=self.timeout,
                follow_redirects=True,
                auth=(self.username, self.password),  # Basic Auth
            )
        return self.client

    async def execute_operation(
        self,
        path: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Execute an API operation with retry logic."""
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._ensure_client()
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=body,
                    headers=headers,
                )

                # Handle errors
                if response.status_code == 401:
                    raise AuthenticationError(self.host)
                elif response.status_code == 429:
                    raise RateLimitError(retry_after=response.headers.get("Retry-After"))
                elif response.status_code >= 400:
                    raise APIResponseError(
                        message=f"API error: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                return response.json() if response.content else {}

            except (AuthenticationError, RateLimitError, APIResponseError):
                raise
            except httpx.ConnectError as e:
                raise ConnectionError(self.host, e)
            except (httpx.TimeoutException, httpx.RequestError) as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        raise ConnectionError(self.host, last_error, f"Failed after {self.max_retries} attempts")

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self) -> "YourDeviceAPIClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
```

### 4. HTTP Server (`http_server.py`)

ASGI server for HTTP/SSE transport (used by n8n and web clients).

```python
"""HTTP server with SSE transport for MCP."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport

from .config import Config, load_config
from .server import YourDeviceMCPServer

ASGIApp = Callable[[dict, Callable, Callable], Awaitable[None]]


class ServerMetrics:
    """Simple metrics collector."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.requests_total = 0
        self.errors_total = 0
        self.active_connections = 0

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "uptime_seconds": round(self.uptime_seconds, 2),
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "active_connections": self.active_connections,
        }


class MCPHttpServer:
    """ASGI HTTP server for MCP with SSE transport."""

    VERSION = "1.0.0"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.mcp_server = YourDeviceMCPServer(config)
        self.sse_transport = SseServerTransport("/messages")
        self.metrics = ServerMetrics()
        self._initialized = False

    async def initialize(self) -> None:
        if not self._initialized:
            await self.mcp_server.initialize()
            self._initialized = True

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """ASGI entry point."""
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        if scope["type"] != "http":
            return

        path = scope["path"]
        method = scope["method"]
        self.metrics.requests_total += 1

        try:
            if path == "/health" and method == "GET":
                await self._handle_health(send)
            elif path == "/sse" and method == "GET":
                await self._handle_sse(scope, receive, send)
            elif path == "/messages" and method == "POST":
                await self._handle_messages(scope, receive, send)
            elif method == "OPTIONS":
                await self._handle_cors_preflight(send)
            else:
                await self._handle_not_found(scope, send)
        except Exception as e:
            self.metrics.errors_total += 1
            await self._handle_error(send, e)

    async def _handle_lifespan(self, scope, receive, send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await self.initialize()
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _handle_health(self, send) -> None:
        data = {
            "status": "healthy" if self._initialized else "starting",
            "version": self.VERSION,
            "tools": len(self.mcp_server.tools) if self._initialized else 0,
            "uptime_seconds": round(self.metrics.uptime_seconds, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._send_json(send, 200, data)

    async def _handle_sse(self, scope, receive, send) -> None:
        self.metrics.active_connections += 1
        try:
            async with self.sse_transport.connect_sse(scope, receive, send) as streams:
                await self.mcp_server.server.run(
                    streams[0],
                    streams[1],
                    InitializationOptions(
                        server_name="your-device-mcp-server",
                        server_version=self.VERSION,
                        capabilities=self.mcp_server.server.get_capabilities(
                            NotificationOptions(), {}
                        ),
                    ),
                )
        finally:
            self.metrics.active_connections -= 1

    async def _handle_messages(self, scope, receive, send) -> None:
        await self.sse_transport.handle_post_message(scope, receive, send)

    async def _handle_cors_preflight(self, send) -> None:
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [
                [b"access-control-allow-origin", b"*"],
                [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
                [b"access-control-allow-headers", b"*"],
            ],
        })
        await send({"type": "http.response.body", "body": b""})

    async def _handle_not_found(self, scope, send) -> None:
        await self._send_json(send, 404, {
            "error": "Not Found",
            "path": scope["path"],
            "available_endpoints": ["/health", "/sse", "/messages"],
        })

    async def _handle_error(self, send, error: Exception) -> None:
        await self._send_json(send, 500, {"error": str(error)})

    async def _send_json(self, send, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"access-control-allow-origin", b"*"],
            ],
        })
        await send({"type": "http.response.body", "body": body})


def create_app(config: Optional[Config] = None) -> ASGIApp:
    """Create ASGI application."""
    if config is None:
        config = load_config()
    return MCPHttpServer(config)


# Default app for uvicorn
app = create_app()
```

### 5. Exception Hierarchy (`exceptions.py`)

```python
"""Custom exception hierarchy."""

from typing import Any, Optional


class YourDeviceMCPError(Exception):
    """Base exception for all errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# Configuration Errors
class ConfigurationError(YourDeviceMCPError):
    """Invalid or missing configuration."""
    pass


# API Errors
class YourDeviceAPIError(YourDeviceMCPError):
    """Base for API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message, details={
            "status_code": status_code,
            "response_body": response_body,
            **(details or {}),
        })


class AuthenticationError(YourDeviceAPIError):
    """Authentication failed (401)."""

    def __init__(self, host: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(
            f"Authentication failed for host: {host}",
            status_code=401,
            details={"host": host, **(details or {})},
        )


class ConnectionError(YourDeviceAPIError):
    """Connection to device failed."""

    def __init__(
        self,
        host: str,
        original_error: Optional[Exception] = None,
        message: Optional[str] = None,
    ) -> None:
        msg = message or f"Failed to connect to: {host}"
        if original_error:
            msg = f"{msg} - {original_error}"
        super().__init__(msg, details={"host": host})


class RateLimitError(YourDeviceAPIError):
    """Rate limit exceeded (429)."""

    def __init__(self, retry_after: Optional[int] = None) -> None:
        super().__init__(
            "Rate limit exceeded",
            status_code=429,
            details={"retry_after": retry_after},
        )


class APIResponseError(YourDeviceAPIError):
    """General API error response."""
    pass


# Tool Errors
class ToolError(YourDeviceMCPError):
    """Base for tool-related errors."""

    def __init__(self, tool_name: str, message: Optional[str] = None, **kwargs) -> None:
        self.tool_name = tool_name
        msg = message or f"Tool error: {tool_name}"
        super().__init__(msg, details={"tool_name": tool_name, **kwargs})


class ToolNotFoundError(ToolError):
    """Tool doesn't exist."""

    def __init__(self, tool_name: str, message: Optional[str] = None) -> None:
        super().__init__(tool_name, message or f"Tool not found: {tool_name}")


class InvalidToolArgumentsError(ToolError):
    """Invalid or missing tool arguments."""

    def __init__(
        self,
        tool_name: str,
        missing_args: Optional[list[str]] = None,
        message: Optional[str] = None,
    ) -> None:
        msg = message or f"Invalid arguments for tool: {tool_name}"
        if missing_args:
            msg = f"{msg} - Missing: {', '.join(missing_args)}"
        super().__init__(tool_name, msg, missing_args=missing_args)


# OpenAPI Errors
class OpenAPILoadError(YourDeviceMCPError):
    """Failed to load OpenAPI spec."""

    def __init__(self, path: str, error: Optional[Exception] = None, message: Optional[str] = None) -> None:
        msg = message or f"Failed to load OpenAPI spec: {path}"
        if error:
            msg = f"{msg} - {error}"
        super().__init__(msg, details={"path": path})


class OpenAPIParseError(YourDeviceMCPError):
    """Failed to parse OpenAPI spec."""

    def __init__(self, path: str, error: Optional[Exception] = None) -> None:
        super().__init__(
            f"Failed to parse OpenAPI spec: {path} - {error}",
            details={"path": path},
        )
```

---

## Implementation Guide

### Step 1: Obtain OpenAPI Specification

Get the OpenAPI spec from your Dell device:

```bash
# Most Dell devices expose OpenAPI at a standard path
curl -k -u admin:password https://your-device/api/rest/swagger.json > openapi.json

# Or download from Dell support documentation
```

### Step 2: Analyze the OpenAPI Spec

```python
import json

with open("openapi.json") as f:
    spec = json.load(f)

# Count endpoints
paths = spec.get("paths", {})
print(f"Total endpoints: {len(paths)}")

# Count GET endpoints (what we'll generate tools for)
get_endpoints = sum(1 for p, item in paths.items() if "get" in item)
print(f"GET endpoints: {get_endpoints}")

# List resources
resources = set()
for path in paths:
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if parts:
        resources.add(parts[0])
print(f"Resources: {sorted(resources)}")
```

### Step 3: Customize for Your Device

1. **Update API base URL** in `api_client.py`:
   ```python
   # PowerStore uses /api/rest
   self.base_url = f"https://{host}/api/rest"

   # PowerScale might use /platform
   self.base_url = f"https://{host}/platform"
   ```

2. **Customize filter examples** in `tool_generator.py`:
   ```python
   def _get_filter_examples(self, resource_name: str, properties: dict) -> str:
       if resource_name == "your_resource":
           return '{"status": "eq.ACTIVE"}'
   ```

3. **Update priority fields** for your device's important attributes

### Step 4: Create Configuration

```python
# config.py
from pydantic import BaseModel, Field

class DeviceConfig(BaseModel):
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_version: str = "v1"
    local_spec_path: Optional[str] = None
    tls_verify: bool = False

class ServerConfig(BaseModel):
    port: int = 3000
    log_level: str = "INFO"
    max_retries: int = 3
    request_timeout: int = 30000

class Config(BaseModel):
    device: DeviceConfig = DeviceConfig()
    server: ServerConfig = ServerConfig()

def load_config() -> Config:
    return Config(
        device=DeviceConfig(
            local_spec_path=os.getenv("OPENAPI_SPEC_PATH", "./openapi.json"),
        ),
        server=ServerConfig(
            port=int(os.getenv("HTTP_PORT", "3000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        ),
    )
```

---

## MCP Protocol Compliance

### Key MCP Spec Requirements

1. **Tool Definitions** must include:
   - `name`: Unique tool identifier
   - `description`: Human-readable description
   - `inputSchema`: Valid JSON Schema

2. **Tool Results** must use `CallToolResult`:
   ```python
   types.CallToolResult(
       content=[types.TextContent(type="text", text="...")],
       isError=False,  # True for execution errors
   )
   ```

3. **Error Handling**:
   - **Protocol errors** (invalid params, unknown tool): Raise exceptions
   - **Execution errors** (API failures): Return `isError=True`

4. **Input Schema** should include:
   ```python
   {
       "type": "object",
       "properties": {...},
       "required": [...],
       "additionalProperties": False,  # Important!
   }
   ```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_tool_generator.py
import pytest
from your_device_mcp.tool_generator import ToolGenerator

@pytest.fixture
def sample_spec():
    return {
        "paths": {
            "/volume": {
                "get": {
                    "summary": "Get all volumes",
                    "parameters": [],
                }
            },
            "/volume/{id}": {
                "get": {
                    "summary": "Get volume by ID",
                    "parameters": [
                        {"name": "id", "in": "path", "required": True}
                    ],
                }
            },
        },
        "definitions": {},
    }

def test_generate_tools(sample_spec):
    generator = ToolGenerator(sample_spec)
    tools = generator.generate_tools()

    assert len(tools) == 2
    assert tools[0]["name"] == "getVolume"
    assert tools[1]["name"] == "getVolumeById"

def test_tool_has_credentials(sample_spec):
    generator = ToolGenerator(sample_spec)
    tools = generator.generate_tools()

    schema = tools[0]["inputSchema"]
    assert "host" in schema["properties"]
    assert "username" in schema["properties"]
    assert "password" in schema["properties"]
```

### Integration Tests

```python
# tests/test_server.py
import pytest
from your_device_mcp.server import YourDeviceMCPServer

@pytest.mark.asyncio
async def test_execute_tool_missing_credentials(mock_server):
    result = await mock_server._execute_tool("getVolume", {})
    # Should raise InvalidToolArgumentsError

@pytest.mark.asyncio
async def test_execute_tool_success(mock_server, mock_api_response):
    result = await mock_server._execute_tool("getVolume", {
        "host": "test.example.com",
        "username": "admin",
        "password": "secret",
    })
    assert result.isError is False
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY your_device_mcp/ ./your_device_mcp/
COPY openapi.json .

ENV OPENAPI_SPEC_PATH=/app/openapi.json
ENV HTTP_PORT=3000

EXPOSE 3000

CMD ["uvicorn", "your_device_mcp.http_server:app", "--host", "0.0.0.0", "--port", "3000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    ports:
      - "3000:3000"
    environment:
      - LOG_LEVEL=INFO
      - OPENAPI_SPEC_PATH=/app/openapi.json
    volumes:
      - ./openapi.json:/app/openapi.json:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Customization Points

### 1. Authentication Method

If your device uses a different auth method:

```python
# Session-based auth
async def _ensure_client(self) -> httpx.AsyncClient:
    if self.client is None:
        self.client = httpx.AsyncClient(...)
        # Login and get session token
        response = await self.client.post("/auth/login", json={
            "username": self.username,
            "password": self.password,
        })
        token = response.json()["token"]
        self.client.headers["Authorization"] = f"Bearer {token}"
    return self.client
```

### 2. API Response Format

Handle different response structures:

```python
async def execute_operation(self, path: str, ...) -> Any:
    response = await self.client.request(...)
    data = response.json()

    # Some APIs wrap results
    if "data" in data:
        return data["data"]
    if "items" in data:
        return data["items"]
    return data
```

### 3. Tool Name Generation

Customize naming for your API:

```python
def _generate_tool_name_from_path(self, path: str, method: str) -> str:
    # Custom logic for your API's path structure
    ...
```

### 4. Query Syntax

Adapt filter syntax for your API:

```python
# PowerStore uses: ?state=eq.ACTIVE
# Other APIs might use: ?filter=state:ACTIVE
def _build_api_params(self, arguments: dict) -> dict:
    query_params = arguments.get("queryParams", {})

    # Transform to your API's syntax
    filters = []
    for key, value in query_params.items():
        filters.append(f"{key}:{value}")

    if filters:
        return {"filter": ",".join(filters)}
    return {}
```

---

## Summary

This architecture provides a robust, reusable pattern for building MCP servers from OpenAPI specifications. Key benefits:

1. **Automatic tool generation** from OpenAPI specs
2. **Credential-free** per-request authentication
3. **LLM-optimized** descriptions with field and filter information
4. **Dual transport** support (stdio + HTTP/SSE)
5. **MCP spec compliant** error handling
6. **Production-ready** with health checks, metrics, and logging

To adapt for a new Dell device:

1. Obtain the OpenAPI specification
2. Copy this project structure
3. Customize API client (base URL, auth method)
4. Customize tool generator (filter examples, priority fields)
5. Update configuration for your device
6. Test and deploy
