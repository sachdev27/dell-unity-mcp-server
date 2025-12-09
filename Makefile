.PHONY: help install install-dev test lint format type-check clean build docker-build docker-run run-http run-stdio

# Default target
help:
	@echo "Dell Unity MCP Server - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install       Install production dependencies"
	@echo "  make install-dev   Install development dependencies"
	@echo "  make test          Run tests"
	@echo "  make lint          Run linter (ruff)"
	@echo "  make format        Format code (black + ruff)"
	@echo "  make type-check    Run type checker (mypy)"
	@echo ""
	@echo "Running:"
	@echo "  make run-stdio     Run MCP server in stdio mode (for Claude Desktop)"
	@echo "  make run-http      Run MCP server in HTTP mode"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run Docker container"
	@echo ""
	@echo "Build:"
	@echo "  make build         Build Python package"
	@echo "  make clean         Clean build artifacts"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testing
test:
	pytest tests/ -v --cov=unity_mcp --cov-report=term-missing

test-quick:
	pytest tests/ -v -x

# Code quality
lint:
	ruff check unity_mcp/ tests/

format:
	black unity_mcp/ tests/
	ruff check --fix unity_mcp/ tests/

type-check:
	mypy unity_mcp/

# All quality checks
check: lint type-check test

# Running the server
run-stdio:
	@echo "Starting Unity MCP Server in stdio mode..."
	@echo "Make sure LOCAL_OPENAPI_SPEC_PATH is set"
	python -m unity_mcp

run-http:
	@echo "Starting Unity MCP Server in HTTP mode on port 8000..."
	@echo "Make sure LOCAL_OPENAPI_SPEC_PATH is set"
	uvicorn unity_mcp.http_server:app --host 0.0.0.0 --port 8000 --reload

# Docker
docker-build:
	docker build -t dell-unity-mcp-server:latest .

docker-run:
	docker run -p 8000:8000 --rm dell-unity-mcp-server:latest

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

# Build package
build:
	python -m build

# Clean
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Convert swagger spec (if needed)
convert-spec:
	python convert_swagger_to_openapi.py
