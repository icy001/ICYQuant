"""
ICYQuant Cloud Native Runtime - Service Mesh Manager

Manages service mesh operations with Istio, providing:
- Traffic routing (weighted, canary, blue/green)
- mTLS configuration
- Retry and circuit breaker policies
- Rate limiting
- Shadow traffic testing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class TrafficDirection(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    SHADOW = "shadow"


class LoadBalancingStrategy(str, Enum):
    ROUND_ROBIN = "round-robin"
    LEAST_CONNECTIONS = "least-connections"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent-hash"


@dataclass
class VirtualRoute:
    name: str
    host: str
    port: int
    path: str = "/"
    version: str = "stable"
    weight: int = 100
    timeout_seconds: int = 30
    retries: int = 3
    retry_on: List[str] = field(default_factory=lambda: ["5xx", "reset", "connect-failure"])
    mirrors_to: Optional[str] = None
    mirror_percentage: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "version": self.version,
            "weight": self.weight,
            "timeoutSeconds": self.timeout_seconds,
            "retries": self.retries,
            "retryOn": self.retry_on,
            "mirrorsTo": self.mirrors_to,
            "mirrorPercentage": self.mirror_percentage,
        }


@dataclass
class MTLSConfig:
    mode: str = "strict"  # strict, permissive, disable
    cert_provider: str = "istio"
    rotation_hours: int = 24

    def to_dict(self) -> Dict:
        return {
            "mode": self.mode,
            "certProvider": self.cert_provider,
            "rotationHours": self.rotation_hours,
        }


@dataclass
class RateLimitConfig:
    requests_per_second: int = 100
    burst_size: int = 200
    throttle_action: str = "deny"

    def to_dict(self) -> Dict:
        return {
            "requestsPerSecond": self.requests_per_second,
            "burstSize": self.burst_size,
            "throttleAction": self.throttle_action,
        }


@dataclass
class CircuitBreakerConfig:
    consecutive_errors: int = 5
    interval_seconds: int = 30
    base_ejection_seconds: int = 30
    max_ejection_percent: int = 50

    def to_dict(self) -> Dict:
        return {
            "consecutiveErrors": self.consecutive_errors,
            "intervalSeconds": self.interval_seconds,
            "baseEjectionSeconds": self.base_ejection_seconds,
            "maxEjectionPercent": self.max_ejection_percent,
        }


@dataclass
class ServiceMeshPolicy:
    name: str
    service: str
    routes: List[VirtualRoute] = field(default_factory=list)
    mtls: MTLSConfig = field(default_factory=MTLSConfig)
    rate_limit: Optional[RateLimitConfig] = None
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    load_balancing: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "service": self.service,
            "routes": [r.to_dict() for r in self.routes],
            "mtls": self.mtls.to_dict(),
            "rateLimit": self.rate_limit.to_dict() if self.rate_limit else None,
            "circuitBreaker": self.circuit_breaker.to_dict(),
            "loadBalancing": self.load_balancing.value,
        }


class ServiceMeshManager:
    """
    Service mesh manager for ICYQuant platform.

    Manages:
    - Virtual services and routes
    - Destination rules
    - Peer authentication (mTLS)
    - Authorization policies
    - Traffic splitting (canary/blue-green)
    - Resilience patterns
    """

    def __init__(self):
        self._policies: Dict[str, ServiceMeshPolicy] = {}
        self._service_routes: Dict[str, List[VirtualRoute]] = {}
        self._policy_history: List[Dict] = []

    def create_policy(
        self,
        service: str,
        routes: List[VirtualRoute],
        mtls: Optional[MTLSConfig] = None,
        rate_limit: Optional[RateLimitConfig] = None,
        circuit_breaker: Optional[CircuitBreakerConfig] = None,
    ) -> ServiceMeshPolicy:
        policy_id = str(uuid.uuid4())[:12]
        policy = ServiceMeshPolicy(
            name=f"{service}-policy",
            service=service,
            routes=routes,
            mtls=mtls or MTLSConfig(),
            rate_limit=rate_limit,
            circuit_breaker=circuit_breaker or CircuitBreakerConfig(),
        )
        self._policies[service] = policy
        self._service_routes[service] = routes
        self._record_policy_change("create", policy)
        return policy

    def update_routes(
        self,
        service: str,
        routes: List[VirtualRoute],
    ) -> Optional[ServiceMeshPolicy]:
        policy = self._policies.get(service)
        if not policy:
            return None
        old_weights = {r.name: r.weight for r in policy.routes}
        policy.routes = routes
        policy.updated_at = datetime.now()
        self._service_routes[service] = routes
        self._record_policy_change("update", policy, old_weights)
        return policy

    def set_canary_weight(
        self,
        service: str,
        stable_weight: int,
        canary_weight: int,
    ) -> Optional[ServiceMeshPolicy]:
        policy = self._policies.get(service)
        if not policy:
            return None
        for route in policy.routes:
            if route.version == "stable":
                route.weight = stable_weight
            elif route.version == "canary":
                route.weight = canary_weight
        policy.updated_at = datetime.now()
        self._record_policy_change("canary", policy, {
            "stable": stable_weight,
            "canary": canary_weight,
        })
        return policy

    def promote_canary(
        self,
        service: str,
    ) -> Optional[ServiceMeshPolicy]:
        policy = self._policies.get(service)
        if not policy:
            return None
        for route in policy.routes:
            if route.version == "canary":
                route.version = "stable"
                route.weight = 100
            elif route.version == "stable":
                route.weight = 0
        policy.updated_at = datetime.now()
        self._record_policy_change("promote", policy)
        return policy

    def configure_shadow_traffic(
        self,
        service: str,
        shadow_service: str,
        percentage: float = 5.0,
    ) -> Optional[ServiceMeshPolicy]:
        policy = self._policies.get(service)
        if not policy:
            return None
        for route in policy.routes:
            route.mirrors_to = shadow_service
            route.mirror_percentage = percentage
        policy.updated_at = datetime.now()
        self._record_policy_change("shadow", policy)
        return policy

    def set_rate_limit(
        self,
        service: str,
        rps: int,
        burst: int = None,
    ) -> Optional[ServiceMeshPolicy]:
        policy = self._policies.get(service)
        if not policy:
            return None
        policy.rate_limit = RateLimitConfig(
            requests_per_second=rps,
            burst_size=burst or rps * 2,
        )
        policy.updated_at = datetime.now()
        self._record_policy_change("rate_limit", policy)
        return policy

    def get_policy(self, service: str) -> Optional[ServiceMeshPolicy]:
        return self._policies.get(service)

    def get_routes(self, service: str) -> List[VirtualRoute]:
        return self._service_routes.get(service, [])

    def list_services(self) -> List[str]:
        return list(self._policies.keys())

    def get_status(self) -> Dict:
        return {
            "services": {
                name: {
                    "routes": [r.to_dict() for r in p.routes],
                    "mtls": p.mtls.to_dict(),
                    "rateLimit": p.rate_limit.to_dict() if p.rate_limit else None,
                }
                for name, p in self._policies.items()
            },
            "policyCount": len(self._policies),
            "history": self._policy_history[-20:],
        }

    def _record_policy_change(
        self,
        action: str,
        policy: ServiceMeshPolicy,
        details: Optional[Dict] = None,
    ):
        self._policy_history.append({
            "action": action,
            "service": policy.service,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        })