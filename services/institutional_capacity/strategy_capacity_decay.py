"""
Capacity Decay — Models alpha decay as capital increases.

As capital grows: Expected Return declines, Market Impact rises, Slippage increases.
The capacity decay model quantifies this relationship.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CapacityDecay:
    """Capacity decay point: capital -> expected return."""

    capital: float = 0.0
    expected_return: float = 0.0
    marginal_return: float = 0.0
    decay_from_base: float = 0.0       # 0 = no decay, 1 = total decay


@dataclass
class CapacityDecayModel:
    """Models how alpha erodes as capital scales up."""

    model_id: str = field(default_factory=lambda: f"CD-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""

    base_capital: float = 1.0          # Reference capital (small scale)
    base_return: float = 0.20          # Return at base capital

    # Decay parameters
    decay_exponent: float = 0.15       # Typical: 0.05-0.30
    half_life_capital: float = 10.0    # Capital at which return halves

    def return_at(self, capital: float) -> float:
        """Expected return at a given capital level."""
        if capital <= self.base_capital:
            return self.base_return
        return self.base_return * (self.base_capital / capital) ** self.decay_exponent

    def marginal_return(self, capital: float, delta: float = 1.0) -> float:
        """Marginal return of adding delta capital."""
        r_now = self.return_at(capital)
        r_next = self.return_at(capital + delta)
        return r_next - r_now

    def build_decay_curve(self, max_capital: float = 100.0, steps: int = 20) -> List[CapacityDecay]:
        """Build full decay curve."""
        curve = []
        prev_return = self.base_return
        for i in range(steps + 1):
            cap = self.base_capital + (max_capacity := (max_capital - self.base_capital)) * i / steps
            ret = self.return_at(cap)
            marginal = (ret - prev_return) / max(cap - self.base_capital, 1) if i > 0 else self.base_return
            decay = 1.0 - ret / self.base_return
            curve.append(CapacityDecay(cap, ret, marginal, decay))
            prev_return = ret
        return curve

    def optimal_capital(self, min_marginal_return: float = 0.02) -> float:
        """Find optimal capital using marginal return threshold."""
        curve = self.build_decay_curve()
        for d in curve:
            if abs(d.marginal_return) < min_marginal_return:
                return d.capital
        return curve[-1].capital if curve else float("inf")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "strategy_id": self.strategy_id,
            "base_capital": self.base_capital,
            "base_return": self.base_return,
            "decay_exponent": self.decay_exponent,
            "half_life_capital": self.half_life_capital,
        }
