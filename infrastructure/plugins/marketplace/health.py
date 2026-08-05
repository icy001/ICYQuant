"""Marketplace health checks.

Provides :class:`MarketplaceHealth` for running health probes
against marketplace repositories, cache, and registry components,
producing an aggregate health report.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _HealthProbeResult:
    """Result of a single health probe."""

    name: str
    healthy: bool
    message: str
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the result to a dictionary."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "details": dict(self.details),
        }


class MarketplaceHealth:
    """Unified health check for the marketplace system.

    Runs probes against configured repositories, cache, and
    registry to produce an aggregate health report.

    Attributes:
        _repositories: List of repository configurations to probe.
        _cache: Optional cache component to check.
        _registry: Optional registry component to check.
    """

    def __init__(
        self,
        repositories: Optional[List[Any]] = None,
        cache: Optional[Any] = None,
        registry: Optional[Any] = None,
    ) -> None:
        self._repositories = repositories or []
        self._cache = cache
        self._registry = registry
        self._last_results: List[_HealthProbeResult] = []
        self._last_check_time: float = 0.0

    async def check(self) -> Dict[str, Any]:
        """Run all health checks and return a combined result.

        Returns:
            Dictionary with overall health status and individual
            check results.
        """
        start = time.monotonic()
        results: List[_HealthProbeResult] = []

        repo_results = self.check_repositories()
        for rr in repo_results:
            results.append(
                _HealthProbeResult(
                    name=f"repository:{rr.get('name', 'unknown')}",
                    healthy=rr.get("healthy", False),
                    message=rr.get("message", ""),
                    latency_ms=rr.get("latency_ms", 0.0),
                    details=rr.get("details", {}),
                )
            )

        cache_result = self.check_cache()
        results.append(
            _HealthProbeResult(
                name="cache",
                healthy=cache_result.get("healthy", False),
                message=cache_result.get("message", ""),
                latency_ms=cache_result.get("latency_ms", 0.0),
                details=cache_result.get("details", {}),
            )
        )

        registry_result = self.check_registry()
        results.append(
            _HealthProbeResult(
                name="registry",
                healthy=registry_result.get("healthy", False),
                message=registry_result.get("message", ""),
                latency_ms=registry_result.get("latency_ms", 0.0),
                details=registry_result.get("details", {}),
            )
        )

        overall_healthy = all(r.healthy for r in results)
        total_latency = (time.monotonic() - start) * 1000.0

        self._last_results = results
        self._last_check_time = time.time()

        return {
            "healthy": overall_healthy,
            "timestamp": self._last_check_time,
            "total_latency_ms": total_latency,
            "checks": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "healthy_count": sum(
                    1 for r in results if r.healthy
                ),
                "unhealthy_count": sum(
                    1 for r in results if not r.healthy
                ),
            },
        }

    def check_repositories(
        self,
    ) -> List[Dict[str, Any]]:
        """Check connectivity to configured repositories.

        Returns:
            A list of per-repository health check result dictionaries.
        """
        results: List[Dict[str, Any]] = []
        if not self._repositories:
            results.append({
                "name": "default",
                "healthy": True,
                "message": "No repositories configured; skipping.",
                "latency_ms": 0.0,
                "details": {},
            })
            return results

        for repo in self._repositories:
            check_start = time.monotonic()
            repo_name = getattr(repo, "name", str(repo))
            repo_url = getattr(repo, "url", "")

            try:
                healthy = True
                message = f"Repository '{repo_name}' is reachable."
                details: Dict[str, Any] = {"url": repo_url}

                ping_method = getattr(repo, "ping", None)
                if callable(ping_method):
                    ping_result = ping_method()
                    if isinstance(ping_result, bool):
                        healthy = ping_result
                    elif isinstance(ping_result, dict):
                        healthy = ping_result.get("healthy", True)
                    if not healthy:
                        message = (
                            f"Repository '{repo_name}' ping failed."
                        )

                results.append({
                    "name": repo_name,
                    "healthy": healthy,
                    "message": message,
                    "latency_ms": (time.monotonic() - check_start)
                    * 1000.0,
                    "details": details,
                })
            except Exception as exc:
                logger.error(
                    "Repository check failed for '%s': %s",
                    repo_name,
                    exc,
                )
                results.append({
                    "name": repo_name,
                    "healthy": False,
                    "message": f"Repository check failed: {exc}",
                    "latency_ms": (time.monotonic() - check_start)
                    * 1000.0,
                    "details": {"error": str(exc)},
                })

        return results

    def check_cache(self) -> Dict[str, Any]:
        """Check cache health.

        Returns:
            A dictionary with cache health status and details.
        """
        check_start = time.monotonic()
        if self._cache is None:
            return {
                "healthy": True,
                "message": "No cache configured; skipping.",
                "latency_ms": (time.monotonic() - check_start)
                * 1000.0,
                "details": {},
            }

        try:
            get_stats = getattr(self._cache, "get_stats", None)
            stats: Dict[str, Any] = {}
            if callable(get_stats):
                stats = get_stats()

            entry_count = stats.get(
                "package_entries", 0
            ) + stats.get("repository_entries", 0)
            healthy = True
            message = (
                f"Cache accessible; {entry_count} entries stored."
            )

            return {
                "healthy": healthy,
                "message": message,
                "latency_ms": (time.monotonic() - check_start)
                * 1000.0,
                "details": {"cache_stats": stats},
            }
        except Exception as exc:
            logger.error("Cache health check failed: %s", exc)
            return {
                "healthy": False,
                "message": f"Cache check failed: {exc}",
                "latency_ms": (time.monotonic() - check_start)
                * 1000.0,
                "details": {"error": str(exc)},
            }

    def check_registry(self) -> Dict[str, Any]:
        """Check registry health.

        Returns:
            A dictionary with registry health status and details.
        """
        check_start = time.monotonic()
        if self._registry is None:
            return {
                "healthy": True,
                "message": "No registry configured; skipping.",
                "latency_ms": (time.monotonic() - check_start)
                * 1000.0,
                "details": {},
            }

        try:
            plugin_count = 0
            method = getattr(self._registry, "count", None)
            if callable(method):
                plugin_count = method()

            list_method = getattr(
                self._registry, "list_ids", None
            )
            plugin_ids: List[str] = []
            if callable(list_method):
                plugin_ids = list_method()

            return {
                "healthy": True,
                "message": (
                    f"Registry accessible; {plugin_count} "
                    f"plugins registered."
                ),
                "latency_ms": (time.monotonic() - check_start)
                * 1000.0,
                "details": {
                    "plugin_count": plugin_count,
                    "plugin_ids": plugin_ids[:20],
                },
            }
        except Exception as exc:
            logger.error(
                "Registry health check failed: %s", exc
            )
            return {
                "healthy": False,
                "message": f"Registry check failed: {exc}",
                "latency_ms": (time.monotonic() - check_start)
                * 1000.0,
                "details": {"error": str(exc)},
            }

    def is_healthy(self) -> bool:
        """Return True if the last health check was fully healthy.

        Returns:
            True if all checks passed, False otherwise.
        """
        if not self._last_results:
            return False
        return all(r.healthy for r in self._last_results)

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics from the last health check.

        Returns:
            Dictionary with last check details and results.
        """
        return {
            "last_check_time": self._last_check_time,
            "total_checks": len(self._last_results),
            "healthy_checks": sum(
                1 for r in self._last_results if r.healthy
            ),
            "unhealthy_checks": sum(
                1 for r in self._last_results if not r.healthy
            ),
            "results": [r.to_dict() for r in self._last_results],
            "repositories_configured": len(self._repositories),
            "cache_available": self._cache is not None,
            "registry_available": self._registry is not None,
        }