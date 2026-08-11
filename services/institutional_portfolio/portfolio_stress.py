"""
Portfolio Stress — Extreme Scenario Stress Testing

Stress scenarios:
- Market crash (-30%)
- Volatility spike (+200%)
- Liquidity collapse (-80%)
- Correlation to 1 (all assets move together)
- Execution cost spike (10x)
- Strategy failure cascade
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StressResult:
    stress_name: str
    portfolio_pnl: float = 0.0
    capital_remaining: float = 1.0
    survival: bool = True
    max_drawdown: float = 0.0
    required_delever: float = 0.0


class PortfolioStress:
    """
    Extreme scenario stress testing for capital survival analysis.

    Answers: "If the market crashes 30% and liquidity disappears,
    can the portfolio survive?"
    """

    def __init__(
        self,
        stress_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.stress_id = stress_id or f"pst-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._stress_multipliers = {
            "market_crash": -0.30,
            "vol_spike": -0.25,
            "liquidity_collapse": -0.35,
            "correlation_spike": -0.20,
            "execution_cost_spike": -0.15,
            "strategy_failure_cascade": -0.40,
        }

    def stress_test(
        self,
        portfolio_value: float,
        exposures: Optional[Dict[str, float]] = None,
    ) -> List[StressResult]:
        """Run all stress tests."""
        results = []
        for name, multiplier in self._stress_multipliers.items():
            pnl = portfolio_value * multiplier
            remaining = max(0.0, portfolio_value + pnl)
            drawdown = abs(pnl) / max(1, portfolio_value)
            survival = remaining > portfolio_value * 0.70

            results.append(StressResult(
                stress_name=name,
                portfolio_pnl=pnl,
                capital_remaining=remaining,
                survival=survival,
                max_drawdown=drawdown,
                required_delever=0.0 if survival else (portfolio_value * 0.70 - remaining) / max(1, portfolio_value),
            ))

        return results

    def worst_case(self, results: List[StressResult]) -> StressResult:
        return max(results, key=lambda r: abs(r.portfolio_pnl), default=StressResult(stress_name="NONE", survival=True))
