"""Feature Flag Adapter — canary releases and blue-green deployments for workflows.

Supports:

* **Workflow Version A / B** — run multiple versions side by side
* **Canary Workflow** — gradual rollout to a subset of traffic
* **Blue / Green** — instant switch between versions

Used for gradual rollouts, A/B testing, and safe rollback of workflow changes.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlagScope(str, Enum):
    """Scope of a feature flag."""

    GLOBAL = "global"
    WORKFLOW = "workflow"
    NODE = "node"
    USER = "user"
    ACCOUNT = "account"


@dataclass
class FeatureFlag:
    """A feature flag controlling workflow behaviour."""

    flag_id: str
    name: str
    description: str = ""
    scope: FlagScope = FlagScope.WORKFLOW
    enabled: bool = False
    rollout_pct: float = 0.0  # 0.0–100.0
    variant_a: str = "default"
    variant_b: str = "canary"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_active_for(self, key: str = "") -> bool:
        """Determine if this flag is active for a given key."""
        if not self.enabled:
            return False
        if self.rollout_pct >= 100.0:
            return True
        # Deterministic based on key hash
        if key:
            h = hash(key) % 100
            return h < self.rollout_pct
        return random.random() * 100 < self.rollout_pct

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag_id": self.flag_id,
            "name": self.name,
            "description": self.description,
            "scope": self.scope.value,
            "enabled": self.enabled,
            "rollout_pct": self.rollout_pct,
            "variant_a": self.variant_a,
            "variant_b": self.variant_b,
        }


class FeatureFlagAdapter:
    """Feature flag management for canary and blue-green workflow deployments.

    Usage::

        adapter = FeatureFlagAdapter()
        await adapter.start()
        flag = FeatureFlag(flag_id="wf_v2", name="order_execution_v2", rollout_pct=10.0)
        await adapter.set_flag(flag)
        is_canary = await adapter.is_active("wf_v2", key="account_123")
    """

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._lock = threading.RLock()
        self._started = False
        self._flags: Dict[str, FeatureFlag] = {}
        self._on_change_callbacks: list = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("FeatureFlagAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("FeatureFlagAdapter: stopped")

    # ------------------------------------------------------------------
    # Flag management
    # ------------------------------------------------------------------

    async def set_flag(self, flag: FeatureFlag) -> None:
        with self._lock:
            self._flags[flag.flag_id] = flag
        for cb in self._on_change_callbacks:
            try:
                cb(flag.flag_id, flag)
            except Exception:
                logger.exception("FeatureFlagAdapter: change callback error")

    async def get_flag(self, flag_id: str) -> Optional[FeatureFlag]:
        with self._lock:
            return self._flags.get(flag_id)

    async def delete_flag(self, flag_id: str) -> bool:
        with self._lock:
            return self._flags.pop(flag_id, None) is not None

    async def list_flags(
        self,
        *,
        scope: Optional[FlagScope] = None,
        enabled_only: bool = False,
    ) -> List[FeatureFlag]:
        with self._lock:
            results = list(self._flags.values())
            if scope:
                results = [f for f in results if f.scope == scope]
            if enabled_only:
                results = [f for f in results if f.enabled]
            return results

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def is_active(self, flag_id: str, *, key: str = "") -> bool:
        """Check if a feature flag is active for a given key."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag is None:
                return False
            return flag.is_active_for(key)

    async def get_variant(self, flag_id: str, *, key: str = "") -> str:
        """Get which variant (a or b) should be used."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag is None:
                return "default"
            if flag.is_active_for(key):
                return flag.variant_b
            return flag.variant_a

    # ------------------------------------------------------------------
    # Rollout control
    # ------------------------------------------------------------------

    async def set_rollout(self, flag_id: str, pct: float) -> None:
        """Update the rollout percentage for a flag."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag:
                flag.rollout_pct = max(0.0, min(100.0, pct))
                flag.updated_at = datetime.utcnow()

    async def enable(self, flag_id: str) -> None:
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag:
                flag.enabled = True

    async def disable(self, flag_id: str) -> None:
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag:
                flag.enabled = False

    # ------------------------------------------------------------------
    # Change notification
    # ------------------------------------------------------------------

    def on_change(self, callback) -> None:
        self._on_change_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_flags": len(self._flags),
                "enabled": sum(1 for f in self._flags.values() if f.enabled),
            }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_flags": len(self._flags),
                "enabled_flags": sum(1 for f in self._flags.values() if f.enabled),
                "flags": {
                    fid: {"enabled": f.enabled, "rollout_pct": f.rollout_pct}
                    for fid, f in self._flags.items()
                },
            }
