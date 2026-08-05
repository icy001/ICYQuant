"""Health checker for ICYQuant service discovery.

Provides ``HealthChecker`` for executing health probes against
service instances. Delegates probe creation to ``ProbeFactory`` and
maintains a registry of custom probes. Thread-safe.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .exceptions import ServiceDiscoveryError
from .probe import HTTPProbe, Probe, ProbeFactory, TCPProbe, GRPCProbe

logger = logging.getLogger(__name__)


class HealthChecker:
    """Executes health probes against service instances.

    Maintains a registry of named probes (tcp, http, grpc, internal
    by default) and supports custom probes. Thread-safe.

    Args:
        default_timeout: Default timeout for probes in seconds.
    """

    def __init__(self, default_timeout: float = 5.0) -> None:
        self._default_timeout = float(default_timeout) if default_timeout > 0 else 5.0
        self._lock = threading.RLock()
        self._probes: Dict[str, Probe] = {
            "tcp": TCPProbe(timeout=self._default_timeout),
            "http": HTTPProbe(timeout=self._default_timeout),
            "grpc": GRPCProbe(timeout=self._default_timeout),
        }
        self._check_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_results: Dict[str, Dict[str, Any]] = {}

    # ── Public API ──

    async def check(
        self,
        service_name: str,
        instance_id: str,
        probe_type: str = "tcp",
    ) -> Dict[str, Any]:
        """Run a health check against an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            probe_type: Probe name (default ``tcp``).

        Returns:
            A dictionary describing the check result, including
            ``service_name``, ``instance_id``, and the probe outcome.
        """
        probe = self.get_probe(probe_type)
        target = self._resolve_target(service_name, instance_id)
        start = time.monotonic()
        try:
            result = await probe.execute(target)
        except Exception as exc:
            latency = time.monotonic() - start
            result = {
                "success": False,
                "status": "failed",
                "latency_ms": latency * 1000.0,
                "message": f"Health check error: {exc}",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"error": str(exc)},
            }

        outcome = {
            "service_name": service_name,
            "instance_id": instance_id,
            "probe_type": probe_type,
            "target": target,
            "result": result,
            "checked_at": datetime.utcnow().isoformat(),
        }
        self._record_outcome(service_name, instance_id, outcome)
        return outcome

    async def check_tcp(
        self, host: str, port: int, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Run a TCP health check against ``host:port``."""
        probe = TCPProbe(timeout=timeout if timeout > 0 else self._default_timeout)
        return await probe.execute(f"{host}:{port}")

    async def check_http(
        self, url: str, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Run an HTTP health check against ``url``."""
        probe = HTTPProbe(timeout=timeout if timeout > 0 else self._default_timeout)
        return await probe.execute(url)

    async def check_grpc(
        self, target: str, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Run a gRPC health check against ``target``."""
        probe = GRPCProbe(timeout=timeout if timeout > 0 else self._default_timeout)
        return await probe.execute(target)

    async def check_internal(self, check_fn: Callable) -> Dict[str, Any]:
        """Run an internal (function-call) health check."""
        from .probe import InternalProbe

        probe = InternalProbe(check_fn=check_fn)
        return await probe.execute("internal")

    def register_custom_probe(self, name: str, probe: Probe) -> None:
        """Register a custom probe under ``name``.

        Args:
            name: Probe name.
            probe: ``Probe`` instance.
        """
        if not isinstance(probe, Probe):
            raise ServiceDiscoveryError(
                f"Expected Probe instance, got {type(probe).__name__}."
            )
        with self._lock:
            self._probes[name] = probe
        logger.info("Registered custom probe '%s'.", name)

    def get_probe(self, name: str = "tcp") -> Probe:
        """Return the probe registered under ``name``.

        Falls back to creating a probe via ``ProbeFactory`` when the
        name is not pre-registered.
        """
        with self._lock:
            probe = self._probes.get(name)
        if probe is not None:
            return probe
        try:
            return ProbeFactory.create(name, timeout=self._default_timeout)
        except ValueError as exc:
            raise ServiceDiscoveryError(str(exc)) from exc

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the health checker."""
        with self._lock:
            probe_stats = {
                name: probe.get_stats() for name, probe in self._probes.items()
            }
            return {
                "default_timeout": self._default_timeout,
                "registered_probes": list(self._probes.keys()),
                "check_count": self._check_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "last_results_count": len(self._last_results),
                "probes": probe_stats,
            }

    # ── Internal helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def _resolve_target(self, service_name: str, instance_id: str) -> str:
        """Resolve a check target from the last known instance info.

        Falls back to ``service_name:instance_id`` when no host/port
        information is available.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            last = self._last_results.get(key)
        if last and last.get("target"):
            return last["target"]
        return f"{service_name}:{instance_id}"

    def _record_outcome(
        self,
        service_name: str,
        instance_id: str,
        outcome: Dict[str, Any],
    ) -> None:
        key = self._make_key(service_name, instance_id)
        with self._lock:
            self._check_count += 1
            result = outcome.get("result", {})
            if result.get("success"):
                self._success_count += 1
            else:
                self._failure_count += 1
            self._last_results[key] = outcome

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HealthChecker(probes={len(self._probes)}, "
                f"checks={self._check_count})"
            )
