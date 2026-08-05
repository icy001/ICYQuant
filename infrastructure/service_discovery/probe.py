"""Health probes for ICYQuant service discovery.

Provides an abstract ``Probe`` interface and concrete implementations
(``TCPProbe``, ``HTTPProbe``, ``GRPCProbe``, ``InternalProbe``) for
checking service instance health. ``ProbeResult`` captures the
outcome of a probe execution and ``ProbeFactory`` constructs probes
by type name.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """Result of a single probe execution.

    Attributes:
        success: Whether the probe succeeded.
        status: Human-readable status string (e.g. ``ok``, ``failed``).
        latency_ms: Round-trip latency in milliseconds.
        message: Additional context message.
        timestamp: When the probe was executed.
        details: Extra structured details.
    """

    success: bool
    status: str
    latency_ms: float
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the probe result to a dictionary."""
        return {
            "success": self.success,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
            if self.timestamp
            else None,
            "details": dict(self.details),
        }


class Probe(ABC):
    """Abstract base class for health probes."""

    @abstractmethod
    async def execute(self, target: str) -> Dict[str, Any]:
        """Execute the probe against ``target``.

        Args:
            target: The target descriptor (URL, host:port, etc.).

        Returns:
            A dictionary representation of a ``ProbeResult``.
        """

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the probe."""
        return {"probe_type": type(self).__name__}


class TCPProbe(Probe):
    """TCP connection probe.

    Performs a TCP connect against ``host:port`` and reports success
    based on whether a connection can be established within the
    configured timeout.

    Args:
        timeout: Connection timeout in seconds.
    """

    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = float(timeout) if timeout > 0 else 5.0
        self._lock = threading.RLock()
        self._exec_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def execute(self, target: str) -> Dict[str, Any]:
        """Execute a TCP connect probe.

        ``target`` may be ``host:port`` or just ``host`` (port 80).
        """
        host, port = self._parse_target(target)
        start = time.monotonic()
        loop = asyncio.get_event_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, self._tcp_connect, host, port),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            return self._record_failure(
                target, time.monotonic() - start, "tcp connect timeout"
            )
        except Exception as exc:
            return self._record_failure(
                target, time.monotonic() - start, str(exc)
            )
        return self._record_success(target, time.monotonic() - start)

    def _tcp_connect(self, host: str, port: int) -> None:
        with socket.create_connection(
            (host, port), timeout=self._timeout
        ) as sock:
            sock.settimeout(self._timeout)

    @staticmethod
    def _parse_target(target: str) -> tuple:
        if not target:
            return ("localhost", 80)
        if ":" in target:
            host, _, port = target.rpartition(":")
            try:
                return (host or "localhost", int(port))
            except ValueError:
                return (target, 80)
        return (target, 80)

    def _record_success(self, target: str, latency: float) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._success_count += 1
        return ProbeResult(
            success=True,
            status="ok",
            latency_ms=latency * 1000.0,
            message=f"TCP connect to {target} succeeded.",
            details={"target": target},
        ).to_dict()

    def _record_failure(
        self, target: str, latency: float, error: str
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._failure_count += 1
        return ProbeResult(
            success=False,
            status="failed",
            latency_ms=latency * 1000.0,
            message=f"TCP connect to {target} failed: {error}",
            details={"target": target, "error": error},
        ).to_dict()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "probe_type": "tcp",
                "timeout": self._timeout,
                "exec_count": self._exec_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
            }


class HTTPProbe(Probe):
    """HTTP health-check probe.

    Args:
        method: HTTP method (default ``GET``).
        headers: Optional request headers.
        expected_status: Expected HTTP status code (default 200).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        expected_status: int = 200,
        timeout: float = 5.0,
    ) -> None:
        self._method = method or "GET"
        self._headers = dict(headers) if headers else {}
        self._expected_status = int(expected_status) if expected_status else 200
        self._timeout = float(timeout) if timeout > 0 else 5.0
        self._lock = threading.RLock()
        self._exec_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def execute(self, target: str) -> Dict[str, Any]:
        """Execute an HTTP probe against ``target`` URL."""
        start = time.monotonic()
        loop = asyncio.get_event_loop()
        try:
            status_code, body = await asyncio.wait_for(
                loop.run_in_executor(
                    None, self._http_request, target
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            return self._record_failure(
                target, time.monotonic() - start, "http timeout"
            )
        except Exception as exc:
            return self._record_failure(
                target, time.monotonic() - start, str(exc)
            )

        latency = time.monotonic() - start
        if status_code == self._expected_status:
            return self._record_success(target, latency, status_code)
        return self._record_failure(
            target,
            latency,
            f"unexpected status {status_code} (expected {self._expected_status})",
            status_code=status_code,
        )

    def _http_request(self, url: str) -> tuple:
        """Perform a blocking HTTP request using urllib."""
        from urllib.request import Request, urlopen

        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"http://{url}"
        request = Request(url, method=self._method, headers=self._headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(request, timeout=self._timeout, context=ctx) as response:
            body = response.read()
            return (response.status, body)

    def _record_success(
        self, target: str, latency: float, status_code: int
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._success_count += 1
        return ProbeResult(
            success=True,
            status="ok",
            latency_ms=latency * 1000.0,
            message=f"HTTP {self._method} {target} returned {status_code}.",
            details={
                "target": target,
                "status_code": status_code,
                "method": self._method,
            },
        ).to_dict()

    def _record_failure(
        self,
        target: str,
        latency: float,
        error: str,
        status_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._failure_count += 1
        return ProbeResult(
            success=False,
            status="failed",
            latency_ms=latency * 1000.0,
            message=f"HTTP {self._method} {target} failed: {error}",
            details={
                "target": target,
                "error": error,
                "status_code": status_code,
                "method": self._method,
            },
        ).to_dict()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "probe_type": "http",
                "method": self._method,
                "expected_status": self._expected_status,
                "timeout": self._timeout,
                "exec_count": self._exec_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
            }


class GRPCProbe(Probe):
    """gRPC health-check probe.

    Performs a best-effort gRPC health check. Falls back to a TCP
    connect against the gRPC target when the ``grpc`` package is
    unavailable.

    Args:
        service: Optional gRPC service name for the health check.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        service: str = "",
        timeout: float = 5.0,
    ) -> None:
        self._service = service or ""
        self._timeout = float(timeout) if timeout > 0 else 5.0
        self._lock = threading.RLock()
        self._exec_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def execute(self, target: str) -> Dict[str, Any]:
        """Execute a gRPC health check against ``target``."""
        start = time.monotonic()
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._grpc_check, target),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            return self._record_failure(
                target, time.monotonic() - start, "grpc timeout"
            )
        except Exception as exc:
            return self._record_failure(
                target, time.monotonic() - start, str(exc)
            )

        latency = time.monotonic() - start
        if result.get("healthy"):
            return self._record_success(target, latency, result)
        return self._record_failure(
            target,
            latency,
            result.get("error", "grpc service unhealthy"),
            details=result,
        )

    def _grpc_check(self, target: str) -> Dict[str, Any]:
        """Perform the gRPC health check.

        Attempts to use the ``grpc_health`` module; falls back to a
        TCP connect check when grpc is unavailable.
        """
        try:
            import grpc  # type: ignore
            from grpc_health.v1 import (  # type: ignore
                health_pb2,
                health_pb2_grpc,
            )

            channel = grpc.insecure_channel(target)
            stub = health_pb2_grpc.HealthStub(channel)
            request = health_pb2.HealthCheckRequest(service=self._service)
            response = stub.Check(request, timeout=self._timeout)
            serving = response.status == health_pb2.HealthCheckResponse.SERVING
            return {
                "healthy": serving,
                "status": response.status,
                "service": self._service,
            }
        except ImportError:
            logger.debug(
                "grpc_health unavailable; falling back to TCP check."
            )
            host, port = TCPProbe._parse_target(target)
            with socket.create_connection(
                (host, port), timeout=self._timeout
            ):
                pass
            return {
                "healthy": True,
                "status": "tcp_fallback",
                "service": self._service,
            }

    def _record_success(
        self, target: str, latency: float, details: Dict[str, Any]
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._success_count += 1
        return ProbeResult(
            success=True,
            status="ok",
            latency_ms=latency * 1000.0,
            message=f"gRPC check to {target} succeeded.",
            details={"target": target, **details},
        ).to_dict()

    def _record_failure(
        self,
        target: str,
        latency: float,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._failure_count += 1
        return ProbeResult(
            success=False,
            status="failed",
            latency_ms=latency * 1000.0,
            message=f"gRPC check to {target} failed: {error}",
            details={"target": target, "error": error, **(details or {})},
        ).to_dict()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "probe_type": "grpc",
                "service": self._service,
                "timeout": self._timeout,
                "exec_count": self._exec_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
            }


class InternalProbe(Probe):
    """Internal function-call probe.

    Calls a user-supplied callable to determine health. The callable
    may be synchronous or asynchronous.

    Args:
        check_fn: Callable returning a bool or dict describing health.
    """

    def __init__(self, check_fn: Optional[Callable] = None) -> None:
        self._check_fn = check_fn
        self._lock = threading.RLock()
        self._exec_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def execute(self, target: str) -> Dict[str, Any]:
        """Execute the internal check function."""
        if self._check_fn is None:
            return ProbeResult(
                success=False,
                status="failed",
                latency_ms=0.0,
                message="No check function configured.",
                details={"target": target},
            ).to_dict()
        start = time.monotonic()
        try:
            result = self._check_fn()
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as exc:
            return self._record_failure(
                target, time.monotonic() - start, str(exc)
            )
        latency = time.monotonic() - start
        return self._handle_result(target, latency, result)

    def _handle_result(
        self, target: str, latency: float, result: Any
    ) -> Dict[str, Any]:
        if isinstance(result, dict):
            success = bool(result.get("success", result.get("healthy", False)))
            message = str(result.get("message", "internal check complete."))
            return self._record(
                success, target, latency, message, result
            )
        success = bool(result)
        return self._record(
            success,
            target,
            latency,
            "internal check complete." if success else "internal check failed.",
            {"raw": result},
        )

    def _record(
        self,
        success: bool,
        target: str,
        latency: float,
        message: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1
        return ProbeResult(
            success=success,
            status="ok" if success else "failed",
            latency_ms=latency * 1000.0,
            message=message,
            details={"target": target, **details},
        ).to_dict()

    def _record_failure(
        self, target: str, latency: float, error: str
    ) -> Dict[str, Any]:
        with self._lock:
            self._exec_count += 1
            self._failure_count += 1
        return ProbeResult(
            success=False,
            status="failed",
            latency_ms=latency * 1000.0,
            message=f"Internal check failed: {error}",
            details={"target": target, "error": error},
        ).to_dict()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "probe_type": "internal",
                "check_fn_set": self._check_fn is not None,
                "exec_count": self._exec_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
            }


class ProbeFactory:
    """Factory for creating probes by type name."""

    @staticmethod
    def create(probe_type: str, **kwargs: Any) -> Probe:
        """Create a probe of the given type.

        Args:
            probe_type: One of ``tcp``, ``http``, ``grpc``,
                ``internal``.
            **kwargs: Keyword arguments forwarded to the probe.

        Returns:
            A ``Probe`` instance.

        Raises:
            ValueError: If the probe type is unknown.
        """
        probe_type = (probe_type or "").lower().strip()
        if probe_type in ("tcp", "tcp_probe"):
            return TCPProbe(
                timeout=kwargs.get("timeout", 5.0),
            )
        if probe_type in ("http", "http_probe"):
            return HTTPProbe(
                method=kwargs.get("method", "GET"),
                headers=kwargs.get("headers"),
                expected_status=kwargs.get("expected_status", 200),
                timeout=kwargs.get("timeout", 5.0),
            )
        if probe_type in ("grpc", "grpc_probe"):
            return GRPCProbe(
                service=kwargs.get("service", ""),
                timeout=kwargs.get("timeout", 5.0),
            )
        if probe_type in ("internal", "internal_probe"):
            return InternalProbe(check_fn=kwargs.get("check_fn"))
        raise ValueError(f"Unknown probe type: {probe_type!r}")
