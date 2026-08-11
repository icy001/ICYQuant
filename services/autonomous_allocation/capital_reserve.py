"""Capital Reserve — dynamic reserve management.

Reserve is no longer a fixed percentage.
It adapts based on:
- Stress risk level
- Liquidity risk
- Margin risk
- Execution risk
- Tail risk
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReserveLevel(str, Enum):
    """Reserve level based on market conditions."""
    MINIMAL = "MINIMAL"  # 5%
    NORMAL = "NORMAL"  # 10%
    CAUTION = "CAUTION"  # 15%
    STRESS = "STRESS"  # 25%
    CRITICAL = "CRITICAL"  # 40%


RESERVE_RATIOS = {
    ReserveLevel.MINIMAL: 0.05,
    ReserveLevel.NORMAL: 0.10,
    ReserveLevel.CAUTION: 0.15,
    ReserveLevel.STRESS: 0.25,
    ReserveLevel.CRITICAL: 0.40,
}


@dataclass
class ReserveState:
    """Current state of capital reserves."""
    level: ReserveLevel = ReserveLevel.NORMAL
    reserve_ratio: float = 0.10
    reserve_amount: float = 0.0
    total_capital: float = 0.0
    stress_risk: float = 0.0
    liquidity_risk: float = 0.0
    margin_risk: float = 0.0
    execution_risk: float = 0.0
    tail_risk: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapitalReserve:
    """Manages dynamic capital reserves.

    Reserve ratio adapts to market conditions:
    - Higher stress → higher reserve
    - Lower liquidity → higher reserve
    - Higher margin requirements → higher reserve
    - Higher tail risk → higher reserve
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._level = ReserveLevel.NORMAL
        self._total_capital = 0.0

    @property
    def level(self) -> ReserveLevel:
        return self._level

    @property
    def reserve_ratio(self) -> float:
        return RESERVE_RATIOS.get(self._level, 0.10)

    @property
    def reserve_amount(self) -> float:
        return self._total_capital * self.reserve_ratio

    def set_total_capital(self, capital: float) -> None:
        self._total_capital = capital

    def assess_reserve_level(self,
                              stress_risk: float = 0.0,
                              liquidity_risk: float = 0.0,
                              margin_risk: float = 0.0,
                              execution_risk: float = 0.0,
                              tail_risk: float = 0.0) -> ReserveLevel:
        """Determine appropriate reserve level from risk indicators.

        Composite risk score determines the level.
        """
        composite = (
            0.30 * stress_risk +
            0.25 * liquidity_risk +
            0.20 * margin_risk +
            0.15 * execution_risk +
            0.10 * tail_risk
        )

        if composite > 0.80:
            level = ReserveLevel.CRITICAL
        elif composite > 0.60:
            level = ReserveLevel.STRESS
        elif composite > 0.40:
            level = ReserveLevel.CAUTION
        elif composite > 0.20:
            level = ReserveLevel.NORMAL
        else:
            level = ReserveLevel.MINIMAL

        self._level = level
        return level

    def get_state(self) -> ReserveState:
        """Get current reserve state."""
        return ReserveState(
            level=self._level,
            reserve_ratio=self.reserve_ratio,
            reserve_amount=self.reserve_amount,
            total_capital=self._total_capital,
        )

    def available_for_deployment(self) -> float:
        """Capital available for deployment after reserve."""
        return max(0.0, self._total_capital - self.reserve_amount)

    def required_reserve_increase(self, target_level: ReserveLevel) -> float:
        """Compute how much additional reserve is needed to reach target level."""
        current = self.reserve_amount
        target_ratio = RESERVE_RATIOS.get(target_level, 0.10)
        target_amount = self._total_capital * target_ratio
        return max(0.0, target_amount - current)

    def release_from_reserve(self, amount: float) -> float:
        """Release capital from reserves (for outflows)."""
        max_release = max(0.0, self.reserve_amount - self._total_capital * 0.03)
        released = min(amount, max_release)
        return released
