"""
Execution Throttle — Dynamically adjusts execution rate based on market conditions.

Normal: 20% participation → Stressed: 10% → Crisis: 3%

Prevents aggressive execution during poor liquidity conditions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .liquidity_regime import LiquidityRegime

# Throttle multipliers per regime
THROTTLE_MAP: Dict[LiquidityRegime, float] = {
    LiquidityRegime.HIGH_LIQUIDITY: 1.2,
    LiquidityRegime.NORMAL: 1.0,
    LiquidityRegime.LOW_LIQUIDITY: 0.7,
    LiquidityRegime.STRESSED: 0.4,
    LiquidityRegime.CRISIS: 0.15,
}


class ThrottleState(str, Enum):
    FULL = "full"               # Normal execution speed
    MODERATE = "moderate"       # Slightly reduced
    REDUCED = "reduced"         # Significantly reduced
    MINIMAL = "minimal"         # Bare minimum
    HALTED = "halted"           # No execution


@dataclass
class ExecutionThrottle:
    """Dynamic execution rate throttle."""

    throttle_id: str = field(default_factory=lambda: f"ET-{uuid.uuid4().hex[:8]}")
    current_state: ThrottleState = ThrottleState.FULL
    multiplier: float = 1.0

    # Conditions
    base_rate: float = 1.0              # base execution rate
    effective_rate: float = 1.0          # throttled rate

    liquidity_regime: LiquidityRegime = LiquidityRegime.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "throttle_id": self.throttle_id,
            "state": self.current_state.value,
            "multiplier": self.multiplier,
            "effective_rate": self.effective_rate,
            "regime": self.liquidity_regime.value,
        }

    def update_for_regime(self, regime: LiquidityRegime) -> None:
        self.liquidity_regime = regime
        self.multiplier = THROTTLE_MAP.get(regime, 1.0)

        if self.multiplier >= 1.0:
            self.current_state = ThrottleState.FULL
        elif self.multiplier >= 0.65:
            self.current_state = ThrottleState.MODERATE
        elif self.multiplier >= 0.35:
            self.current_state = ThrottleState.REDUCED
        elif self.multiplier > 0:
            self.current_state = ThrottleState.MINIMAL
        else:
            self.current_state = ThrottleState.HALTED

        self.effective_rate = self.base_rate * self.multiplier

    def throttle(self, order_size: float) -> float:
        """Apply throttle to order size."""
        return order_size * self.effective_rate

    def halt(self) -> None:
        self.current_state = ThrottleState.HALTED
        self.multiplier = 0.0
        self.effective_rate = 0.0

    def resume(self) -> None:
        self.current_state = ThrottleState.FULL
        self.multiplier = 1.0
        self.effective_rate = self.base_rate
