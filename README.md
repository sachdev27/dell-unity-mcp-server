# Dell Unity MCP Server

[![PyPI version](https://img.shields.io/pypi/v/dell-unity-mcp-server.svg)](https://pypi.org/project/dell-unity-mcp-server/)
[![PyPI downloads](https://img.shields.io/pypi/dm/dell-unity-mcp-server.svg)](https://pypi.org/project/dell-unity-mcp-server/)
[![CI](https://github.com/sachdev27/dell-unity-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/sachdev27/dell-unity-mcp-server/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/dell-unity-mcp-server.svg)](https://pypi.org/project/dell-unity-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for Dell Unity storage arrays that automatically generates tools from OpenAPI specifications with a credential-free architecture. Enables AI assistants like Claude and automation platforms like n8n to interact with Unity storage systems.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔄 **Automatic Tool Generation** | Dynamically generates 359+ MCP tools from Dell Unity OpenAPI specs |
| 🔐 **Credential-Free Architecture** | No stored credentials - pass host/username/password with each tool call |
| 🌐 **Multi-Host Support** | Manage multiple Unity arrays from a single server |
| 🛡️ **Configurable Operations** | GET-only by default, configurable to enable POST/DELETE |
| 🔌 **Multiple Transports** | HTTP/SSE for n8n, stdio for Claude Desktop |
| 📊 **Health Monitoring** | Built-in health checks and metrics endpoints |
| 🐳 **Docker Ready** | Production-ready container images |

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Integration](#-integration)
- [Available Tools](#-available-tools)
- [Architecture](#-architecture)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/sachdev27/dell-unity-mcp-server.git
cd dell-unity-mcp-server
pip install -e .

# Run HTTP/SSE server (for n8n)
export LOCAL_OPENAPI_SPEC_PATH="./openapi.json"
python -m uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 8000

# Or run stdio server (for Claude Desktop)
python -m unity_mcp.main
```

## 📦 Installation

### From Source

### From PyPI (Recommended)

```bash
pip install dell-unity-mcp-server
```

### From Source

```bash
# Clone the repository
git clone https://github.com/sachdev27/dell-unity-mcp-server.git
cd dell-unity-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows

# Install in development mode
pip install -e ".[dev]"
```

### Using Docker

```bash
# Build the image
docker build -t dell-unity-mcp-server .

# Run with SSE transport (GET-only by default)
docker run -p 8000:8000 dell-unity-mcp-server

# Run with full access (GET, POST, DELETE)
docker run -p 8000:8000 -e ALLOWED_HTTP_METHODS="GET,POST,DELETE" dell-unity-mcp-server
```

### Requirements

- **Python**: 3.10, 3.11, 3.12, or 3.13
- **Dell Unity**: Any supported version with REST API enabled (v5.x recommended)

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_OPENAPI_SPEC_PATH` | Path to OpenAPI specification (required) | - |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `HTTP_SERVER_PORT` | HTTP server port | `8000` |
| `ALLOWED_HTTP_METHODS` | Comma-separated list of allowed methods | `GET` |
| `UNITY_HOST` | Default Unity hostname (optional) | - |
| `UNITY_TLS_VERIFY` | Verify TLS certificates | `false` |
| `REQUEST_TIMEOUT` | Request timeout in milliseconds | `30000` |
| `MAX_RETRIES` | Maximum retry attempts | `3` |

### Example `.env` File

```env
# Required
LOCAL_OPENAPI_SPEC_PATH=/app/openapi.json

# Server Configuration
HTTP_SERVER_PORT=8000
LOG_LEVEL=INFO

# HTTP Methods (GET = read-only, add POST,DELETE for write operations)
ALLOWED_HTTP_METHODS=GET

# Optional Unity defaults
# UNITY_HOST=unity.example.com
# UNITY_TLS_VERIFY=false
```

### Configuring HTTP Methods

By default, the server only exposes **GET** operations (read-only). To enable write operations:

```bash
# Read-only (default) - 359 tools
export ALLOWED_HTTP_METHODS="GET"

# Full access - 777 tools
export ALLOWED_HTTP_METHODS="GET,POST,PUT,PATCH,DELETE"
```

> ⚠️ **Important:** Unity credentials are NOT stored in configuration. They are passed securely with each tool call.

## 📖 Usage

### HTTP/SSE Mode (for n8n and Web Clients)

```bash
# Using uvicorn
python -m uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 8000

# Using the main module
python -m unity_mcp.main --mode http
```

The server provides:
- **SSE Endpoint**: `http://localhost:8000/sse`
- **Health Check**: `http://localhost:8000/health`
- **Readiness Check**: `http://localhost:8000/ready`
- **Liveness Check**: `http://localhost:8000/live`
- **Metrics**: `http://localhost:8000/metrics`

### stdio Mode (for Claude Desktop)

```bash
# Using Python module
python -m unity_mcp.main
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  unity-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ALLOWED_HTTP_METHODS=GET
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
# Start the server
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the server
docker-compose down
```

## 🔗 Integration

### n8n AI Agent

1. Add an **MCP Client** node to your n8n workflow
2. Configure the connection:
   - **Transport**: SSE
   - **URL**: `http://localhost:8000/sse`
3. The 359+ Unity tools will be available to AI agents

### Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dell-unity": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "unity_mcp.main"],
      "env": {
        "LOCAL_OPENAPI_SPEC_PATH": "/path/to/openapi.json"
      }
    }
  }
}
```

### Custom MCP Clients

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://localhost:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Found {len(tools.tools)} tools")

            # Get system information
            result = await session.call_tool("systemCollectionQuery", {
                "host": "unity.example.com",
                "username": "admin",
                "password": "password",
                "fields": "id,name,model,serialNumber"
            })
            print(result)

            # Get all LUNs
            result = await session.call_tool("lunCollectionQuery", {
                "host": "unity.example.com",
                "username": "admin",
                "password": "password",
                "fields": "id,name,sizeTotal,pool",
                "per_page": 100
            })
            print(result)

asyncio.run(main())
```

## 🔧 Available Tools

The server dynamically generates **359+ tools** (GET-only) or **777+ tools** (full access) from the Unity OpenAPI specification.

### Authentication Parameters

Every tool requires these authentication parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `host` | string | Unity hostname or IP |
| `username` | string | Unity username |
| `password` | string | Unity password |

### Tool Categories

| Category | Example Tools | Description |
|----------|--------------|-------------|
| **Storage** | `lunCollectionQuery`, `poolCollectionQuery` | LUN and pool management |
| **System** | `systemCollectionQuery`, `licenseCollectionQuery` | System information |
| **Network** | `ipInterfaceCollectionQuery`, `fcPortCollectionQuery` | Network configuration |
| **File Services** | `nasServerCollectionQuery`, `fileSystemCollectionQuery` | File storage |
| **Protection** | `snapCollectionQuery`, `replicationSessionCollectionQuery` | Data protection |
| **Monitoring** | `alertCollectionQuery`, `eventCollectionQuery` | Alerts and events |
| **Host Access** | `hostCollectionQuery`, `hostLUNCollectionQuery` | Host management |

### Query Parameters

All collection endpoints support Unity query parameters:

```json
{
  "host": "unity.example.com",
  "username": "admin",
  "password": "password",
  "fields": "id,name,sizeTotal,health",
  "filter": "name lk 'prod*'",
  "per_page": 100,
  "page": 1,
  "compact": "true"
}
```

### Unity Filter Syntax

Unity uses a specific filter syntax for queries:

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `filter=severity eq 4` |
| `ne` | Not equals | `filter=health.value ne 5` |
| `lt` | Less than | `filter=sizeTotal lt 1073741824` |
| `gt` | Greater than | `filter=sizeTotal gt 1073741824` |
| `lk` | Like (wildcard) | `filter=name lk 'prod*'` |
| `and` | Logical AND | `filter=severity eq 4 and state eq 2` |

## 🏗️ Architecture

### Credential-Free Design

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AI Client     │────▶│   MCP Server    │────▶│   Dell Unity    │
│ (Claude/n8n)    │     │ (No Credentials)│     │    Array        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │
         │   Tool Call with     │   Per-Request
         │   Credentials        │   Authentication
         ▼                      ▼
    {host, user, pass}      Basic Auth Header
```

### Key Design Principles

- **No Stored Credentials**: Server starts without any Unity connection
- **Per-Request Auth**: Each tool call includes host/username/password
- **Fresh Sessions**: New API client created for each request
- **Multi-Host Ready**: Easily manage multiple Unity arrays
- **Configurable Access**: Control which HTTP methods are exposed

### Module Structure

```
unity_mcp/
├── __init__.py          # Package initialization and version
├── api_client.py        # Async Unity API client with retry logic
├── config.py            # Configuration management with validation
├── exceptions.py        # Custom exception hierarchy
├── http_server.py       # HTTP/SSE transport server
├── logging_config.py    # Structured logging configuration
├── main.py              # stdio transport entry point
├── server.py            # Core MCP server with tool handlers
└── tool_generator.py    # OpenAPI parser and tool generator
```

## 🧪 Development

### Setup Development Environment

```bash
# Clone and install with dev dependencies
git clone https://github.com/sachdev27/dell-unity-mcp-server.git
cd dell-unity-mcp-server
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=unity_mcp --cov-report=html

# Run specific test file
pytest tests/test_tool_generator.py -v
```

### Code Quality

```bash
# Format code
black unity_mcp tests

# Lint code
ruff check unity_mcp tests

# Type checking
mypy unity_mcp

# Security scan
bandit -r unity_mcp
```

### Building

```bash
# Build distribution packages
python -m build

# Build Docker image
docker build -t dell-unity-mcp-server .
```

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📚 Additional Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [Dell Unity Documentation](https://www.dell.com/support/home/en-us/product-support/product/unity-all-flash)
- [Dell Unity REST API Guide](https://developer.dell.com/)
- [n8n MCP Integration Guide](https://docs.n8n.io/)

---

<p align="center">
  Made with ❤️ for the storage automation community
</p>
