"""
Drift Controller — Weight & Risk Drift Detection

Monitors portfolio drift from targets:
- Weight drift: position weight moved from target
- Risk drift: risk contribution changed even if weight unchanged

Triggers rebalance when drift exceeds configured thresholds.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DriftState:
    asset: str
    weight_drift: float = 0.0
    risk_drift: float = 0.0
    weight_exceeded: bool = False
    risk_exceeded: bool = False


class DriftController:
    """
    Monitors weight and risk drift from target allocations.

    Example: Target NVDA = 10%. Current = 14%. Drift = +4%.
    If threshold is 2% → Rebalance Required.

    Risk drift: weight = 10% but volatility increased → risk contribution 5% → 11%.
    If risk drift threshold exceeded → rebalance required even if weight stable.
    """

    def __init__(
        self,
        controller_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.controller_id = controller_id or f"dc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._weight_threshold = self.config.get("weight_drift_threshold", 0.02)
        self._risk_threshold = self.config.get("risk_drift_threshold", 0.03)
        self._drift_states: Dict[str, DriftState] = {}
        self._targets: Dict[str, float] = {}
        self._current: Dict[str, float] = {}

    def set_targets(self, targets: Dict[str, float]) -> None:
        self._targets = targets

    def set_current(self, current: Dict[str, float], risk_contributions: Optional[Dict[str, float]] = None) -> None:
        self._current = current
        risk_contributions = risk_contributions or {}

        for asset, cw in current.items():
            tw = self._targets.get(asset, 0.0)
            state = self._drift_states.get(asset, DriftState(asset=asset))
            state.weight_drift = cw - tw
            state.weight_exceeded = abs(state.weight_drift) > self._weight_threshold
            state.risk_drift = risk_contributions.get(asset, 0.0)
            state.risk_exceeded = abs(state.risk_drift) > self._risk_threshold
            self._drift_states[asset] = state

    def get_drifted_assets(self) -> Dict[str, float]:
        """Get assets that exceeded drift thresholds."""
        return {
            asset: state.weight_drift
            for asset, state in self._drift_states.items()
            if state.weight_exceeded or state.risk_exceeded
        }

    def get_current_weights(self) -> Dict[str, float]:
        return dict(self._current)

    def compute_deltas(self, targets: Dict[str, float]) -> Dict[str, float]:
        """Compute required weight changes to reach targets."""
        return {
            asset: targets.get(asset, 0) - self._current.get(asset, 0)
            for asset in set(list(targets.keys()) + list(self._current.keys()))
        }

    def has_drift(self) -> bool:
        return any(s.weight_exceeded or s.risk_exceeded for s in self._drift_states.values())

    def get_total_drift(self) -> float:
        return sum(abs(s.weight_drift) for s in self._drift_states.values())
