"""
Exposure Controller — manages automatic exposure/position reduction.

Part 1.5: supports automated exposure reduction when triggered by the
governance control plane, following risk reduction priorities:
  CANCEL → STOP_ALLOCATION → REDUCE_LEVERAGE → REDUCE_EXPOSURE → HEDGE → CLOSE
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


class ExposureController:
    """Manages automated exposure reduction for governance control."""

    def __init__(self):
        self._current_exposure: float = 0.0
        self._max_allowed_exposure: float = 0.15  # 15%
        self._current_leverage: float = 1.0
        self._max_allowed_leverage: float = 2.0
        self._reduction_history: List[Dict[str, Any]] = []

    def set_state(
        self,
        current_exposure: float,
        current_leverage: float = 1.0,
    ) -> None:
        """Update current exposure/leverage state."""
        self._current_exposure = current_exposure
        self._current_leverage = current_leverage

    def set_limits(
        self,
        max_exposure: float = 0.15,
        max_leverage: float = 2.0,
    ) -> None:
        """Set exposure/leverage limits."""
        self._max_allowed_exposure = max_exposure
        self._max_allowed_leverage = max_leverage

    def check(
        self,
        current_exposure: Optional[float] = None,
        current_leverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Check if exposure or leverage exceeds limits.

        Returns breaches if any.
        """
        exp = current_exposure or self._current_exposure
        lev = current_leverage or self._current_leverage

        issues = []
        if exp > self._max_allowed_exposure:
            issues.append({
                "metric": "exposure",
                "current": exp,
                "limit": self._max_allowed_exposure,
                "excess": exp - self._max_allowed_exposure,
            })
        if lev > self._max_allowed_leverage:
            issues.append({
                "metric": "leverage",
                "current": lev,
                "limit": self._max_allowed_leverage,
                "excess": lev - self._max_allowed_leverage,
            })

        return {
            "breached": len(issues) > 0,
            "issues": issues,
            "current_exposure": exp,
            "current_leverage": lev,
        }

    def reduce_exposure(
        self,
        target_exposure: Optional[float] = None,
        reason: str = "",
        correlation_id: str = "",
        steps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute exposure reduction following risk-reduction priorities.

        Priority order:
            1. Cancel new orders
            2. Stop new allocation
            3. Reduce leverage
            4. Reduce exposure
            5. Hedge
            6. Emergency close
        """
        target = target_exposure or self._max_allowed_exposure

        # Default reduction steps in priority order
        if steps is None:
            steps = [
                "CANCEL_NEW_ORDERS",
                "STOP_NEW_ALLOCATION",
                "REDUCE_LEVERAGE",
                "REDUCE_EXPOSURE",
            ]

        reduction_id = f"RED-{uuid.uuid4().hex[:12].upper()}"

        result = {
            "reduction_id": reduction_id,
            "status": "INITIATED",
            "reason": reason,
            "correlation_id": correlation_id,
            "current_exposure": self._current_exposure,
            "target_exposure": target,
            "steps_executed": steps,
            "timestamp": time.time(),
            "final_exposure": target,
            "success": True,
        }

        self._reduction_history.append(result)

        # Update state
        self._current_exposure = target
        if "REDUCE_LEVERAGE" in steps:
            self._current_leverage = min(self._current_leverage, self._max_allowed_leverage)

        return result

    def get_reduction_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._reduction_history[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "current_exposure": self._current_exposure,
            "max_allowed_exposure": self._max_allowed_exposure,
            "current_leverage": self._current_leverage,
            "max_allowed_leverage": self._max_allowed_leverage,
            "reductions_applied": len(self._reduction_history),
        }
