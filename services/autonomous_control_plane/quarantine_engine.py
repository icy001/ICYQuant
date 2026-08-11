"""
Quarantine Engine — Isolates anomalous or degrading models.

Quarantined models:
- Cannot receive production capital
- Cannot execute autonomous trades
- Cannot be promoted
- But continue to be observed for recovery
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QuarantineEngine:
    """
    Manages model quarantine — isolating models that are anomalous
    or degraded without permanently deleting them.

    Quarantine allows observation and potential recovery.
    """

    def __init__(self, lifecycle_engine=None):
        self._lifecycle = lifecycle_engine
        self._quarantined: dict[str, dict] = {}
        self._total_quarantines = 0

    async def quarantine(
        self, model_id: str, reason: str, context: Optional[dict] = None,
    ) -> bool:
        """Place a model into quarantine."""
        if self._lifecycle:
            from .model_lifecycle import ModelLifecycleState
            ok, msg = self._lifecycle.transition(
                model_id, ModelLifecycleState.QUARANTINED, reason
            )
            if ok:
                self._quarantined[model_id] = {
                    "model_id": model_id,
                    "reason": reason,
                    "quarantined_at": time.time(),
                    "context": context or {},
                }
                self._total_quarantines += 1
                logger.warning("Model %s QUARANTINED: %s", model_id, reason)
                return True
        else:
            # Fallback without lifecycle
            self._quarantined[model_id] = {
                "model_id": model_id,
                "reason": reason,
                "quarantined_at": time.time(),
            }
            self._total_quarantines += 1
            return True
        return False

    async def release(self, model_id: str, reason: str = "") -> bool:
        """Release a model from quarantine."""
        if model_id not in self._quarantined:
            return False

        if self._lifecycle:
            from .model_lifecycle import ModelLifecycleState
            ok, _ = self._lifecycle.transition(
                model_id, ModelLifecycleState.SHADOW, f"released: {reason}"
            )
            if ok:
                del self._quarantined[model_id]
                logger.info("Model %s released from quarantine: %s", model_id, reason)
                return True
        return False

    def is_quarantined(self, model_id: str) -> bool:
        return model_id in self._quarantined

    def get_quarantined(self) -> list[dict]:
        return list(self._quarantined.values())

    def stats(self) -> dict:
        return {
            "total_quarantines": self._total_quarantines,
            "currently_quarantined": len(self._quarantined),
        }
