"""Strategy Generator — Generates strategy candidates from alphas.

Converts alpha signals into complete trading strategies with
entry/exit rules, position sizing, and risk controls.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from .strategy_candidate import StrategyCandidate

logger = logging.getLogger(__name__)


class StrategyGenerator:

    def __init__(self) -> None:
        self._strategies_generated: int = 0

    async def generate(
        self,
        alphas: List[Dict[str, Any]],
        max_strategies: int = 5,
    ) -> Dict[str, Any]:
        strategies: List[Dict[str, Any]] = []

        for alpha in alphas[:max_strategies]:
            strategy = StrategyCandidate(
                strategy_id=f"strat_{alpha.get('alpha_id', '')}_{random.randint(1000, 9999)}",
                alpha_id=alpha.get("alpha_id", ""),
                entry_rules=["alpha_signal > threshold"],
                exit_rules=["alpha_signal < threshold", "stop_loss"],
                position_sizing="equal_weight",
                risk_rules=["max_position_10pct", "stop_loss_5pct"],
                universe=alpha.get("symbols", []),
                execution_constraints=["limit_order_only", "max_spread_20bps"],
            )
            strategies.append(strategy.to_dict())

        self._strategies_generated += len(strategies)
        logger.info("Strategies generated: %d (from %d alphas)", len(strategies), len(alphas))

        return {
            "strategies": strategies,
            "total_generated": self._strategies_generated,
        }
