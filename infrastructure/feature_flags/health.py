"""
Feature flag platform health check.

Provides health status checking for all
feature flag platform components including
registry, cache, storage, and overall
platform readiness.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .constants import FlagStatus
from .models import FeatureFlag

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult:
    """Result of a component health check."""

    def __init__(
        self,
        name: str,
        healthy: bool = True,
        message: str = "",
        latency_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.healthy = healthy
        self.message = message
        self.latency_ms = latency_ms
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "status": "healthy" if self.healthy else "unhealthy",
            "message": self.message,
            "latency_ms": self.latency_ms,
            "details": self.details,
        }


class FeatureFlagHealth:
    """
    Health check aggregator for the feature flag platform.

    Performs comprehensive health checks on all
    platform components and provides an overall
    platform readiness status for load balancers
    and orchestrators.

    Components checked:
        - Feature flags registry
        - Feature evaluator
        - Local cache
        - Storage backend
        - Audit manager
        - Metrics collector

    Usage:
        health = FeatureFlagHealth(manager)
        status = await health.check()
        is_ready = health.is_ready()
    """

    def __init__(
        self,
        manager: Any = None,
        registry: Any = None,
        evaluator: Any = None,
        cache: Any = None,
        storage: Any = None,
        audit: Any = None,
        metrics: Any = None,
        canary: Any = None,
        experiment: Any = None,
        runtime: Any = None,
    ) -> None:
        """
        Initialize health checker.

        Args:
            manager: FeatureFlagManager instance.
            registry: FeatureRegistry instance.
            evaluator: FeatureEvaluator instance.
            cache: FeatureFlagCache instance.
            storage: FeatureStorage instance.
            audit: AuditManager instance.
            metrics: FeatureFlagMetrics instance.
            canary: CanaryManager instance.
            experiment: ExperimentManager instance.
            runtime: RuntimeFeatureService instance.
        """
        self._manager = manager
        self._registry = registry
        self._evaluator = evaluator
        self._cache = cache
        self._storage = storage
        self._audit = audit
        self._metrics = metrics
        self._canary = canary
        self._experiment = experiment
        self._runtime = runtime
        self._last_check: Optional[Dict[str, Any]] = None
        self._check_interval_ms = 5000
        self._last_check_time: float = 0

    async def check(self) -> Dict[str, Any]:
        """
        Run comprehensive health checks on all components.

        Returns:
            Health status dictionary with per-component
            results and overall status.
        """
        results: List[HealthCheckResult] = []

        # Check feature flags / registry
        results.append(await self._check_registry())

        # Check evaluator
        results.append(await self._check_evaluator())

        # Check cache
        results.append(await self._check_cache())

        # Check storage
        results.append(await self._check_storage())

        # Check audit
        results.append(await self._check_audit())

        # Check metrics
        results.append(await self._check_metrics())

        # Check canary
        results.append(await self._check_canary())

        # Check experiment
        results.append(await self._check_experiment())

        # Check runtime
        results.append(await self._check_runtime())

        # Determine overall status
        healthy_count = sum(1 for r in results if r.healthy)
        total_count = len(results)

        overall_healthy = all(r.healthy for r in results)
        degraded = (
            not overall_healthy
            and healthy_count > 0
        )

        status = {
            "feature_flags": {
                "healthy": overall_healthy,
                "status": (
                    HealthStatus.HEALTHY
                    if overall_healthy
                    else HealthStatus.DEGRADED if degraded
                    else HealthStatus.UNHEALTHY
                ),
                "components": [r.to_dict() for r in results],
                "total_components": total_count,
                "healthy_components": healthy_count,
            },
            "registry": results[0].to_dict(),
            "evaluator": results[1].to_dict(),
            "cache": results[2].to_dict(),
            "storage": results[3].to_dict(),
            "audit": results[4].to_dict(),
            "metrics": results[5].to_dict(),
            "canary": results[6].to_dict(),
            "experiment": results[7].to_dict(),
            "runtime": results[8].to_dict(),
        }

        self._last_check = status
        self._last_check_time = time.monotonic()

        return status

    async def _check_registry(self) -> HealthCheckResult:
        """Check feature registry health."""
        start = time.perf_counter()
        try:
            registry = self._registry
            if registry is None and self._manager:
                registry = self._manager.get_registry()

            if registry is None:
                return HealthCheckResult(
                    name="registry",
                    healthy=False,
                    message="Registry not initialized",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            count = registry.count()
            by_status = registry.count_by_status()

            healthy = True
            message = f"{count} flags registered"

            return HealthCheckResult(
                name="registry",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details={
                    "total_flags": count,
                    "active_flags": by_status.get("active", 0),
                    "inactive_flags": by_status.get("inactive", 0),
                    "by_status": by_status,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name="registry",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_evaluator(self) -> HealthCheckResult:
        """Check feature evaluator health."""
        start = time.perf_counter()
        try:
            evaluator = self._evaluator
            if evaluator is None and self._manager:
                evaluator = self._manager.get_evaluator()

            if evaluator is None:
                return HealthCheckResult(
                    name="evaluator",
                    healthy=False,
                    message="Evaluator not initialized",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            stats = evaluator.get_stats()
            error_rate = stats.get("error_rate", 0)

            healthy = error_rate < 0.1  # Less than 10% error rate
            message = (
                f"error_rate={error_rate:.2%}"
                if not healthy
                else "operational"
            )

            return HealthCheckResult(
                name="evaluator",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details=stats,
            )
        except Exception as e:
            return HealthCheckResult(
                name="evaluator",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_cache(self) -> HealthCheckResult:
        """Check cache health."""
        start = time.perf_counter()
        try:
            cache = self._cache
            if cache is None and self._manager:
                cache = self._manager.get_cache()

            if cache is None:
                return HealthCheckResult(
                    name="cache",
                    healthy=True,
                    message="Cache not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            stats = cache.get_stats()
            healthy = stats.get("enabled", False)
            message = (
                f"hit_ratio={stats.get('hit_ratio', 0):.2%}, "
                f"entries={stats.get('entries', 0)}"
            )

            return HealthCheckResult(
                name="cache",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details=stats,
            )
        except Exception as e:
            return HealthCheckResult(
                name="cache",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_storage(self) -> HealthCheckResult:
        """Check storage backend health."""
        start = time.perf_counter()
        try:
            storage = self._storage
            if storage is None and self._manager:
                storage = self._manager._storage

            if storage is None:
                return HealthCheckResult(
                    name="storage",
                    healthy=False,
                    message="Storage not initialized",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            health = await storage.health_check()
            healthy = health.get("healthy", False)

            return HealthCheckResult(
                name="storage",
                healthy=healthy,
                message=str(health),
                latency_ms=(time.perf_counter() - start) * 1000,
                details=health,
            )
        except Exception as e:
            return HealthCheckResult(
                name="storage",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_audit(self) -> HealthCheckResult:
        """Check audit manager health."""
        start = time.perf_counter()
        try:
            if self._audit is None:
                return HealthCheckResult(
                    name="audit",
                    healthy=True,
                    message="Audit not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            stats = self._audit.get_stats()
            healthy = True
            message = f"{stats.get('total_entries', 0)} entries"

            return HealthCheckResult(
                name="audit",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details=stats,
            )
        except Exception as e:
            return HealthCheckResult(
                name="audit",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_metrics(self) -> HealthCheckResult:
        """Check metrics collector health."""
        start = time.perf_counter()
        try:
            if self._metrics is None:
                return HealthCheckResult(
                    name="metrics",
                    healthy=True,
                    message="Metrics not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            snapshot = self._metrics.snapshot()
            healthy = True
            message = "metrics operational"

            return HealthCheckResult(
                name="metrics",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details={
                    "eval_total": sum(snapshot.get("eval_total", {}).values()),
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name="metrics",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_canary(self) -> HealthCheckResult:
        """Check canary engine health."""
        start = time.perf_counter()
        try:
            if self._canary is None:
                return HealthCheckResult(
                    name="canary",
                    healthy=True,
                    message="Canary not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            stats = self._canary.get_stats()
            active = stats.get("active_deployments", 0)
            healthy = True
            message = f"{active} active deployments"

            return HealthCheckResult(
                name="canary",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details=stats,
            )
        except Exception as e:
            return HealthCheckResult(
                name="canary",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_experiment(self) -> HealthCheckResult:
        """Check experiment engine health."""
        start = time.perf_counter()
        try:
            if self._experiment is None:
                return HealthCheckResult(
                    name="experiment",
                    healthy=True,
                    message="Experiment not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            stats = self._experiment.get_stats()
            total = stats.get("total_experiments", 0)
            healthy = True
            message = f"{total} experiments"

            return HealthCheckResult(
                name="experiment",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details=stats,
            )
        except Exception as e:
            return HealthCheckResult(
                name="experiment",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_runtime(self) -> HealthCheckResult:
        """Check runtime service health."""
        start = time.perf_counter()
        try:
            if self._runtime is None:
                return HealthCheckResult(
                    name="runtime",
                    healthy=True,
                    message="Runtime not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

            stats = self._runtime.get_stats()
            is_running = stats.get("running", False)
            healthy = is_running
            message = (
                "operational"
                if is_running
                else "not running"
            )

            return HealthCheckResult(
                name="runtime",
                healthy=healthy,
                message=message,
                latency_ms=(time.perf_counter() - start) * 1000,
                details=stats,
            )
        except Exception as e:
            return HealthCheckResult(
                name="runtime",
                healthy=False,
                message=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    def is_ready(self) -> bool:
        """
        Check if the platform is ready to serve traffic.

        Returns:
            True if all critical components are healthy.
        """
        if self._last_check is None:
            return False

        ff = self._last_check.get("feature_flags", {})
        return ff.get("healthy", False)

    def get_cached_status(self) -> Optional[Dict[str, Any]]:
        """Get the last cached health check result."""
        return self._last_check

    def is_cache_valid(self) -> bool:
        """Check if the cached status is still valid."""
        if self._last_check_time == 0:
            return False
        elapsed = time.monotonic() - self._last_check_time
        return elapsed < self._check_interval_ms / 1000.0

    def set_check_interval(
        self,
        interval_ms: int,
    ) -> None:
        """
        Set the health check cache interval.

        Args:
            interval_ms: Cache validity duration in ms.
        """
        self._check_interval_ms = max(100, interval_ms)