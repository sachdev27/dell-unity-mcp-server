"""Unity API client with Basic Auth (no session required).

This module provides an async HTTP client for the Unity REST API
using Basic Authentication on every request.

Example:
    >>> async with UnityAPIClient(
    ...     host="unity.example.com",
    ...     username="admin",
    ...     password="secret",
    ... ) as client:
    ...     luns = await client.execute_operation("/api/types/lun/instances", "GET")
    ...     print(f"Found {len(luns)} LUNs")

Note:
    This client uses Basic Auth directly on each request, which is
    simpler and more stateless than session-based authentication.
    The Unity API accepts Basic Auth for all operations.

    Unity API URL structure:
    - Collection query: /api/types/{resource}/instances
    - Instance query: /api/instances/{resource}/{id}
    - Actions: /api/instances/{resource}/{id}/action/{action}
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urljoin

import httpx

from .exceptions import (
    APIResponseError,
    AuthenticationError,
    ConnectionError,
    RateLimitError,
)
from .logging_config import LoggerAdapter, get_logger

logger = get_logger(__name__)


class UnityAPIClient:
    """Unity API client using Basic Auth directly on each request.

    This client creates a new HTTP connection for each request, using
    Basic Authentication. No login session is maintained.

    The Unity REST API uses a different URL structure than PowerStore:
    - Collection queries: /api/types/{resource}/instances
    - Instance queries: /api/instances/{resource}/{id}
    - Actions: /api/instances/{resource}/{id}/action/{action}

    Attributes:
        host: Unity host address.
        base_url: Full base URL for API requests.

    Example:
        >>> client = UnityAPIClient(
        ...     host="unity.example.com",
        ...     username="admin",
        ...     password="secret",
        ... )
        >>> try:
        ...     result = await client.execute_operation("/api/types/alert/instances", "GET")
        ...     print(result)
        ... finally:
        ...     await client.close()
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        tls_verify: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize Unity API client.

        Args:
            host: Unity host (e.g., "unity.example.com").
            username: Unity username.
            password: Unity password.
            tls_verify: Whether to verify TLS certificates.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts for transient errors.

        Raises:
            ValueError: If host, username, or password is empty.
        """
        if not host:
            raise ValueError("host is required")
        if not username:
            raise ValueError("username is required")
        if not password:
            raise ValueError("password is required")

        self.host = host
        self.username = username
        self.password = password
        self.tls_verify = tls_verify
        self.timeout = timeout
        self.max_retries = max_retries

        # Unity API base URL
        self.base_url = f"https://{host}"

        # Create logger adapter with host context
        self._logger = LoggerAdapter(logger, {"host": host})

        # Create HTTP client with Basic Auth
        self.client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized.

        Returns:
            The initialized HTTP client.
        """
        if self.client is None:
            self.client = httpx.AsyncClient(
                verify=self.tls_verify,
                timeout=self.timeout,
                follow_redirects=True,
                auth=(self.username, self.password),
            )
        return self.client

    async def execute_operation(
        self,
        path: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Execute an API operation with Basic Auth.

        This method handles retries for transient errors and provides
        detailed logging for debugging.

        Args:
            path: API endpoint path (e.g., "/api/types/lun/instances").
            method: HTTP method (GET, POST, PUT, DELETE).
            params: Query parameters.
            body: Request body for POST/PUT requests.

        Returns:
            API response data (dict or list).

        Raises:
            AuthenticationError: If authentication fails (401).
            RateLimitError: If rate limit is exceeded (429).
            APIResponseError: For other API errors (4xx, 5xx).
            ConnectionError: If connection to host fails.

        Example:
            >>> result = await client.execute_operation(
            ...     path="/api/types/alert/instances",
            ...     method="GET",
            ...     params={"fields": "id,message,severity"},
            ... )
        """
        # Build full URL
        url = urljoin(self.base_url, path)

        # Prepare headers - Unity requires specific headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-EMC-REST-CLIENT": "true",  # Unity-specific header
        }

        self._logger.debug(
            f"Executing {method} {path}",
            extra={"params": params, "has_body": body is not None},
        )

        # Retry logic for transient errors
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._ensure_client()
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=body,
                    headers=headers,
                )

                # Handle error responses
                if response.status_code == 401:
                    raise AuthenticationError(
                        self.host,
                        details={"url": url, "method": method},
                    )
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise RateLimitError(
                        retry_after=int(retry_after) if retry_after else None,
                    )
                elif response.status_code >= 400:
                    raise APIResponseError(
                        message=f"API request failed: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                        details={"url": url, "method": method, "params": params},
                    )

                # Parse and return response
                if response.content:
                    data = response.json()
                    # Unity wraps collection responses in "entries" array
                    if isinstance(data, dict) and "entries" in data:
                        return data["entries"]
                    return data
                return {}

            except (AuthenticationError, RateLimitError, APIResponseError):
                # Don't retry client errors
                raise
            except httpx.ConnectError as e:
                raise ConnectionError(self.host, e) from e
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = 2**attempt  # Exponential backoff
                    self._logger.warning(
                        f"Request timeout, retrying in {wait_time}s",
                        extra={"attempt": attempt, "max_retries": self.max_retries},
                    )
                    await asyncio.sleep(wait_time)
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = 2**attempt
                    self._logger.warning(
                        f"Request error, retrying in {wait_time}s: {e}",
                        extra={"attempt": attempt, "max_retries": self.max_retries},
                    )
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        raise ConnectionError(
            self.host,
            last_error,
            f"Request failed after {self.max_retries} attempts",
        )

    async def health_check(self) -> bool:
        """Check if the Unity system is reachable.

        Returns:
            True if the system is reachable and authentication works.

        Example:
            >>> if await client.health_check():
            ...     print("Unity is healthy")
        """
        try:
            await self.execute_operation(
                "/api/types/basicSystemInfo/instances",
                "GET",
                params={"fields": "id"},
            )
            return True
        except Exception as e:
            self._logger.warning(f"Health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client and release resources.

        This method should be called when the client is no longer needed
        to properly clean up connections.
        """
        if self.client:
            await self.client.aclose()
            self.client = None
            self._logger.debug("HTTP client closed")

    async def __aenter__(self) -> UnityAPIClient:
        """Async context manager entry.

        Returns:
            The client instance.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Async context manager exit.

        Args:
            exc_type: Exception type if an error occurred.
            exc_val: Exception value if an error occurred.
            exc_tb: Exception traceback if an error occurred.
        """
        await self.close()
