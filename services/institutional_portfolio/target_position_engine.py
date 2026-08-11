"""
Target Position Engine — Compute Portfolio Target Positions

After netting and conflict resolution, compute final target positions:

    target = {
        asset: target_weight, target_notional, gross_exposure,
        net_exposure, risk_contribution, capital_requirement
    }
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TargetPosition:
    asset: str
    target_weight: float = 0.0
    target_notional: float = 0.0
    current_weight: float = 0.0
    current_notional: float = 0.0
    required_change: float = 0.0
    risk_contribution: float = 0.0
    capital_requirement: float = 0.0
    source: str = "NETTED"


class TargetPositionEngine:
    """
    Computes target positions for the portfolio after netting.

    Outputs per-asset: target weight, notional, change from current,
    risk contribution, and capital requirement.
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"tpe-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._targets: Dict[str, TargetPosition] = {}
        self._total_capital = self.config.get("total_capital", 1.0)

    def compute(
        self,
        netted_positions: Dict[str, float],
        current_positions: Optional[Dict[str, float]] = None,
        total_capital: Optional[float] = None,
    ) -> Dict[str, TargetPosition]:
        """Compute target positions from netted positions."""
        if total_capital is not None:
            self._total_capital = total_capital
        current_positions = current_positions or {}
        self._targets.clear()
        capital = max(self._total_capital, 0.01)

        for asset, target_pos in netted_positions.items():
            current = current_positions.get(asset, 0.0)
            target_notional = target_pos * capital
            current_notional = current * capital

            self._targets[asset] = TargetPosition(
                asset=asset,
                target_weight=target_pos,
                target_notional=target_notional,
                current_weight=current,
                current_notional=current_notional,
                required_change=target_pos - current,
                capital_requirement=abs(target_notional),
                source="NETTED",
            )

        return self._targets

    def get_all_targets(self) -> Dict[str, TargetPosition]:
        return dict(self._targets)

    def get_total_capital_requirement(self) -> float:
        return sum(t.capital_requirement for t in self._targets.values())

    def get_total_required_change(self) -> float:
        return sum(abs(t.required_change) for t in self._targets.values())

    def set_total_capital(self, capital: float) -> None:
        self._total_capital = capital
