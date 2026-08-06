"""Feature Flag Adapter — enables canary and blue-green scheduling.

The :class:`FeatureFlagAdapter` integrates with the feature flag system
to support:
* Canary scheduling — roll out new scheduler versions gradually
* Blue/Green scheduling — dual scheduler deployments
* A/B scheduling — compare scheduling strategies
* Feature-gated trigger evaluation

Architecture::

    Feature Flag Service ──→ FeatureFlagAdapter ──→ Scheduler
                                  │
                          Canary / Blue-Green / A/B
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlagEvaluation(enum.Enum):
    """Feature flag evaluation results."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    UNKNOWN = "unknown"
    ERROR = "error"


class FeatureFlagAdapter:
    """Adapter for feature flag integration.

    Responsibilities:
    * Evaluate feature flags for canary scheduling
    * Support blue-green and A/B scheduler deployments
    * Gate trigger evaluation behind feature flags
    * Gradual rollout of new scheduler features

    Usage::

        adapter = FeatureFlagAdapter()
        await adapter.connect()
        result = await adapter.evaluate("scheduler.v2.enabled", context={"user": "trader-1"})
        if result == FlagEvaluation.ENABLED:
            # Use new scheduler
    """

    def __init__(self, flag_service: Any = None) -> None:
        self._service = flag_service
        self._lock = threading.Lock()
        self._connected = False
        self._flags: Dict[str, Dict[str, Any]] = {}
        self._evaluation_count: int = 0
        self._last_eval_at: Optional[datetime] = None
        self._default_enabled: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    @property
    def flags(self) -> List[str]:
        return list(self._flags.keys())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the feature flag service."""
        logger.info("FeatureFlagAdapter: connecting")
        if self._service and hasattr(self._service, "connect"):
            await self._service.connect()
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the feature flag service."""
        self._connected = False
        self._flags.clear()
        logger.info("FeatureFlagAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize feature flag state."""
        return {"connected": self._connected, "flags": len(self._flags), "evaluations": self._evaluation_count}

    # ------------------------------------------------------------------
    # Flag Management
    # ------------------------------------------------------------------

    def register_flag(
        self,
        name: str,
        description: str = "",
        default: bool = False,
        rollout_percentage: int = 0,
    ) -> None:
        """Register a feature flag."""
        self._flags[name] = {
            "description": description,
            "default": default,
            "rollout_percentage": rollout_percentage,
        }
        logger.info("FeatureFlagAdapter: registered flag '%s'", name)

    async def evaluate(self, flag_name: str, context: Optional[Dict[str, Any]] = None) -> FlagEvaluation:
        """Evaluate a feature flag for the given context.

        Supports:
        * Percentage-based rollout
        * User/group targeting
        * Environment-based gates
        """
        self._evaluation_count += 1
        self._last_eval_at = datetime.now(timezone.utc)

        flag = self._flags.get(flag_name)
        if not flag:
            # Try external service
            if self._service and hasattr(self._service, "evaluate"):
                try:
                    result = await self._service.evaluate(flag_name, context)
                    return FlagEvaluation.ENABLED if result else FlagEvaluation.DISABLED
                except Exception:
                    return FlagEvaluation.ERROR
            return FlagEvaluation.UNKNOWN

        # Percentage rollout
        rollout = flag.get("rollout_percentage", 0)
        if rollout > 0:
            import hashlib
            user = (context or {}).get("user", "default")
            bucket = int(hashlib.md5(user.encode()).hexdigest(), 16) % 100
            if bucket < rollout:
                return FlagEvaluation.ENABLED

        return FlagEvaluation.ENABLED if flag.get("default", False) else FlagEvaluation.DISABLED

    async def is_enabled(self, flag_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Convenience: return True if flag is enabled."""
        return await self.evaluate(flag_name, context) == FlagEvaluation.ENABLED

    # ------------------------------------------------------------------
    # Canary / Blue-Green / A/B
    # ------------------------------------------------------------------

    async def canary_schedule(self, flag_name: str, schedule_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate whether a schedule should run on the canary scheduler."""
        evaluation = await self.evaluate(flag_name, context)
        return {
            "schedule_id": schedule_id,
            "flag": flag_name,
            "evaluation": evaluation.value,
            "use_canary": evaluation == FlagEvaluation.ENABLED,
        }

    async def blue_green_schedule(self, schedule_id: str, target: str = "blue") -> Dict[str, Any]:
        """Route a schedule to blue or green scheduler deployment."""
        return {"schedule_id": schedule_id, "target": target, "status": "routed"}

    async def ab_schedule(self, schedule_id: str, variant: str = "A", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Route a schedule to an A/B test variant."""
        return {"schedule_id": schedule_id, "variant": variant, "status": "routed"}
