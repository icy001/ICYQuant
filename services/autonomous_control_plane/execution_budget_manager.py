"""
Execution Budget Manager — Capital and cost limits for autonomous execution.

Enforces daily limits on turnover, transaction costs, slippage,
and market impact for autonomous trading operations.
"""

from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)


class ExecutionBudgetManager:
    """
    Enforces execution-level budgets for autonomous trading.

    Controls:
    - Max daily turnover
    - Max transaction cost
    - Max slippage allowance
    - Max market impact
    """

    def __init__(
        self,
        max_daily_turnover: float = 10_000_000.0,
        max_transaction_cost: float = 10_000.0,
        max_slippage_bps: float = 20.0,
        max_market_impact_bps: float = 15.0,
    ):
        self._max_turnover = max_daily_turnover
        self._max_txn_cost = max_transaction_cost
        self._max_slippage = max_slippage_bps
        self._max_impact = max_market_impact_bps

        self._turnover_used: float = 0.0
        self._txn_cost_used: float = 0.0
        self._slippage_total: float = 0.0
        self._impact_total: float = 0.0
        self._execution_count: int = 0

        self._last_reset = time.time()
        self._reset_interval = 86400

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_turnover(self, amount: float) -> tuple[bool, str]:
        self._maybe_reset()
        if self._turnover_used + amount > self._max_turnover:
            return False, f"Turnover budget exceeded ({self._turnover_used:.0f}/{self._max_turnover:.0f})"
        return True, ""

    def check_cost(self, cost: float) -> tuple[bool, str]:
        self._maybe_reset()
        if self._txn_cost_used + cost > self._max_txn_cost:
            return False, f"Transaction cost budget exceeded"
        return True, ""

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def record_execution(self, turnover: float, cost: float, slippage_bps: float, impact_bps: float):
        """Record an execution event."""
        self._maybe_reset()
        self._turnover_used += turnover
        self._txn_cost_used += cost
        self._slippage_total += slippage_bps * turnover / 10000.0
        self._impact_total += impact_bps * turnover / 10000.0
        self._execution_count += 1

    def _maybe_reset(self):
        if time.time() - self._last_reset >= self._reset_interval:
            self._turnover_used = 0.0
            self._txn_cost_used = 0.0
            self._slippage_total = 0.0
            self._impact_total = 0.0
            self._execution_count = 0
            self._last_reset = time.time()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        self._maybe_reset()
        return {
            "turnover": {"used": self._turnover_used, "limit": self._max_turnover},
            "txn_cost": {"used": self._txn_cost_used, "limit": self._max_txn_cost},
            "slippage_bps": {"max_allowed": self._max_slippage, "total_impact": self._slippage_total},
            "market_impact_bps": {"max_allowed": self._max_impact, "total_impact": self._impact_total},
            "execution_count": self._execution_count,
        }
