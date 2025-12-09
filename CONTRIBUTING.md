# Contributing to Dell Unity MCP Server

Thank you for your interest in contributing to Dell Unity MCP Server! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Issues

1. **Search existing issues** to avoid duplicates
2. **Use issue templates** when available
3. **Provide detailed information**:
   - Python version
   - Unity version
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages and logs

### Submitting Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Follow coding standards** (see below)
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Run tests** before submitting
6. **Write clear commit messages**

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Make (optional, for convenience commands)

### Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/dell-unity-mcp-server.git
cd dell-unity-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=unity_mcp --cov-report=html

# Run specific test file
pytest tests/test_tool_generator.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black unity_mcp tests

# Lint code
ruff check unity_mcp tests

# Type checking
mypy unity_mcp

# Run all checks
make lint
```

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use [Black](https://black.readthedocs.io/) for formatting
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Maximum line length: 100 characters

### Type Hints

- All public functions must have type hints
- Use `typing` module for complex types
- Run `mypy` to verify type correctness

### Documentation

- All public functions need docstrings (Google style)
- Update README.md for user-facing changes
- Add inline comments for complex logic

### Example Docstring

```python
def execute_operation(
    self,
    path: str,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an API operation against Unity.

    Args:
        path: API endpoint path (e.g., "/api/types/lun/instances").
        method: HTTP method (GET, POST, etc.).
        params: Optional query parameters.

    Returns:
        JSON response from the API.

    Raises:
        UnityAPIError: If the API request fails.
        UnityConnectionError: If connection to Unity fails.
    """
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add support for volume snapshots
fix: handle empty response from alerts API
docs: update installation instructions
test: add tests for tool generator
refactor: simplify API client error handling
```

## Project Structure

```
dell-unity-mcp-server/
├── unity_mcp/              # Main package
│   ├── __init__.py
│   ├── api_client.py       # Unity API client
│   ├── config.py           # Configuration management
│   ├── exceptions.py       # Custom exceptions
│   ├── http_server.py      # HTTP/SSE server
│   ├── logging_config.py   # Logging setup
│   ├── main.py             # Entry point
│   ├── server.py           # MCP server implementation
│   └── tool_generator.py   # OpenAPI to MCP tool converter
├── tests/                  # Test suite
├── openapi.json            # Unity OpenAPI specification
├── pyproject.toml          # Project configuration
└── README.md               # Documentation
```

## Adding New Features

### Adding a New Tool

Tools are auto-generated from the OpenAPI spec. To add custom tools:

1. Modify `tool_generator.py` to handle the new case
2. Add tests in `tests/test_tool_generator.py`
3. Update documentation

### Modifying API Client

1. Update `api_client.py`
2. Add/update tests in `tests/test_api_client.py`
3. Consider backward compatibility

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create a pull request
4. After merge, tag the release
5. GitHub Actions will publish to PyPI

## Getting Help

- Open an issue for questions
- Join discussions in GitHub Discussions
- Check existing documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
