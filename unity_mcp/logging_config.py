"""Logging configuration for Unity MCP Server.

This module provides structured logging with configurable formatters,
handlers, and log levels. It supports both console and file logging
with JSON formatting option for production environments.

Example:
    >>> from unity_mcp.logging_config import setup_logging, get_logger
    >>> setup_logging(log_level="DEBUG", json_format=True)
    >>> logger = get_logger(__name__)
    >>> logger.info("Server started", extra={"port": 3000})
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# Define custom log levels
TRACE = 5
logging.addLevelName(TRACE, "TRACE")

# Package logger
PACKAGE_NAME = "unity_mcp"


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging in production.

    Outputs log records as JSON objects with consistent structure
    for easy parsing by log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info
        if record.pathname:
            log_data["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                if "extra" not in log_data:
                    log_data["extra"] = {}
                log_data["extra"][key] = value

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development.

    Uses ANSI color codes to highlight different log levels
    for easier reading during development.
    """

    # ANSI color codes
    COLORS = {
        "TRACE": "\033[90m",     # Dark gray
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        use_colors: bool = True,
    ) -> None:
        """Initialize the formatter.

        Args:
            fmt: Log message format string.
            datefmt: Date format string.
            use_colors: Whether to use ANSI colors.
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors.

        Args:
            record: The log record to format.

        Returns:
            Formatted log string.
        """
        # Save original values
        original_levelname = record.levelname
        original_msg = record.msg

        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            record.levelname = f"{color}{self.BOLD}{record.levelname:8}{self.RESET}"
            # Color the message based on level
            if record.levelno >= logging.ERROR:
                record.msg = f"{self.COLORS['ERROR']}{record.msg}{self.RESET}"
            elif record.levelno >= logging.WARNING:
                record.msg = f"{self.COLORS['WARNING']}{record.msg}{self.RESET}"

        result = super().format(record)

        # Restore original values
        record.levelname = original_levelname
        record.msg = original_msg

        return result


class RequestContextFilter(logging.Filter):
    """Filter that adds request context to log records.

    This filter can be used to add contextual information
    like request IDs or user information to all log records.
    """

    def __init__(self, name: str = "", context: Optional[dict[str, Any]] = None) -> None:
        """Initialize the filter.

        Args:
            name: Logger name to filter.
            context: Default context to add to all records.
        """
        super().__init__(name)
        self._context = context or {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record.

        Args:
            record: The log record to filter.

        Returns:
            True (always allows the record through).
        """
        for key, value in self._context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True

    def update_context(self, **kwargs: Any) -> None:
        """Update the context values.

        Args:
            **kwargs: Context key-value pairs to update.
        """
        self._context.update(kwargs)


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """Configure logging for the Unity MCP Server.

    This function sets up logging handlers with appropriate formatters
    based on the environment (development vs production).

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: Use JSON formatting for structured logging.
        log_file: Optional file path for file logging.
        max_bytes: Maximum size of log file before rotation.
        backup_count: Number of backup log files to keep.

    Returns:
        The configured root logger for the package.

    Example:
        >>> setup_logging(log_level="DEBUG", json_format=False)
        >>> logger = logging.getLogger("unity_mcp")
        >>> logger.info("Server started")
    """
    # Get or create package logger
    logger = logging.getLogger(PACKAGE_NAME)

    # Clear existing handlers
    logger.handlers.clear()

    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Don't propagate to root logger
    logger.propagate = False

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)

    if json_format:
        console_handler.setFormatter(StructuredFormatter())
    else:
        # Colored formatter for development
        fmt = "%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        # Only use colors if outputting to a terminal
        use_colors = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        console_handler.setFormatter(ColoredFormatter(fmt, datefmt, use_colors))

    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(level)
        # Always use JSON format for file logs
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)

    # Also configure third-party loggers
    for name in ["httpx", "uvicorn", "mcp"]:
        third_party = logging.getLogger(name)
        third_party.setLevel(max(level, logging.WARNING))

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger that is a child of the package logger.

    Args:
        name: Module name (typically __name__).

    Returns:
        A logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request")
    """
    if name.startswith(PACKAGE_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{PACKAGE_NAME}.{name}")


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter with additional context support.

    This adapter allows adding persistent context to all log messages
    from a particular component.

    Example:
        >>> logger = get_logger(__name__)
        >>> adapter = LoggerAdapter(logger, {"component": "api_client"})
        >>> adapter.info("Request sent", extra={"url": "/api/types/lun"})
    """

    def process(
        self, msg: str, kwargs: Any
    ) -> tuple[str, Any]:
        """Process the log message and kwargs.

        Args:
            msg: The log message.
            kwargs: Keyword arguments for the log call.

        Returns:
            Tuple of (message, kwargs) with extra context added.
        """
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs
