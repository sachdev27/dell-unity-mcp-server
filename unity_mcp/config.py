"""Configuration loader for Unity MCP Server.

This module provides configuration management using Pydantic models
for validation and environment variable loading.

Example:
    >>> from unity_mcp.config import load_config
    >>> config = load_config()
    >>> print(config.server.port)
    3000

Environment Variables:
    UNITY_HOST: Default Unity host (optional).
    UNITY_USERNAME: Default username (optional).
    UNITY_PASSWORD: Default password (optional).
    LOCAL_OPENAPI_SPEC_PATH: Path to OpenAPI spec file (required).
    HTTP_SERVER_PORT: HTTP server port (default: 3000).
    LOG_LEVEL: Logging level (default: INFO).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from .exceptions import ConfigurationError, EnvironmentVariableError
from .logging_config import get_logger

logger = get_logger(__name__)


class UnityConfig(BaseModel):
    """Unity connection configuration.

    Attributes:
        host: Unity host (optional, can be provided per-request).
        username: Unity username (optional).
        password: Unity password (optional).
        local_spec_path: Path to local OpenAPI spec file.
        tls_verify: Whether to verify TLS certificates.
    """

    host: str | None = Field(
        default="localhost",
        description="Unity host (optional, provided per-request)",
    )
    username: str | None = Field(
        default=None,
        description="Unity username (optional)",
    )
    password: str | None = Field(
        default=None,
        description="Unity password (optional)",
    )
    local_spec_path: str | None = Field(
        default=None,
        description="Local OpenAPI spec file path",
    )
    tls_verify: bool = Field(
        default=False,
        description="Verify TLS certificates",
    )

    @field_validator("local_spec_path")
    @classmethod
    def validate_spec_path(cls, v: str | None) -> str | None:
        """Validate that the OpenAPI spec path exists if provided.

        Args:
            v: The path value to validate.

        Returns:
            The validated path.

        Raises:
            ValueError: If the path doesn't exist.
        """
        if v is not None and not Path(v).exists():
            raise ValueError(f"OpenAPI spec file not found: {v}")
        return v

    model_config = {"extra": "ignore"}


class ServerConfig(BaseModel):
    """Server configuration.

    Attributes:
        port: HTTP server port.
        log_level: Logging level.
        log_json: Use JSON format for logs.
        log_file: Optional log file path.
        enable_endpoint_aggregation: Enable aggregated endpoints.
        cache_openapi_spec: Cache OpenAPI spec.
        openapi_cache_ttl: OpenAPI cache TTL in seconds.
        max_retries: Max API retry attempts.
        retry_delay: Retry delay in milliseconds.
        request_timeout: Request timeout in milliseconds.
    """

    port: int = Field(
        default=3000,
        ge=1,
        le=65535,
        description="HTTP server port",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_json: bool = Field(
        default=False,
        description="Use JSON format for logs",
    )
    log_file: str | None = Field(
        default=None,
        description="Optional log file path",
    )
    enable_endpoint_aggregation: bool = Field(
        default=True,
        description="Enable aggregated endpoints",
    )
    cache_openapi_spec: bool = Field(
        default=True,
        description="Cache OpenAPI spec",
    )
    openapi_cache_ttl: int = Field(
        default=3600,
        ge=0,
        description="OpenAPI cache TTL in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max API retry attempts",
    )
    retry_delay: int = Field(
        default=1000,
        ge=0,
        description="Retry delay in milliseconds",
    )
    request_timeout: int = Field(
        default=30000,
        ge=1000,
        description="Request timeout in milliseconds",
    )
    allowed_http_methods: list[str] = Field(
        default=["GET"],
        description="HTTP methods to generate tools for. Default is GET only for safe read-only operations. Set to ['GET', 'POST', 'DELETE', 'PATCH', 'PUT'] to enable all operations.",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level.

        Args:
            v: The log level to validate.

        Returns:
            The validated log level in uppercase.

        Raises:
            ValueError: If the log level is invalid.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    model_config = {"extra": "ignore"}


class Config(BaseModel):
    """Main configuration container.

    Attributes:
        unity: Unity connection configuration.
        server: Server configuration.
    """

    unity: UnityConfig
    server: ServerConfig

    model_config = {"extra": "ignore"}


def load_config(env_file: Path | None = None) -> Config:
    """Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file. If not provided,
                  searches for .env in the current directory.

    Returns:
        Validated configuration object.

    Raises:
        ConfigurationError: If configuration is invalid.
        EnvironmentVariableError: If required environment variable is missing.

    Example:
        >>> config = load_config()
        >>> print(config.server.port)
        3000
    """
    # Load environment variables from .env file
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    try:
        # Get spec path, treating empty string as None
        spec_path_value = os.getenv("LOCAL_OPENAPI_SPEC_PATH") or None

        unity_config = UnityConfig(
            host=os.getenv("UNITY_HOST", "localhost"),
            username=os.getenv("UNITY_USERNAME"),
            password=os.getenv("UNITY_PASSWORD"),
            local_spec_path=spec_path_value,
            tls_verify=os.getenv("NODE_TLS_REJECT_UNAUTHORIZED", "0") != "0",
        )
    except ValueError as e:
        raise ConfigurationError(f"Invalid Unity configuration: {e}") from e

    try:
        # Parse allowed HTTP methods from environment
        allowed_methods_env = os.getenv("ALLOWED_HTTP_METHODS")
        if allowed_methods_env:
            import json
            try:
                allowed_methods = json.loads(allowed_methods_env)
            except json.JSONDecodeError:
                # Try comma-separated format: "GET,POST,DELETE"
                allowed_methods = [m.strip().upper() for m in allowed_methods_env.split(",")]
        else:
            allowed_methods = ["GET"]  # Default to GET only

        server_config = ServerConfig(
            port=int(os.getenv("HTTP_SERVER_PORT", "3000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_json=os.getenv("LOG_JSON", "false").lower() == "true",
            log_file=os.getenv("LOG_FILE"),
            enable_endpoint_aggregation=os.getenv("ENABLE_ENDPOINT_AGGREGATION", "true").lower() == "true",
            cache_openapi_spec=os.getenv("CACHE_OPENAPI_SPEC", "true").lower() == "true",
            openapi_cache_ttl=int(os.getenv("OPENAPI_CACHE_TTL", "3600")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("RETRY_DELAY", "1000")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30000")),
            allowed_http_methods=allowed_methods,
        )
    except ValueError as e:
        raise ConfigurationError(f"Invalid server configuration: {e}") from e

    config = Config(unity=unity_config, server=server_config)

    # Check required configuration
    if not unity_config.local_spec_path:
        raise EnvironmentVariableError(
            "LOCAL_OPENAPI_SPEC_PATH",
            "OpenAPI specification path is required for tool generation",
        )

    # Log configuration summary
    if unity_config.username and unity_config.password:
        logger.info(
            "Configuration loaded: Default credentials available",
            extra={
                "mode": "with_defaults",
                "host": unity_config.host,
            },
        )
    else:
        logger.info(
            "Configuration loaded: Credential-free mode",
            extra={"mode": "credential_free"},
        )

    logger.debug(
        "Server configuration",
        extra={
            "port": server_config.port,
            "log_level": server_config.log_level,
            "timeout_ms": server_config.request_timeout,
        },
    )

    return config
