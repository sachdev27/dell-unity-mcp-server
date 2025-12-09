# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2024-12-09

### Fixed
- Fixed all ruff linting errors (68 issues)
- Updated type annotations to use modern `X | None` syntax instead of `Optional[X]`
- Fixed import sorting across all modules
- Removed unused imports
- Updated pyproject.toml to use new `[tool.ruff.lint]` section format
- Fixed test for invalid JSON to use correct exception types

## [1.0.0] - 2024-12-09

### Added
- Initial release of Dell Unity MCP Server
- Full MCP (Model Context Protocol) compliance
- 359 auto-generated tools from Unity OpenAPI specification
- GET-only operations by default (configurable via `ALLOWED_HTTP_METHODS`)
- Credential-free architecture with per-request authentication
- SSE (Server-Sent Events) transport for real-time communication
- HTTP server with health endpoints
- Docker and Docker Compose support
- Comprehensive test suite (56 tests)
- Full type hints with `py.typed` marker

### Features
- **Storage Management**: Query LUNs, pools, filesystems, and storage resources
- **Alerts & Events**: Monitor system alerts, events, and jobs
- **Hardware Status**: Check storage processors, disks, batteries, fans, PSUs
- **Networking**: Query IP interfaces, Ethernet/FC ports, iSCSI portals
- **Replication**: Monitor replication sessions and remote systems
- **Hosts**: Manage host access, initiators, and host groups
- **Protection**: Query snapshots and snapshot schedules

### Security
- No credentials stored in server configuration
- Per-request authentication to Unity systems
- TLS verification configurable
- Non-root Docker container

### Documentation
- Comprehensive README with installation and usage instructions
- Architecture documentation
- API reference for all 359 tools
- n8n integration guide with prompt templates

[Unreleased]: https://github.com/sachdev27/dell-unity-mcp-server/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/sachdev27/dell-unity-mcp-server/releases/tag/v1.0.0
