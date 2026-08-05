"""Traffic Manager for ICYQuant Service Mesh.

Provides ``TrafficManager`` as the unified entry point for traffic
management, coordinating routing, policies, load balancing, and
traffic governance across the service mesh.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .canary import CanaryRelease
from .circuit_breaker import CircuitBreakerConfig, TrafficCircuitBreaker
from .connection_pool import ConnectionPool
from .destination_rule import DestinationRuleManager
from .diagnostics import TrafficDiagnostics
from .hedging import HedgeManager
from .load_balancer import LoadBalancer, LoadBalancerStrategy
from .metrics import TrafficMetrics
from .mirror import TrafficMirror
from .outlier_detection import OutlierDetector
from .policies import PolicyManager
from .rate_limiter import RateLimiter
from .retry import RetryManager
from .route import RouteDestination, RouteTable, TrafficRoute
from .route_matcher import RouteMatcher
from .route_rewriter import RouteRewriter
from .timeout import TimeoutManager
from .traffic_split import TrafficSplit
from .virtual_service import VirtualService

logger = logging.getLogger(__name__)


class TrafficManager:
    """Unified traffic management entry point."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._started = False

        # Core components
        self._route_table = RouteTable()
        self._route_matcher = RouteMatcher(self._route_table)
        self._route_rewriter = RouteRewriter()
        self._destination_rules = DestinationRuleManager()
        self._policies = PolicyManager()

        # Traffic strategies
        self._traffic_split = TrafficSplit()
        self._load_balancer = LoadBalancer()

        # Deployment strategies
        self._canary = CanaryRelease()
        self._mirror = TrafficMirror()

        # Resilience
        self._retry_manager = RetryManager()
        self._hedge_manager = HedgeManager()
        self._timeout_manager = TimeoutManager()
        self._circuit_breakers: Dict[str, TrafficCircuitBreaker] = {}
        self._outlier_detector = OutlierDetector()
        self._rate_limiter = RateLimiter()
        self._connection_pool = ConnectionPool()

        # Observability
        self._metrics = TrafficMetrics()
        self._diagnostics = TrafficDiagnostics()

        # Virtual services
        self._virtual_services: Dict[str, VirtualService] = {}

        # Request tracking
        self._request_count = 0
        self._active_requests = 0

    async def route(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        host: str = "",
    ) -> Dict[str, Any]:
        """Route a request through the traffic management pipeline."""
        with self._lock:
            self._request_count += 1
            self._active_requests += 1

        headers = headers or {}
        start = time.monotonic()
        self._metrics.increment_requests({"method": method})

        # Step 1: Rate limit check
        if not self._rate_limiter.try_acquire(
            key=host or path
        ):
            self._metrics.increment_rate_limit(
                {"host": host, "path": path}
            )
            self._active_requests -= 1
            return {
                "status": 429,
                "error": "rate_limit_exceeded",
                "route_id": "",
                "target": "",
            }

        # Step 2: Route matching
        route = self._route_matcher.match(
            method, path, headers, host=host
        )
        if not route:
            self._active_requests -= 1
            return {
                "status": 404,
                "error": "no_route_found",
                "route_id": "",
                "target": "",
            }

        self._diagnostics.record_decision(
            route.route_id, True, "", "matched"
        )

        # Step 3: Circuit breaker check
        circuit = self._circuit_breakers.get(route.route_id)
        if circuit and not circuit.allow_request():
            self._metrics.increment_circuit_open(
                {"route": route.route_id}
            )
            self._active_requests -= 1
            return {
                "status": 503,
                "error": "circuit_open",
                "route_id": route.route_id,
                "target": "",
            }

        # Step 4: Destination selection with traffic split
        destination = self._select_destination(route)
        if not destination:
            self._active_requests -= 1
            return {
                "status": 502,
                "error": "no_destination",
                "route_id": route.route_id,
                "target": "",
            }

        target_host = destination.get("host", "")
        target_port = destination.get("port", 80)

        # Step 5: Timeout management
        timeouts = self._timeout_manager.get_timeouts(
            target_host
        )

        # Step 6: Connection acquisition
        conn = self._connection_pool.acquire(
            target_host, target_port
        )

        # Step 7: Rewrite
        rewrite_result = self._route_rewriter.rewrite_request(
            path, headers, route.rewrite
        )

        duration = time.monotonic() - start

        # Step 8: Success recording
        if circuit:
            circuit.record_success()
        self._timeout_manager.record_latency(
            target_host, duration
        )
        self._outlier_detector.record_request(
            target_host, True, duration * 1000
        )
        self._connection_pool.release(conn, error=False)

        # Step 9: Mirror (async, not blocking)
        if route.mirror_policy_id:
            asyncio.create_task(
                self._mirror.mirror_request(
                    method,
                    path,
                    headers,
                    policy_ids=[route.mirror_policy_id],
                )
            )

        # Step 10: Metrics
        self._metrics.record_latency(
            duration,
            {"route": route.route_id, "target": target_host},
        )

        with self._lock:
            self._active_requests -= 1

        return {
            "status": 200,
            "route_id": route.route_id,
            "target": target_host,
            "duration_s": duration,
            "rewritten": rewrite_result.get("rewritten", False),
            "conn_id": conn.conn_id,
            "timeouts": timeouts,
        }

    def _select_destination(
        self, route: TrafficRoute
    ) -> Optional[Dict[str, Any]]:
        """Select a destination using traffic split."""
        destinations = [
            d.to_dict() if hasattr(d, "to_dict") else d
            for d in route.destinations
        ]
        if not destinations:
            return None
        return self._traffic_split.select_destination(
            destinations,
            strategy="weighted",
        )

    def update_policy(
        self, policy_id: str, config: Dict[str, Any]
    ) -> None:
        """Update a traffic policy."""
        from .policies import TrafficPolicy
        policy = TrafficPolicy(
            policy_id=policy_id,
            **config,
        )
        self._policies.register_traffic_policy(policy)

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reload traffic management configuration."""
        with self._lock:
            self._route_table.clear()
            self._destination_rules.clear()
            self._route_matcher.set_route_table(
                self._route_table
            )

        if config:
            routes = config.get("routes", [])
            for r in routes:
                route = TrafficRoute(
                    route_id=r["route_id"],
                    name=r.get("name", r["route_id"]),
                    path=r.get("path", "/"),
                )
                for d in r.get("destinations", []):
                    route.add_destination(
                        d.get("host", ""),
                        d.get("port", 80),
                        d.get("weight", 1.0),
                    )
                self._route_table.add_route(route)

        return {"success": True}

    def register_route(self, route: TrafficRoute) -> None:
        self._route_table.add_route(route)

    def unregister_route(self, route_id: str) -> bool:
        return self._route_table.remove_route(route_id)

    def register_virtual_service(
        self, vs: VirtualService
    ) -> None:
        with self._lock:
            self._virtual_services[vs.name] = vs
            for route in vs.get_routes():
                self._route_table.add_route(route)

    def register_circuit_breaker(
        self,
        target: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> TrafficCircuitBreaker:
        with self._lock:
            cb = TrafficCircuitBreaker(config)
            self._circuit_breakers[target] = cb
            return cb

    def set_load_balancer_strategy(
        self, strategy: str
    ) -> None:
        self._load_balancer.set_strategy(strategy)

    def get_virtual_service(
        self, name: str
    ) -> Optional[VirtualService]:
        with self._lock:
            return self._virtual_services.get(name)

    def list_routes(self) -> List[Dict[str, Any]]:
        return self._route_table.list_routes_dict()

    def list_virtual_services(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                vs.to_dict()
                for vs in self._virtual_services.values()
            ]

    def start(self) -> None:
        with self._lock:
            self._started = True

    def stop(self) -> None:
        with self._lock:
            self._started = False
            self._connection_pool.cleanup()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._started

    @property
    def route_matcher(self) -> RouteMatcher:
        return self._route_matcher

    @property
    def metrics(self) -> TrafficMetrics:
        return self._metrics

    @property
    def circuit_breakers(self) -> Dict[str, TrafficCircuitBreaker]:
        with self._lock:
            return dict(self._circuit_breakers)

    @property
    def diagnostics(self) -> TrafficDiagnostics:
        return self._diagnostics

    @property
    def canary(self) -> CanaryRelease:
        return self._canary

    @property
    def outlier_detector(self) -> OutlierDetector:
        return self._outlier_detector

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started": self._started,
                "request_count": self._request_count,
                "active_requests": self._active_requests,
                "route_count": len(
                    self._route_table.list_routes()
                ),
                "virtual_service_count": len(
                    self._virtual_services
                ),
                "circuit_breaker_count": len(
                    self._circuit_breakers
                ),
                "metrics": self._metrics.get_summary(),
                "policies": self._policies.get_stats(),
                "load_balancer": (
                    self._load_balancer.get_stats()
                ),
                "connection_pool": (
                    self._connection_pool.get_stats()
                ),
                "rate_limiter": self._rate_limiter.get_stats(),
                "diagnostics": self._diagnostics.get_snapshot(),
            }