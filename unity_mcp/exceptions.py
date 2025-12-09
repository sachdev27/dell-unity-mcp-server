"""Custom exceptions for Unity MCP Server.

This module defines a hierarchy of exceptions for precise error handling
throughout the application. All exceptions inherit from a base exception
class to allow catching all Unity-related errors with a single handler.

Example:
    >>> try:
    ...     await client.execute_operation("/api/types/lun/instances", "GET")
    ... except UnityAPIError as e:
    ...     logger.error(f"API call failed: {e}")
    ... except UnityMCPError as e:
    ...     logger.error(f"MCP operation failed: {e}")
"""

from typing import Any


class UnityMCPError(Exception):
    """Base exception for all Unity MCP Server errors.

    All custom exceptions in this package inherit from this class,
    allowing you to catch any Unity-related error with a single
    except clause.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional error context.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation of the exception."""
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary with error information.
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(UnityMCPError):
    """Raised when server configuration is invalid or missing.

    This exception is raised during server startup when required
    configuration values are missing or invalid.

    Example:
        >>> if not config.local_spec_path:
        ...     raise ConfigurationError(
        ...         "OpenAPI spec path is required",
        ...         details={"env_var": "LOCAL_OPENAPI_SPEC_PATH"}
        ...     )
    """

    pass


class EnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing or invalid.

    Attributes:
        variable_name: Name of the missing/invalid environment variable.
    """

    def __init__(
        self,
        variable_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            variable_name: Name of the missing/invalid environment variable.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.variable_name = variable_name
        msg = message or f"Required environment variable not set: {variable_name}"
        super().__init__(msg, details={"variable": variable_name, **(details or {})})


# =============================================================================
# API Errors
# =============================================================================


class UnityAPIError(UnityMCPError):
    """Base exception for Unity API errors.

    This is the base class for all errors that occur during
    communication with the Unity REST API.

    Attributes:
        status_code: HTTP status code from the API response.
        response_body: Raw response body from the API.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code from the API response.
            response_body: Raw response body from the API.
            details: Optional additional details.
        """
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(
            message,
            details={
                "status_code": status_code,
                "response_body": response_body,
                **(details or {}),
            },
        )


class AuthenticationError(UnityAPIError):
    """Raised when API authentication fails.

    This exception indicates that the provided credentials
    were rejected by the Unity system.
    """

    def __init__(
        self,
        host: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            host: Unity host that rejected authentication.
            message: Optional custom message.
            details: Optional additional details.
        """
        msg = message or f"Authentication failed for host: {host}"
        super().__init__(msg, status_code=401, details={"host": host, **(details or {})})


class ConnectionError(UnityAPIError):
    """Raised when connection to Unity fails.

    This exception indicates network-level failures such as
    DNS resolution failures, connection timeouts, or TLS errors.
    """

    def __init__(
        self,
        host: str,
        original_error: Exception | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            host: Unity host that could not be reached.
            original_error: The underlying exception that caused the failure.
            message: Optional custom message.
            details: Optional additional details.
        """
        msg = message or f"Failed to connect to Unity host: {host}"
        if original_error:
            msg = f"{msg} - {original_error}"
        super().__init__(
            msg,
            details={
                "host": host,
                "original_error": str(original_error) if original_error else None,
                **(details or {}),
            },
        )


class APIResponseError(UnityAPIError):
    """Raised when the API returns an error response.

    This exception is raised for HTTP 4xx and 5xx responses
    from the Unity API.
    """

    pass


class RateLimitError(UnityAPIError):
    """Raised when API rate limit is exceeded.

    The Unity API may rate-limit requests to prevent overload.
    This exception indicates that the client should back off and retry.

    Attributes:
        retry_after: Suggested wait time in seconds before retrying.
    """

    def __init__(
        self,
        retry_after: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            retry_after: Suggested wait time in seconds before retrying.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.retry_after = retry_after
        msg = message or "API rate limit exceeded"
        if retry_after:
            msg = f"{msg}. Retry after {retry_after} seconds."
        super().__init__(
            msg, status_code=429, details={"retry_after": retry_after, **(details or {})}
        )


# =============================================================================
# Tool Errors
# =============================================================================


class ToolError(UnityMCPError):
    """Base exception for MCP tool-related errors.

    This is the base class for errors that occur during
    MCP tool generation or execution.
    """

    pass


class ToolNotFoundError(ToolError):
    """Raised when a requested tool does not exist.

    Attributes:
        tool_name: Name of the tool that was not found.
    """

    def __init__(
        self,
        tool_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            tool_name: Name of the tool that was not found.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.tool_name = tool_name
        msg = message or f"Unknown tool: {tool_name}"
        super().__init__(msg, details={"tool_name": tool_name, **(details or {})})


class ToolExecutionError(ToolError):
    """Raised when tool execution fails.

    This exception wraps errors that occur during the execution
    of an MCP tool.

    Attributes:
        tool_name: Name of the tool that failed.
        original_error: The underlying exception that caused the failure.
    """

    def __init__(
        self,
        tool_name: str,
        original_error: Exception | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            tool_name: Name of the tool that failed.
            original_error: The underlying exception that caused the failure.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.tool_name = tool_name
        self.original_error = original_error
        msg = message or f"Failed to execute tool: {tool_name}"
        if original_error:
            msg = f"{msg} - {original_error}"
        super().__init__(
            msg,
            details={
                "tool_name": tool_name,
                "original_error": str(original_error) if original_error else None,
                **(details or {}),
            },
        )


class InvalidToolArgumentsError(ToolError):
    """Raised when tool arguments are invalid or missing.

    Attributes:
        tool_name: Name of the tool.
        missing_args: List of missing required arguments.
        invalid_args: Dict mapping invalid argument names to error messages.
    """

    def __init__(
        self,
        tool_name: str,
        missing_args: list[str] | None = None,
        invalid_args: dict[str, str] | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            tool_name: Name of the tool.
            missing_args: List of missing required arguments.
            invalid_args: Dict mapping invalid argument names to error messages.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.tool_name = tool_name
        self.missing_args = missing_args or []
        self.invalid_args = invalid_args or {}

        msg = message or f"Invalid arguments for tool: {tool_name}"
        if self.missing_args:
            msg = f"{msg}. Missing: {', '.join(self.missing_args)}"
        if self.invalid_args:
            msg = f"{msg}. Invalid: {self.invalid_args}"

        super().__init__(
            msg,
            details={
                "tool_name": tool_name,
                "missing_args": self.missing_args,
                "invalid_args": self.invalid_args,
                **(details or {}),
            },
        )


# =============================================================================
# OpenAPI Errors
# =============================================================================


class OpenAPIError(UnityMCPError):
    """Base exception for OpenAPI specification errors.

    This is the base class for errors related to loading
    or parsing OpenAPI specifications.
    """

    pass


class OpenAPILoadError(OpenAPIError):
    """Raised when OpenAPI specification cannot be loaded.

    Attributes:
        file_path: Path to the OpenAPI spec file.
    """

    def __init__(
        self,
        file_path: str,
        original_error: Exception | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            file_path: Path to the OpenAPI spec file.
            original_error: The underlying exception that caused the failure.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.file_path = file_path
        msg = message or f"Failed to load OpenAPI spec: {file_path}"
        if original_error:
            msg = f"{msg} - {original_error}"
        super().__init__(
            msg,
            details={
                "file_path": file_path,
                "original_error": str(original_error) if original_error else None,
                **(details or {}),
            },
        )


class OpenAPIParseError(OpenAPIError):
    """Raised when OpenAPI specification cannot be parsed.

    Attributes:
        file_path: Path to the OpenAPI spec file.
    """

    def __init__(
        self,
        file_path: str,
        original_error: Exception | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            file_path: Path to the OpenAPI spec file.
            original_error: The underlying exception that caused the failure.
            message: Optional custom message.
            details: Optional additional details.
        """
        self.file_path = file_path
        msg = message or f"Failed to parse OpenAPI spec: {file_path}"
        if original_error:
            msg = f"{msg} - {original_error}"
        super().__init__(
            msg,
            details={
                "file_path": file_path,
                "original_error": str(original_error) if original_error else None,
                **(details or {}),
            },
        )
