"""Intelligent service resolver with advanced routing pipeline.

Provides ``IntelligentServiceResolver`` which orchestrates the
full resolution pipeline: context-based version routing, canary
deployment, feature-flag filtering, health filtering, circuit
breaking, locality routing, and load balancing.

Pipeline: Context → Version Router → Canary Router → Feature Flag
         → Health Filter → Circuit Filter → Locality Router
         → Load Balancer
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from ..endpoint import ServiceEndpoint
from ..instance import ServiceInstance
from .cache import ResolverCache
from .canary import CanaryRouter
from .circuit_filter import CircuitFilter
from .context import ResolveContext
from .diagnostics import ResolverDiagnostics
from .feature_flag import FeatureFlagRouter
from .health_filter import HealthFilter
from .load_balancer import LoadBalancer
from .locality import LocalityRouter
from .metrics import ResolverMetrics
from .telemetry import ResolverTelemetry
from .version_router import VersionRouter

logger = logging.getLogger(__name__)


class IntelligentServiceResolver:
    """Intelligent service resolver with full routing pipeline.

    Integrates all resolver sub-components into a single
    pipeline for production-grade service discovery with
    support for versioning, canary deployments, feature flags,
    health filtering, circuit breaking, locality awareness,
    and pluggable load balancing.

    Usage::

        resolver = IntelligentServiceResolver(registry)
        instance = await resolver.resolve("payment-service", context)
        endpoint = await resolver.resolve_endpoint("payment-service")
    """

    def __init__(
        self,
        load_balancer: Optional[LoadBalancer] = None,
        cache_ttl: float = 5.0,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._lock = threading.RLock()
        self._load_balancer = load_balancer or LoadBalancer()
        self._version_router = VersionRouter()
        self._canary_router = CanaryRouter()
        self._feature_flag_router = FeatureFlagRouter()
        self._health_filter = HealthFilter()
        self._circuit_filter = CircuitFilter(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self._locality_router = LocalityRouter()
        self._cache = ResolverCache(ttl=cache_ttl)
        self._metrics = ResolverMetrics()
        self._diagnostics = ResolverDiagnostics()
        self._telemetry = ResolverTelemetry()
        self._resolve_count = 0
        self._failure_count = 0
        self._total_latency = 0.0

    async def resolve(
        self,
        service_name: str,
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        """Resolve a single service instance through the full pipeline.

        Args:
            service_name: The logical service name.
            context: Optional resolution context.

        Returns:
            The selected ``ServiceInstance`` or None if no
            healthy instances are available.
        """
        start_time = time.time()
        span_id = self._telemetry.start_span("resolve", service_name)

        try:
            candidates = await self._resolve_candidates(
                service_name, context
            )

            if not candidates:
                with self._lock:
                    self._failure_count += 1
                latency = time.time() - start_time
                self._metrics.record_resolve(
                    service_name,
                    context.strategy if context else "round_robin",
                    latency,
                    False,
                )
                self._telemetry.end_span(span_id, "error")
                self._diagnostics.record_resolution(
                    service_name,
                    context.strategy if context else "round_robin",
                    None,
                    latency,
                    {"error": "no_candidates"},
                )
                return None

            strategy = (
                context.strategy
                if context is not None
                else "round_robin"
            )
            selected = await self._load_balancer.select(
                candidates, strategy=strategy, context=context
            )

            if selected is None:
                with self._lock:
                    self._failure_count += 1
                latency = time.time() - start_time
                self._metrics.record_resolve(
                    service_name, strategy, latency, False
                )
                self._telemetry.end_span(span_id, "error")
                self._diagnostics.record_resolution(
                    service_name,
                    strategy,
                    None,
                    latency,
                    {"error": "no_selection"},
                )
                return None

            self._circuit_filter.record_success(selected.instance_id)

            latency = time.time() - start_time
            with self._lock:
                self._resolve_count += 1
                self._total_latency += latency

            self._metrics.record_resolve(
                service_name, strategy, latency, True
            )
            self._metrics.record_load_balance(strategy, True)
            self._metrics.record_locality_route(
                service_name,
                self._determine_locality(selected, context),
            )
            self._telemetry.end_span(span_id, "ok")
            self._telemetry.record_resolve(
                service_name, strategy, selected.instance_id, latency
            )
            self._diagnostics.record_resolution(
                service_name,
                strategy,
                selected.instance_id,
                latency,
                {"candidates": len(candidates)},
            )

            logger.debug(
                "Resolved '%s' to instance '%s' in %.4fs.",
                service_name,
                selected.instance_id,
                latency,
            )
            return selected

        except Exception as e:
            with self._lock:
                self._failure_count += 1
            latency = time.time() - start_time
            self._metrics.record_resolve(
                service_name,
                context.strategy if context else "round_robin",
                latency,
                False,
            )
            self._telemetry.end_span(span_id, "error")
            logger.error(
                "Failed to resolve service '%s': %s", service_name, e
            )
            raise

    async def resolve_many(
        self,
        service_name: str,
        count: int = 1,
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Resolve multiple service instances through the pipeline.

        Args:
            service_name: The logical service name.
            count: Number of instances to resolve.
            context: Optional resolution context.

        Returns:
            A list of selected ``ServiceInstance`` objects.
        """
        start_time = time.time()
        span_id = self._telemetry.start_span(
            "resolve_many", service_name
        )

        try:
            candidates = await self._resolve_candidates(
                service_name, context
            )

            if not candidates:
                latency = time.time() - start_time
                self._telemetry.end_span(span_id, "error")
                return []

            strategy = (
                context.strategy
                if context is not None
                else "round_robin"
            )
            selected = await self._load_balancer.select_many(
                candidates, count, strategy=strategy, context=context
            )

            for instance in selected:
                self._circuit_filter.record_success(instance.instance_id)

            latency = time.time() - start_time
            with self._lock:
                self._resolve_count += len(selected)
                self._total_latency += latency

            self._metrics.record_resolve(
                service_name, strategy, latency, len(selected) > 0
            )
            self._telemetry.end_span(span_id, "ok")
            self._diagnostics.record_resolution(
                service_name,
                strategy,
                f"multiple({len(selected)})",
                latency,
                {"candidates": len(candidates), "count": count},
            )

            return selected

        except Exception as e:
            latency = time.time() - start_time
            self._telemetry.end_span(span_id, "error")
            logger.error(
                "Failed to resolve many for '%s': %s", service_name, e
            )
            raise

    async def resolve_endpoint(
        self,
        service_name: str,
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceEndpoint]:
        """Resolve a service endpoint through the pipeline.

        Args:
            service_name: The logical service name.
            context: Optional resolution context.

        Returns:
            A ``ServiceEndpoint`` or None if unavailable.
        """
        instance = await self.resolve(service_name, context)
        if instance is None:
            return None
        return instance.to_endpoint()

    async def _resolve_candidates(
        self,
        service_name: str,
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Execute the full routing pipeline to get candidates.

        Pipeline stages:
        1. Cache lookup
        2. Version routing
        3. Canary routing
        4. Feature flag routing
        5. Health filtering
        6. Circuit filter
        7. Locality routing

        Args:
            service_name: The logical service name.
            context: Optional resolution context.

        Returns:
            Filtered list of candidate instances.
        """
        context_key = self._make_context_key(context)

        cached = self._cache.get(service_name, context_key)
        if cached is not None:
            self._metrics.record_route("cache_hit", 0.0)
            return cached

        self._metrics.record_route("cache_miss", 0.0)

        instances = await self._discover_instances(
            service_name, context
        )

        if not instances:
            return []

        instances = self._version_router.filter(instances, context)
        if not instances:
            self._diagnostics.record_filtering(
                "version", service_name, len(instances), "no_match"
            )
            return []

        instances = self._canary_router.filter(instances, context)
        if not instances:
            self._diagnostics.record_filtering(
                "canary", service_name, len(instances), "no_match"
            )
            return []

        instances = self._feature_flag_router.filter(
            instances, context
        )
        if not instances:
            self._diagnostics.record_filtering(
                "feature_flag", service_name, len(instances), "no_match"
            )
            return []

        before_health = len(instances)
        instances = self._health_filter.filter(instances, context)
        removed = before_health - len(instances)
        if removed > 0:
            self._diagnostics.record_filtering(
                "health",
                service_name,
                removed,
                "unhealthy_or_unavailable",
            )

        if not instances:
            return []

        before_circuit = len(instances)
        instances = self._circuit_filter.filter(instances, context)
        removed = before_circuit - len(instances)
        if removed > 0:
            self._diagnostics.record_filtering(
                "circuit",
                service_name,
                removed,
                "circuit_open",
            )

        if not instances:
            return []

        instances = self._locality_router.filter(instances, context)

        self._cache.set(service_name, context_key, instances)
        return instances

    async def _discover_instances(
        self,
        service_name: str,
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Discover instances for a service.

        This is a placeholder that can be overridden or
        configured with a discovery backend. Returns an
        empty list by default.

        Args:
            service_name: The logical service name.
            context: Optional resolution context.

        Returns:
            A list of ``ServiceInstance`` objects.
        """
        return []

    @staticmethod
    def _make_context_key(
        context: Optional[ResolveContext],
    ) -> str:
        if context is None:
            return "default"
        return context.to_dict().__repr__()

    @staticmethod
    def _determine_locality(
        instance: ServiceInstance,
        context: Optional[ResolveContext],
    ) -> str:
        if not isinstance(instance.metadata, dict):
            return "unknown"
        instance_region = str(
            instance.metadata.get("region", "")
        )
        if context is not None and context.region:
            if instance_region == context.region:
                return "region"
        instance_zone = str(
            instance.metadata.get("zone", "")
        )
        if context is not None and context.zone:
            if instance_zone == context.zone:
                return "zone"
        if instance_region:
            return "region"
        return "fallback"

    def set_load_balancer(self, load_balancer: LoadBalancer) -> None:
        """Set the load balancer.

        Args:
            load_balancer: The ``LoadBalancer`` instance to use.
        """
        if load_balancer is None:
            raise ValueError("LoadBalancer cannot be None.")
        if not isinstance(load_balancer, LoadBalancer):
            raise TypeError(
                "load_balancer must be an instance of LoadBalancer."
            )
        with self._lock:
            self._load_balancer = load_balancer
        logger.debug(
            "Load balancer set to: %s",
            type(load_balancer).__name__,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Return comprehensive resolver statistics.

        Aggregates statistics from all sub-components.

        Returns:
            A dictionary with resolution counts, latencies,
            and sub-component statistics.
        """
        with self._lock:
            avg_latency = (
                self._total_latency / self._resolve_count
                if self._resolve_count
                else 0.0
            )
            return {
                "resolver": "IntelligentServiceResolver",
                "resolve_count": self._resolve_count,
                "failure_count": self._failure_count,
                "failure_rate": (
                    self._failure_count
                    / (self._resolve_count + self._failure_count)
                    if (self._resolve_count + self._failure_count)
                    else 0.0
                ),
                "avg_latency": avg_latency,
                "total_latency": self._total_latency,
                "load_balancer": self._load_balancer.get_stats(),
                "version_router": self._version_router.get_stats(),
                "canary_router": self._canary_router.get_stats(),
                "feature_flag_router": self._feature_flag_router.get_stats(),
                "health_filter": self._health_filter.get_stats(),
                "circuit_filter": self._circuit_filter.get_stats(),
                "locality_router": self._locality_router.get_stats(),
                "cache": self._cache.get_stats(),
                "metrics": self._metrics.get_stats(),
                "diagnostics": self._diagnostics.get_stats(),
                "telemetry": self._telemetry.get_stats(),
            }

    @property
    def version_router(self) -> VersionRouter:
        """Access the version router."""
        return self._version_router

    @property
    def canary_router(self) -> CanaryRouter:
        """Access the canary router."""
        return self._canary_router

    @property
    def feature_flag_router(self) -> FeatureFlagRouter:
        """Access the feature flag router."""
        return self._feature_flag_router

    @property
    def health_filter(self) -> HealthFilter:
        """Access the health filter."""
        return self._health_filter

    @property
    def circuit_filter(self) -> CircuitFilter:
        """Access the circuit filter."""
        return self._circuit_filter

    @property
    def locality_router(self) -> LocalityRouter:
        """Access the locality router."""
        return self._locality_router

    @property
    def cache(self) -> ResolverCache:
        """Access the resolver cache."""
        return self._cache

    @property
    def metrics(self) -> ResolverMetrics:
        """Access the resolver metrics."""
        return self._metrics

    @property
    def diagnostics(self) -> ResolverDiagnostics:
        """Access the resolver diagnostics."""
        return self._diagnostics

    @property
    def telemetry(self) -> ResolverTelemetry:
        """Access the resolver telemetry."""
        return self._telemetry

    @property
    def load_balancer(self) -> LoadBalancer:
        """Access the load balancer."""
        return self._load_balancer

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"IntelligentServiceResolver(resolves={self._resolve_count}, "
                f"failures={self._failure_count})"
            )