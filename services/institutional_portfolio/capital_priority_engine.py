"""
Capital Priority Engine — Compute Capital Allocation Priority

Computes the Capital Priority Score for each strategy, used by
CapitalCoordinator to resolve competing capital requests.

Priority = f(
    expected_return, risk_adjusted_return, marginal_efficiency,
    capacity, correlation, liquidity, alpha_decay
)
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapitalPriority:
    strategy_id: str
    score: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)


class CapitalPriorityEngine:
    """
    Computes capital allocation priority scores.

    Factors (weighted):
    - Expected Return (30%)
    - Risk-Adjusted Return (25%)
    - Marginal Efficiency (20%)
    - Capacity Available (10%)
    - Correlation (5%)
    - Liquidity (5%)
    - Alpha Decay (5%)
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        registry=None,
        efficiency=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"cpe-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self._efficiency = efficiency
        self.config = config or {}
        self._weights = {
            "expected_return": 0.30,
            "risk_adjusted": 0.25,
            "marginal_efficiency": 0.20,
            "capacity": 0.10,
            "correlation": 0.05,
            "liquidity": 0.05,
            "alpha_decay": 0.05,
        }
        self._scores: Dict[str, CapitalPriority] = {}

    def compute_all(self) -> Dict[str, CapitalPriority]:
        if not self._registry:
            return {}
        self._scores.clear()
        for sid, rec in self._registry.get_active().items():
            self._scores[sid] = self._compute(sid, rec)
        return self._scores

    def _compute(self, strategy_id: str, record) -> CapitalPriority:
        components = {}
        score = 0.0

        # Expected return
        ret = getattr(record, 'expected_return', 0.05)
        components["expected_return"] = min(1.0, ret / 0.20)

        # Risk-adjusted
        sharpe = getattr(record, 'sharpe', 1.0)
        components["risk_adjusted"] = min(1.0, sharpe / 3.0)

        # Marginal efficiency
        components["marginal_efficiency"] = 0.5
        if self._efficiency:
            eff = self._efficiency.get(strategy_id)
            if eff:
                components["marginal_efficiency"] = eff.marginal_efficiency

        # Capacity
        cap = getattr(record, 'capacity', float("inf"))
        alloc = getattr(record, 'capital_allocation', 0.0)
        components["capacity"] = 1.0 - min(1.0, alloc / cap) if cap > 0 else 1.0

        # Correlation (lower is better for diversification)
        corr = getattr(record, 'correlation', 0.5)
        components["correlation"] = 1.0 - abs(corr)

        # Liquidity
        components["liquidity"] = 0.7

        # Alpha decay urgency
        components["alpha_decay"] = 0.5

        for k, v in components.items():
            score += self._weights.get(k, 0.05) * v

        return CapitalPriority(strategy_id=strategy_id, score=score, components=components)

    def rank(self) -> List[Tuple[str, float]]:
        return sorted(
            [(sid, s.score) for sid, s in self._scores.items()],
            key=lambda x: -x[1],
        )
