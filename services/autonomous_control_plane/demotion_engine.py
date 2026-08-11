"""
Demotion Engine — Automatic and manual model demotion.

Handles demotion of models from production/simulation due to
performance decay, risk breaches, or other degradation signals.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DemotionEngine:
    """
    Manages automatic and manual model demotions.

    Triggers:
    - Performance decay below threshold
    - Risk limit breaches
    - Execution degradation
    - Model drift detection
    - Manual operator intervention
    """

    def __init__(self, lifecycle_engine=None):
        self._lifecycle = lifecycle_engine
        self._demotions: list[dict] = []
        self._auto_triggers: int = 0

    async def demote(self, model_id: str, reason: str, auto: bool = False) -> tuple[bool, str]:
        """
        Demote a model by one level.

        Production → Shadow
        Shadow → Candidate
        Paper → Shadow
        """
        if self._lifecycle:
            from .model_lifecycle import ModelLifecycleState
            current = self._lifecycle.get_state(model_id)
            if not current:
                return False, "Model not found"

            demotion_map = {
                ModelLifecycleState.PRODUCTION: (ModelLifecycleState.SHADOW, "shadow"),
                ModelLifecycleState.SHADOW: (ModelLifecycleState.CANDIDATE, "candidate"),
                ModelLifecycleState.PAPER: (ModelLifecycleState.SHADOW, "shadow"),
                ModelLifecycleState.DEGRADED: (ModelLifecycleState.SHADOW, "shadow"),
            }
            mapping = demotion_map.get(current)
            if not mapping:
                return False, f"No demotion path from {current.value}"

            target, _ = mapping
            ok, msg = self._lifecycle.transition(model_id, target, reason)
            if ok:
                self._demotions.append({
                    "model_id": model_id,
                    "from_state": current.value,
                    "to_state": target.value,
                    "reason": reason,
                    "auto": auto,
                    "timestamp": time.time(),
                })
                if auto:
                    self._auto_triggers += 1
                logger.warning("Model %s demoted %s → %s: %s", model_id, current.value, target.value, reason)
                return True, ""
            return False, msg

        return False, "No lifecycle engine bound"

    async def check_and_demote(self, model_id: str, context: dict) -> Optional[dict]:
        """Check degradation signals and auto-demote if needed."""
        from .model_degradation_detector import ModelDegradationDetector, DegradationLevel
        detector = ModelDegradationDetector()

        level, signals = detector.evaluate(
            model_id,
            performance_ratio=context.get("performance_ratio", 1.0),
            risk_breach=context.get("risk_breach", False),
            execution_degraded=context.get("execution_degraded", False),
            drift_detected=context.get("drift_detected", False),
        )

        if level in (DegradationLevel.DEGRADED, DegradationLevel.SEVERE):
            reason = f"Auto-demotion: {level.value} ({', '.join(signals)})"
            ok, _ = await self.demote(model_id, reason, auto=True)
            return {
                "demoted": ok,
                "level": level.value,
                "signals": signals,
                "reason": reason,
            }

        return None

    def stats(self) -> dict:
        return {
            "demotions_total": len(self._demotions),
            "auto_triggers": self._auto_triggers,
            "manual": len(self._demotions) - self._auto_triggers,
        }
