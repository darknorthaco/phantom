"""HTTP transport implementation"""

import logging
from typing import Any, Dict, Optional, Tuple
import httpx
from ..interfaces import TransportAdapter, TransportError, ConnectionError

logger = logging.getLogger(__name__)


class HTTPTransport(TransportAdapter):
    """
    HTTP/HTTPS transport implementation using httpx

    Supports both synchronous and asynchronous HTTP requests.
    Designed for request/response patterns (not streaming).
    """

    def __init__(self, timeout: float = 30.0, verify_ssl: bool = True):
        """
        Initialize HTTP transport

        Args:
            timeout: Default timeout in seconds
            verify_ssl: Verify SSL certificates
        """
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.client: Optional[httpx.AsyncClient] = None
        self.endpoint: Optional[str] = None
        self._is_connected = False

    async def connect(self, endpoint: str, **kwargs) -> None:
        """
        Establish HTTP client connection

        Args:
            endpoint: Base URL for HTTP requests
            **kwargs: Additional httpx client options

        Raises:
            ConnectionError: If connection cannot be established
        """
        try:
            self.endpoint = endpoint

            # Create async HTTP client
            self.client = httpx.AsyncClient(
                timeout=kwargs.get("timeout", self.timeout),
                verify=kwargs.get("verify_ssl", self.verify_ssl),
                follow_redirects=True,
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["timeout", "verify_ssl"]
                },
            )

            # Test connection with a HEAD request
            try:
                response = await self.client.head(endpoint, timeout=5.0)
                logger.debug(
                    f"HTTP connection test to {endpoint}: {response.status_code}"
                )
            except Exception as e:
                logger.warning(f"HTTP connection test failed (may be normal): {e}")

            self._is_connected = True
            logger.info(f"HTTP transport connected to {endpoint}")

        except Exception as e:
            logger.error(f"HTTP connection failed: {e}")
            raise ConnectionError(f"HTTP connection failed: {e}") from e

    async def disconnect(self) -> None:
        """
        Close HTTP client connection

        Raises:
            ConnectionError: If disconnect fails
        """
        try:
            if self.client:
                await self.client.aclose()
                self.client = None

            self._is_connected = False
            logger.info("HTTP transport disconnected")

        except Exception as e:
            logger.error(f"HTTP disconnect failed: {e}")
            raise ConnectionError(f"HTTP disconnect failed: {e}") from e

    async def send(
        self, message: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send HTTP POST request

        Args:
            message: Message bytes to send
            metadata: Optional metadata (headers, path, method, etc.)

        Raises:
            TransportError: If send fails
        """
        if not self._is_connected or not self.client:
            raise TransportError("HTTP transport not connected")

        try:
            metadata = metadata or {}
            method = metadata.get("method", "POST")
            path = metadata.get("path", "")
            headers = metadata.get("headers", {})

            url = f"{self.endpoint}{path}"

            # Set content type if not provided
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/octet-stream"

            response = await self.client.request(
                method=method, url=url, content=message, headers=headers
            )

            # Check for errors
            response.raise_for_status()

            logger.debug(f"HTTP {method} sent to {url}: {response.status_code}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP send failed with status {e.response.status_code}: {e}")
            raise TransportError(f"HTTP send failed: {e}") from e
        except Exception as e:
            logger.error(f"HTTP send failed: {e}")
            raise TransportError(f"HTTP send failed: {e}") from e

    async def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Receive HTTP response

        Note: HTTP is request/response, so this is typically used via send_and_receive.
        This method is provided for compatibility but may not be useful standalone.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (response bytes, metadata dict)

        Raises:
            TransportError: HTTP doesn't support standalone receive
        """
        raise TransportError(
            "HTTP transport requires send_and_receive for request/response pattern"
        )

    async def send_and_receive(
        self,
        message: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Send HTTP request and wait for response

        Args:
            message: Message bytes to send
            metadata: Optional metadata (headers, path, method, etc.)
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (response bytes, response metadata)

        Raises:
            TransportError: If send or receive fails
        """
        if not self._is_connected or not self.client:
            raise TransportError("HTTP transport not connected")

        try:
            metadata = metadata or {}
            method = metadata.get("method", "POST")
            path = metadata.get("path", "")
            headers = metadata.get("headers", {})

            url = f"{self.endpoint}{path}"

            # Set content type if not provided
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/octet-stream"

            # Use custom timeout if provided
            request_timeout = timeout if timeout is not None else self.timeout

            response = await self.client.request(
                method=method,
                url=url,
                content=message,
                headers=headers,
                timeout=request_timeout,
            )

            # Check for errors
            response.raise_for_status()

            # Extract response metadata
            response_metadata = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_type": response.headers.get("Content-Type", ""),
            }

            logger.debug(f"HTTP {method} request to {url}: {response.status_code}")

            return response.content, response_metadata

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP request failed with status {e.response.status_code}: {e}"
            )
            raise TransportError(f"HTTP request failed: {e}") from e
        except httpx.TimeoutException as e:
            logger.error(f"HTTP request timed out: {e}")
            raise TimeoutError(f"HTTP request timed out: {e}") from e
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            raise TransportError(f"HTTP request failed: {e}") from e

    @property
    def is_connected(self) -> bool:
        """Check if transport is connected"""
        return self._is_connected and self.client is not None

    @property
    def name(self) -> str:
        """Transport name"""
        return "http"
