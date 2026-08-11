"""
ICYQuant Traffic Router — Intelligent request routing across model versions.

Routes inference requests to the appropriate model version based on:
  - Production vs canary traffic split
  - Shadow mirroring (production + shadow in parallel)
  - Version-pinned requests (research/backtest)
  - A/B test group assignment

This is the central routing layer that enables safe deployment strategies.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .inference_engine import InferenceEngine
    from .deployment_manager import DeploymentManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class RouteTarget(str, Enum):
    """Routing destinations."""
    PRODUCTION = "production"
    CANARY = "canary"
    SHADOW = "shadow"
    PINNED = "pinned"


@dataclass
class RoutingDecision:
    """Result of traffic routing decision."""
    model_id: str
    target: RouteTarget
    version: str
    shadow_version: Optional[str] = None
    reason: str = ""
    traffic_percent: float = 100.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "target": self.target.value,
            "version": self.version,
            "shadow_version": self.shadow_version,
            "reason": self.reason,
            "traffic_percent": self.traffic_percent,
            "timestamp": self.timestamp,
        }


@dataclass
class RouterConfig:
    """Traffic router configuration."""
    enable_canary: bool = True
    enable_shadow: bool = True
    consistent_hashing: bool = False  # Use hashing for deterministic routing
    hash_ring_size: int = 1000
    traffic_log_sample_rate: float = 0.01  # Log 1% of routing decisions


# ---------------------------------------------------------------------------
# Traffic Router
# ---------------------------------------------------------------------------

class TrafficRouter:
    """Central request routing engine.

    Key features:
      - Canary traffic splitting (percentage-based)
      - Shadow mirroring (parallel to production)
      - Version pinning support
      - Consistent hashing for deterministic routing
      - A/B test group assignment

    Usage::

        router = TrafficRouter(engine, deployment_manager)
        await router.initialize()

        decision = await router.route("nvda_model")
        if decision.target == RouteTarget.CANARY:
            result = await serve_with_canary(features, decision.version)
    """

    def __init__(
        self,
        engine: "InferenceEngine",
        deployment_manager: "DeploymentManager",
        config: Optional[RouterConfig] = None,
    ):
        self.engine = engine
        self.deployment_manager = deployment_manager
        self.config = config or RouterConfig()
        self._initialized = False

        # Routing statistics
        self._route_counts: Dict[str, int] = {
            RouteTarget.PRODUCTION.value: 0,
            RouteTarget.CANARY.value: 0,
            RouteTarget.SHADOW.value: 0,
            RouteTarget.PINNED.value: 0,
        }

        # A/B test group assignments: request_hash → group
        self._ab_groups: Dict[str, str] = {}

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("TrafficRouter initialized")

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def route(
        self,
        model_id: str,
        *,
        pinned_version: Optional[str] = None,
        request_hash: Optional[str] = None,
        force_target: Optional[RouteTarget] = None,
    ) -> RoutingDecision:
        """Determine which model version to route a request to.

        Priority:
          1. force_target — explicit override
          2. pinned_version — user-specified version
          3. Canary traffic split
          4. Production (default)

        Args:
            model_id: Model identifier.
            pinned_version: If set, route to this exact version.
            request_hash: Hash for deterministic routing.
            force_target: Override routing decision.

        Returns:
            RoutingDecision with target version.
        """
        # 1. Force target
        if force_target:
            return await self._route_to_target(model_id, force_target)

        # 2. Pinned version
        if pinned_version:
            self._route_counts[RouteTarget.PINNED.value] += 1
            return RoutingDecision(
                model_id=model_id,
                target=RouteTarget.PINNED,
                version=pinned_version,
                reason="version_pinned",
            )

        # 3. Check for canary
        if self.config.enable_canary:
            canary_version = self._get_canary_version(model_id)
            if canary_version:
                traffic_pct = self._get_canary_traffic(model_id)
                should_route = self._should_route_to_canary(
                    model_id, traffic_pct, request_hash
                )
                if should_route:
                    self._route_counts[RouteTarget.CANARY.value] += 1

                    # Check if shadow is also active
                    shadow_version = None
                    if self.config.enable_shadow:
                        shadow_version = self._get_shadow_version(model_id)

                    return RoutingDecision(
                        model_id=model_id,
                        target=RouteTarget.CANARY,
                        version=canary_version,
                        shadow_version=shadow_version,
                        reason="canary_split",
                        traffic_percent=traffic_pct,
                    )

        # 4. Production
        prod_version = self._get_production_version(model_id)

        # Check shadow
        shadow_version = None
        if self.config.enable_shadow:
            shadow_version = self._get_shadow_version(model_id)

        self._route_counts[RouteTarget.PRODUCTION.value] += 1

        if shadow_version:
            self._route_counts[RouteTarget.SHADOW.value] += 1

        return RoutingDecision(
            model_id=model_id,
            target=RouteTarget.PRODUCTION if not shadow_version else RouteTarget.PRODUCTION,
            version=prod_version,
            shadow_version=shadow_version,
            reason="production_default",
            traffic_percent=100.0,
        )

    async def route_batch(
        self,
        model_id: str,
        count: int,
        *,
        pinned_version: Optional[str] = None,
    ) -> List[RoutingDecision]:
        """Route a batch of requests — preserves canary split proportionally."""
        decisions = []
        canary_version = self._get_canary_version(model_id)
        canary_pct = self._get_canary_traffic(model_id)
        canary_count = int(count * canary_pct / 100.0) if canary_version else 0

        for i in range(count):
            if i < canary_count:
                decision = await self.route(
                    model_id,
                    force_target=RouteTarget.CANARY,
                )
            else:
                decision = await self.route(
                    model_id,
                    pinned_version=pinned_version,
                )
            decisions.append(decision)

        return decisions

    # ------------------------------------------------------------------
    # Shadow mirroring
    # ------------------------------------------------------------------

    async def mirror_to_shadow(
        self,
        model_id: str,
        features: Dict[str, Any],
    ) -> Optional[RoutingDecision]:
        """Mirror a prediction request to shadow deployment.

        This fires in parallel with production inference and its
        result is only logged — never affects trading decisions.

        Args:
            model_id: Model identifier.
            features: Feature dictionary.

        Returns:
            Shadow routing decision if shadow is active, else None.
        """
        shadow_version = self._get_shadow_version(model_id)
        if shadow_version is None:
            return None

        return RoutingDecision(
            model_id=model_id,
            target=RouteTarget.SHADOW,
            version=shadow_version,
            reason="shadow_mirror",
        )

    async def execute_shadow_mirror(
        self,
        model_id: str,
        features: Dict[str, Any],
    ) -> None:
        """Execute shadow mirror inference (fire-and-forget)."""
        try:
            shadow_version = self._get_shadow_version(model_id)
            if shadow_version is None:
                return

            # Run shadow inference — don't block, don't raise
            _ = await self.engine.predict(
                model_id=model_id,
                features=features,
                version=shadow_version,
            )
        except Exception:
            # Shadow failures are logged but never propagated
            logger.debug("Shadow inference failed for %s", model_id, exc_info=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _route_to_target(
        self,
        model_id: str,
        target: RouteTarget,
    ) -> RoutingDecision:
        """Route to a specific target."""
        if target == RouteTarget.PRODUCTION:
            version = self._get_production_version(model_id)
        elif target == RouteTarget.CANARY:
            version = self._get_canary_version(model_id) or self._get_production_version(model_id)
        elif target == RouteTarget.SHADOW:
            version = self._get_shadow_version(model_id) or self._get_production_version(model_id)
        else:
            version = self._get_production_version(model_id)

        return RoutingDecision(
            model_id=model_id,
            target=target,
            version=version,
            reason=f"force_{target.value}",
        )

    def _get_production_version(self, model_id: str) -> str:
        deployment = self.deployment_manager.get_production(model_id)
        if deployment:
            return deployment.version
        # Fallback — query runtime
        loaded = self.engine.runtime.list_models()
        for model in loaded:
            if model["model_id"] == model_id:
                return model["version"]
        raise ValueError(f"No production version found for {model_id}")

    def _get_canary_version(self, model_id: str) -> Optional[str]:
        deployment = self.deployment_manager.get_canary(model_id)
        return deployment.version if deployment else None

    def _get_canary_traffic(self, model_id: str) -> float:
        deployment = self.deployment_manager.get_canary(model_id)
        return deployment.config.canary_traffic_percent if deployment else 0.0

    def _get_shadow_version(self, model_id: str) -> Optional[str]:
        deployment = self.deployment_manager.get_shadow(model_id)
        return deployment.version if deployment else None

    def _should_route_to_canary(
        self,
        model_id: str,
        traffic_pct: float,
        request_hash: Optional[str] = None,
    ) -> bool:
        """Determine if request should go to canary.

        Uses either probabilistic sampling or consistent hashing.
        """
        if self.config.consistent_hashing and request_hash:
            # Deterministic routing based on request hash
            h = int(hashlib.md5(request_hash.encode()).hexdigest(), 16)
            bucket = h % self.config.hash_ring_size
            return bucket < (traffic_pct / 100.0) * self.config.hash_ring_size
        else:
            # Probabilistic routing
            return random.random() < (traffic_pct / 100.0)

    # ------------------------------------------------------------------
    # A/B testing
    # ------------------------------------------------------------------

    def assign_ab_group(
        self,
        model_id: str,
        request_id: str,
        groups: Optional[Dict[str, float]] = None,
    ) -> str:
        """Assign a request to an A/B test group.

        Args:
            model_id: Model identifier.
            request_id: Unique request identifier.
            groups: {group_name: weight} dict. Default: equal split.

        Returns:
            Assigned group name.
        """
        if groups is None:
            groups = {"A": 0.5, "B": 0.5}

        # Consistent assignment based on request hash
        h = int(hashlib.md5(request_id.encode()).hexdigest(), 16) % 10000
        cumulative = 0.0
        for group, weight in sorted(groups.items()):
            cumulative += weight * 10000
            if h < cumulative:
                self._ab_groups[request_id] = group
                return group

        return "default"

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total = sum(self._route_counts.values())
        return {
            "total_routes": total,
            "production": self._route_counts["production"],
            "canary": self._route_counts["canary"],
            "shadow": self._route_counts["shadow"],
            "pinned": self._route_counts["pinned"],
            "canary_pct": round(
                self._route_counts["canary"] / max(total, 1) * 100, 2
            ),
            "shadow_pct": round(
                self._route_counts["shadow"] / max(total, 1) * 100, 2
            ),
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "routing": self.get_routing_stats(),
        }

    async def shutdown(self) -> None:
        self._initialized = False

    def __repr__(self) -> str:
        return (
            f"TrafficRouter(prod={self._route_counts['production']}, "
            f"canary={self._route_counts['canary']})"
        )
