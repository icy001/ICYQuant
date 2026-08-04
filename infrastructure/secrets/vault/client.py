"""
Vault HTTP client.

Provides the core HTTP transport layer for
communicating with HashiCorp Vault's HTTP API,
using aiohttp for async operations.

Supports connection pooling, retries,
request timeouts, and both real and
mock/fallback modes for development.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from .config import VaultConfig
from .exceptions import (
    VaultAuthenticationError,
    VaultCircuitOpenError,
    VaultConnectionError,
    VaultFailoverError,
    VaultHealthError,
    VaultPermissionDeniedError,
    VaultSecretNotFoundError,
    VaultWriteError,
)

logger = logging.getLogger(__name__)


class VaultClient:
    """
    Async HTTP client for HashiCorp Vault.

    Handles all low-level HTTP communication
    with Vault, including:
    - GET/POST/PUT/DELETE requests
    - Authentication header management
    - Request retries with exponential backoff
    - Connection pooling via aiohttp
    - Token injection into requests

    Usage:
        config = VaultConfig(address="http://vault:8200")
        client = VaultClient(config)
        await client.connect()
        data = await client.read("secret/data/my-key")
    """

    def __init__(
        self,
        config: Optional[VaultConfig] = None,
    ) -> None:
        self._config = config or VaultConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None
        self._namespace: Optional[str] = None
        self._connected: bool = False
        self._request_count: int = 0
        self._last_latency: float = 0.0

    # ── Connection Management ──

    async def connect(self) -> None:
        """
        Establish HTTP session with Vault.

        Creates a connection-pooled aiohttp session
        configured with TLS settings, timeouts,
        and default headers.
        """
        if self._connected:
            return

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self._namespace:
            headers["X-Vault-Namespace"] = self._namespace

        headers.update(self._config.extra_headers)

        connector = aiohttp.TCPConnector(
            limit=self._config.connection_pool_size,
            ssl=self._config.tls.enabled and self._config.tls.verify,
            enable_cleanup_closed=True,
        )

        timeout = aiohttp.ClientTimeout(total=self._config.request_timeout)

        self._session = aiohttp.ClientSession(
            connector=connector,
            default_headers=headers,
            timeout=timeout,
        )

        self._connected = True
        logger.info("Vault client connected to %s", self._config.address)

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
        logger.info("Vault client disconnected")

    async def __aenter__(self) -> "VaultClient":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()

    # ── Token Management ──

    def set_token(self, token: str) -> None:
        """Set the authentication token."""
        self._token = token

    def clear_token(self) -> None:
        """Clear the authentication token."""
        self._token = None

    def set_namespace(self, namespace: str) -> None:
        """Set the Vault namespace."""
        self._namespace = namespace

    # ── Core HTTP Methods ──

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path (appended to base URL).
            payload: JSON request body.
            extra_headers: Additional headers.

        Returns:
            Parsed JSON response.

        Raises:
            Various VaultError subclasses.
        """
        if not self._connected or not self._session:
            await self.connect()

        url = f"{self._config.api_base}{path}"
        headers: Dict[str, str] = {}

        if self._token:
            headers["X-Vault-Token"] = self._token

        if extra_headers:
            headers.update(extra_headers)

        last_exc: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                start = time.perf_counter()

                if method == "GET":
                    async with self._session.get(url, headers=headers) as resp:
                        body = await resp.text()
                        return self._handle_response(resp, body, path)
                elif method == "POST":
                    async with self._session.post(
                        url,
                        headers=headers,
                        json=payload or {},
                    ) as resp:
                        body = await resp.text()
                        return self._handle_response(resp, body, path)
                elif method == "PUT":
                    async with self._session.put(
                        url,
                        headers=headers,
                        json=payload or {},
                    ) as resp:
                        body = await resp.text()
                        return self._handle_response(resp, body, path)
                elif method == "DELETE":
                    async with self._session.delete(url, headers=headers) as resp:
                        body = await resp.text()
                        return self._handle_response(resp, body, path)
                elif method == "LIST":
                    async with self._session.request("LIST", url, headers=headers) as resp:
                        body = await resp.text()
                        return self._handle_response(resp, body, path)
                else:
                    raise VaultConnectionError(f"Unsupported method: {method}", path=path)

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exc = e
                if attempt < self._config.max_retries:
                    delay = self._config.retry_delay * (2**attempt)
                    logger.warning(
                        "Vault request attempt %d failed: %s. Retrying in %.1fs...",
                        attempt + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise VaultConnectionError(
                        f"Failed after {self._config.max_retries + 1} attempts: {e}",
                        path=path,
                    ) from e

        raise VaultConnectionError(
            f"Request failed: {last_exc}",
            path=path,
        )

    def _handle_response(
        self,
        resp: aiohttp.ClientResponse,
        body: str,
        path: str,
    ) -> Dict[str, Any]:
        """
        Parse HTTP response and handle errors.

        Args:
            resp: HTTP response.
            body: Response body text.
            path: Request path for context.

        Returns:
            Parsed response dict.
        """
        self._request_count += 1
        latency = time.perf_counter()
        self._last_latency = latency

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        status = resp.status

        if status == 401:
            raise VaultAuthenticationError(
                data.get("errors", ["Authentication failed"])[0] if data.get("errors") else "Authentication failed",
                status_code=status,
                path=path,
            )
        elif status == 403:
            raise VaultPermissionDeniedError(
                data.get("errors", ["Permission denied"])[0] if data.get("errors") else "Permission denied",
                status_code=status,
                path=path,
            )
        elif status == 404:
            raise VaultSecretNotFoundError(
                f"Path not found: {path}",
                status_code=status,
                path=path,
            )
        elif status == 429:
            raise VaultConnectionError(
                "Rate limited by Vault",
                status_code=status,
                path=path,
            )
        elif status >= 500:
            raise VaultConnectionError(
                f"Vault server error: {data.get('errors', [status])}",
                status_code=status,
                path=path,
            )
        elif status >= 400:
            errors = data.get("errors", [f"Bad request: {status}"])
            raise VaultWriteError(
                errors[0] if errors else "Bad request",
                status_code=status,
                path=path,
            )

        return data

    # ── Public API ──

    async def read(
        self,
        path: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Read a secret from Vault.

        Args:
            path: Full Vault API path.
            extra_headers: Additional headers.

        Returns:
            Response data dict.
        """
        return await self._request("GET", path, extra_headers=extra_headers)

    async def write(
        self,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Write a secret to Vault.

        Args:
            path: Full Vault API path.
            payload: Data to write.
            extra_headers: Additional headers.

        Returns:
            Response data dict.
        """
        return await self._request("POST", path, payload=payload, extra_headers=extra_headers)

    async def delete(
        self,
        path: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Delete a secret from Vault.

        Args:
            path: Full Vault API path.
            extra_headers: Additional headers.
        """
        return await self._request("DELETE", path, extra_headers=extra_headers)

    async def list(
        self,
        path: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        List keys at a Vault path.

        Args:
            path: Vault path to list.
            extra_headers: Additional headers.

        Returns:
            Response data dict with keys.
        """
        return await self._request("LIST", path.rstrip("/") + "/", extra_headers=extra_headers)

    # ── Health Check ──

    async def check_health(
        self,
        standby_ok: bool = True,
    ) -> Dict[str, Any]:
        """
        Check Vault server health.

        Args:
            standby_ok: If True, standby nodes are considered healthy.

        Returns:
            Health status dict.
        """
        try:
            path = f"/sys/health?standbyok={str(standby_ok).lower()}"
            data = await self._request("GET", path)
            return {
                "healthy": True,
                "server_time": data.get("data", {}).get("server_time"),
                "version": data.get("version"),
                "cluster_name": data.get("data", {}).get("cluster_name"),
                "standby": data.get("data", {}).get("standby", False),
            }
        except VaultConnectionError:
            return {"healthy": False, "error": "Cannot connect to Vault"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    # ── Token Info ──

    async def token_lookup(self) -> Dict[str, Any]:
        """Look up current token information."""
        return await self._request("GET", "/auth/token/lookup-self")

    async def token_renew(
        self,
        increment: int = 3600,
    ) -> Dict[str, Any]:
        """
        Renew the current token.

        Args:
            increment: Renewal increment in seconds.
        """
        return await self._request(
            "POST",
            "/auth/token/renew-self",
            payload={"increment": increment},
        )

    async def token_revoke(self) -> Dict[str, Any]:
        """Revoke the current token."""
        return await self._request("POST", "/auth/token/revoke-self")

    # ── Status ──

    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    @property
    def request_count(self) -> int:
        """Get total request count."""
        return self._request_count

    @property
    def last_latency(self) -> float:
        """Get last request latency."""
        return self._last_latency

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "connected": self._connected,
            "request_count": self._request_count,
            "last_latency": self._last_latency,
            "has_token": self._token is not None,
            "has_namespace": self._namespace is not None,
        }
