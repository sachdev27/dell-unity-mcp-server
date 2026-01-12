#!/bin/bash
# Start Dell Unity MCP Server in HTTP/SSE mode (for n8n and web clients)
#
# This script starts the MCP server with HTTP/SSE transport, which is used
# for n8n, web applications, and other HTTP-based clients.
#
# Usage:
#   ./start-http.sh [port] [host]
#
# Examples:
#   ./start-http.sh                  # Start on default port 8000
#   ./start-http.sh 3000            # Start on port 3000
#   ./start-http.sh 3000 0.0.0.0    # Start on port 3000, all interfaces
#
# Environment variables:
#   LOCAL_OPENAPI_SPEC_PATH - Path to OpenAPI spec (default: ./openapi.json)
#   ALLOWED_HTTP_METHODS    - Comma-separated HTTP methods (default: GET)
#   LOG_LEVEL               - Logging level (default: INFO)
#   LOG_FILE                - Optional log file path
#   TLS_VERIFY              - Verify SSL certificates (default: false)

set -e  # Exit on error

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
PORT="${1:-8000}"
HOST="${2:-127.0.0.1}"

echo -e "${GREEN}Starting Dell Unity MCP Server (HTTP/SSE mode)${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
else
    source venv/bin/activate
fi

# Check if OpenAPI spec exists
OPENAPI_SPEC="${LOCAL_OPENAPI_SPEC_PATH:-./openapi.json}"
if [ ! -f "$OPENAPI_SPEC" ]; then
    echo -e "${RED}Error: OpenAPI spec not found at $OPENAPI_SPEC${NC}"
    echo "Please set LOCAL_OPENAPI_SPEC_PATH or ensure openapi.json exists"
    exit 1
fi

# Set default environment variables if not set
export LOCAL_OPENAPI_SPEC_PATH="${LOCAL_OPENAPI_SPEC_PATH:-./openapi.json}"
export ALLOWED_HTTP_METHODS="${ALLOWED_HTTP_METHODS:-GET}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export TLS_VERIFY="${TLS_VERIFY:-false}"

echo -e "${GREEN}Configuration:${NC}"
echo "  OpenAPI Spec: $LOCAL_OPENAPI_SPEC_PATH"
echo "  Allowed Methods: $ALLOWED_HTTP_METHODS"
echo "  Log Level: $LOG_LEVEL"
echo "  TLS Verify: $TLS_VERIFY"
[ -n "$LOG_FILE" ] && echo "  Log File: $LOG_FILE"
echo ""
echo -e "${BLUE}Server will be available at:${NC}"
echo "  SSE Endpoint: http://$HOST:$PORT/sse"
echo "  Health Check: http://$HOST:$PORT/health"
echo ""

# Warning if methods other than GET are enabled
if [[ "$ALLOWED_HTTP_METHODS" != "GET" ]]; then
    echo -e "${YELLOW}⚠️  Warning: Write operations enabled!${NC}"
    echo "  Allowed methods: $ALLOWED_HTTP_METHODS"
    echo ""
fi

echo -e "${GREEN}Starting server...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Run the server with uvicorn
exec python -m uvicorn unity_mcp.http_server:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info \
    --access-log \
    --no-server-header
