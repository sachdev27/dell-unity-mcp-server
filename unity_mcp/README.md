# Dell Unity MCP Server

A Model Context Protocol (MCP) server for Dell Unity storage systems. This server automatically generates tools from OpenAPI specifications and supports both stdio and HTTP/SSE transports.

## Features

- **Automatic tool generation** from Unity OpenAPI specs
- **Credential-free architecture** with per-request authentication
- **Multi-host support** for managing multiple Unity arrays
- **Read-only GET operations** for safe diagnostics
- **SSE transport** for n8n and web clients
- **stdio transport** for Claude Desktop

## Prerequisites

- Python 3.10+
- Dell Unity OpenAPI specification (JSON or YAML)

## Installation

### Install Dependencies

```bash
pip install mcp httpx pydantic python-dotenv pyyaml
```

### Or using pip with requirements

Create a `requirements.txt`:

```
mcp>=1.0.0
httpx>=0.25.0
pydantic>=2.0.0
python-dotenv>=1.0.0
pyyaml>=6.0.0
```

Then run:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```bash
# Required: Path to Unity OpenAPI specification
LOCAL_OPENAPI_SPEC_PATH=/path/to/unity-openapi.json

# Optional: Default Unity host (can be overridden per-request)
UNITY_HOST=unity.example.com

# Optional: Default credentials (can be overridden per-request)
UNITY_USERNAME=admin
UNITY_PASSWORD=your-password

# Optional: HTTP server port (default: 3000)
HTTP_SERVER_PORT=3000

# Optional: Logging level (default: INFO)
LOG_LEVEL=INFO
```

## Usage

### Stdio Transport (Claude Desktop)

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
    "mcpServers": {
        "dell-unity": {
            "command": "python",
            "args": ["-m", "unity_mcp"],
            "env": {
                "LOCAL_OPENAPI_SPEC_PATH": "/path/to/unity-openapi.json"
            }
        }
    }
}
```

Or run directly:

```bash
python -m unity_mcp
```

### HTTP/SSE Transport (n8n, Web Clients)

Run with uvicorn:

```bash
uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 3000
```

Then connect your MCP client to:
- **SSE endpoint**: `http://localhost:3000/sse`
- **Messages endpoint**: `http://localhost:3000/messages`

### Health Endpoints

- `GET /health` - Detailed health status
- `GET /ready` - Kubernetes readiness probe
- `GET /live` - Kubernetes liveness probe
- `GET /metrics` - Server metrics

## Unity API Structure

The Unity REST API uses different URL patterns than PowerStore:

| Pattern | Description | Example |
|---------|-------------|---------|
| `/api/types/{resource}/instances` | Collection query | `/api/types/lun/instances` |
| `/api/instances/{resource}/{id}` | Instance query | `/api/instances/lun/sv_1` |
| `/api/instances/{resource}/{id}/action/{action}` | Actions | `/api/instances/lun/sv_1/action/modify` |

## Query Parameters

### Common Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `fields` | Comma-separated fields to return | `id,name,health` |
| `filter` | Unity filter expression | `severity eq 4` |
| `per_page` | Results per page (default: 2000) | `100` |
| `page` | Page number (starts at 1) | `2` |
| `compact` | Compact output format | `true` |

### Filter Syntax

Unity uses a different filter syntax than PowerStore:

```
# Equality
filter=severity eq 4

# Not equal
filter=state neq 0

# Like (wildcard)
filter=name lk "*prod*"

# Greater than
filter=sizeTotal gt 1000000000

# Combining filters
filter=severity eq 4 and isAcknowledged eq false
```

## Tool Examples

Each tool requires credentials to be passed with the request:

```json
{
    "tool_name": "getTypesAlertInstances",
    "arguments": {
        "host": "unity.example.com",
        "username": "admin",
        "password": "your-password",
        "fields": "id,message,severity,isAcknowledged",
        "queryParams": {
            "filter": "isAcknowledged eq false"
        }
    }
}
```

## Unity Resources

The Unity API exposes many resources including:

### Storage
- `lun` - LUN (Logical Unit Number) volumes
- `storageResource` - Storage resources
- `pool` - Storage pools
- `filesystem` - File systems
- `snap` - Snapshots

### Networking
- `nasServer` - NAS servers
- `cifsServer` - CIFS/SMB servers
- `nfsServer` - NFS servers
- `cifsShare` - CIFS shares
- `nfsShare` - NFS shares

### Monitoring
- `alert` - System alerts
- `event` - System events
- `metric` - Performance metrics

### Hardware
- `storageProcessor` - Storage processors
- `disk` - Physical disks
- `battery` - Batteries
- `fan` - Fans
- `powerSupply` - Power supplies

### System
- `system` - System information
- `basicSystemInfo` - Basic system info
- `user` - Users
- `host` - Host initiators

## Project Structure

```
unity_mcp/
├── __init__.py          # Package initialization
├── api_client.py        # Unity REST API client
├── config.py            # Configuration loader
├── exceptions.py        # Exception hierarchy
├── http_server.py       # HTTP/SSE transport server
├── logging_config.py    # Logging configuration
├── main.py              # stdio transport entry point
├── py.typed             # PEP 561 type marker
├── server.py            # MCP server implementation
└── tool_generator.py    # OpenAPI to MCP tool generator
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_OPENAPI_SPEC_PATH` | Path to OpenAPI spec (required) | - |
| `UNITY_HOST` | Default Unity host | `localhost` |
| `UNITY_USERNAME` | Default username | - |
| `UNITY_PASSWORD` | Default password | - |
| `HTTP_SERVER_PORT` | HTTP server port | `3000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_JSON` | Use JSON log format | `false` |
| `LOG_FILE` | Log file path | - |
| `MAX_RETRIES` | API retry attempts | `3` |
| `REQUEST_TIMEOUT` | Request timeout (ms) | `30000` |

## Obtaining Unity OpenAPI Spec

You can export the OpenAPI specification from your Unity system:

```bash
# Unity typically exposes API documentation at:
curl -k -u admin:password https://unity.example.com/api/swagger.json > unity-openapi.json

# Or check the Dell documentation portal for the API specification
```

## Docker Support

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY unity_mcp/ ./unity_mcp/
COPY unity-openapi.json .

ENV LOCAL_OPENAPI_SPEC_PATH=/app/unity-openapi.json
ENV HTTP_SERVER_PORT=3000

EXPOSE 3000

CMD ["uvicorn", "unity_mcp.http_server:app", "--host", "0.0.0.0", "--port", "3000"]
```

## License

MIT License

## Author

sachdev27
