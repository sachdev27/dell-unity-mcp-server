# Dell Unity MCP Server

A Model Context Protocol (MCP) server for Dell Unity Storage Systems, enabling AI-powered storage management through Claude and other MCP-compatible clients.

## Features

- **359 MCP Tools** - Full coverage of Dell Unity REST API operations
- **Per-Request Authentication** - Secure credential handling without persistent storage
- **Dual Transport** - Supports both stdio (Claude Desktop) and HTTP/SSE modes
- **OpenAPI-Driven** - Tools automatically generated from Unity's official API spec
- **Docker Ready** - Containerized deployment support

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Dell Unity storage system with REST API access
- Network connectivity to Unity management interface

### Installation

```bash
# Clone the repository
git clone https://github.com/dell/dell-unity-mcp-server.git
cd dell-unity-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Configuration

Set the required environment variable:

```bash
export LOCAL_OPENAPI_SPEC_PATH="/path/to/dell-unity-mcp-server/openapi.json"
```

### Running the Server

**For Claude Desktop (stdio mode):**
```bash
python -m unity_mcp
```

**For HTTP/SSE mode:**
```bash
uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 8000
```

## Claude Desktop Integration

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "dell-unity": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "unity_mcp"],
      "env": {
        "LOCAL_OPENAPI_SPEC_PATH": "/path/to/dell-unity-mcp-server/openapi.json"
      }
    }
  }
}
```

## Usage Examples

Once connected, you can ask Claude to interact with your Unity storage:

```
"List all LUNs on my Unity system at 192.168.1.100"
"Show me the storage pools and their capacity"
"Get all alerts with severity WARNING or higher"
"What is the health status of my Unity system?"
"List all NAS servers and their file systems"
```

Every request requires credentials:
- `unity_host`: Unity management IP or hostname
- `unity_username`: Admin username
- `unity_password`: Admin password

## API Coverage

The server provides tools for all Unity resource types:

| Category | Resources |
|----------|-----------|
| **Storage** | lun, pool, filesystem, storageResource, snap, quota |
| **Hosts** | host, hostGroup, hostInitiator, hostLUN |
| **Networking** | ipInterface, nasServer, cifsServer, nfsServer, dnsServer |
| **Monitoring** | alert, event, metric, job, system |
| **Protection** | snap, snapSchedule, replicationSession |
| **Hardware** | storageProcessor, disk, battery, fan, powerSupply |

Total: **147 resource types**, **359 tools**, **777 operations**

## Docker Deployment

```bash
# Build image
docker build -t dell-unity-mcp-server .

# Run container
docker run -p 8000:8000 dell-unity-mcp-server

# Or use docker-compose
docker-compose up -d
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
make test

# Run linter
make lint

# Format code
make format

# Type checking
make type-check
```

## Project Structure

```
dell-unity-mcp-server/
├── unity_mcp/              # Main package
│   ├── __init__.py         # Package exports
│   ├── server.py           # MCP server implementation
│   ├── api_client.py       # Unity REST API client
│   ├── tool_generator.py   # OpenAPI to MCP tool converter
│   ├── config.py           # Configuration management
│   ├── exceptions.py       # Exception hierarchy
│   ├── http_server.py      # HTTP/SSE transport
│   ├── main.py             # CLI entry point
│   └── logging_config.py   # Structured logging
├── openapi.json            # Unity OpenAPI 3.0 specification
├── spec.yml                # Original Unity Swagger spec
├── pyproject.toml          # Package configuration
├── Dockerfile              # Container build
├── docker-compose.yml      # Container orchestration
├── Makefile                # Build commands
└── requirements.txt        # Dependencies
```

## Security

- **No Credential Storage**: Credentials are passed per-request, never persisted
- **TLS Support**: Configurable TLS verification for Unity connections
- **Basic Auth**: Standard HTTP Basic Authentication to Unity API
- **Non-root Container**: Docker runs as unprivileged user

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## Support

- **Documentation**: [Dell Unity REST API Guide](https://www.dell.com/support)
- **Issues**: GitHub Issues
- **Dell Support**: [Dell Technologies Support](https://www.dell.com/support)
