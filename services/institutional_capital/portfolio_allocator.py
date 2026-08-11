"""
Portfolio Allocator — Distribute Strategy Capital to Portfolios

Receives strategy-level capital and distributes it across the
strategy's portfolios according to weights and constraints.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAllocResult:
    result_id: str
    strategy_id: str
    allocated: Dict[str, float]
    residual: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PortfolioAllocator:
    """
    Distributes strategy capital across multiple portfolios.
    Handles: proportional distribution, capacity capping, residual handling.
    """

    def __init__(
        self,
        allocator_id: Optional[str] = None,
        portfolio_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.allocator_id = allocator_id or f"pa-{uuid.uuid4().hex[:12]}"
        self._portfolio_pool = portfolio_pool
        self.config = config or {}
        self._history: List[PortfolioAllocResult] = []

    def allocate(
        self,
        strategy_id: str,
        total_capital: float,
        weights: Dict[str, float],
        capacity_limits: Optional[Dict[str, float]] = None,
    ) -> PortfolioAllocResult:
        """
        Distribute total_capital across portfolios by weights,
        respecting individual capacity limits.
        """
        capacity_limits = capacity_limits or {}
        total_weight = sum(weights.values())
        if total_weight <= 0:
            return PortfolioAllocResult(
                result_id=f"pa-{uuid.uuid4().hex[:8]}",
                strategy_id=strategy_id,
                allocated={},
                residual=total_capital,
            )

        allocated = {}
        remaining = total_capital

        # First pass: allocate up to capacity
        for pid, w in sorted(weights.items(), key=lambda x: -x[1]):
            target = total_capital * (w / total_weight)
            cap = capacity_limits.get(pid, float("inf"))
            alloc = min(target, cap, remaining)
            allocated[pid] = alloc
            remaining -= alloc

        # Second pass: distribute residual to uncapped portfolios
        uncapped = [pid for pid in allocated if capacity_limits.get(pid, float("inf")) == float("inf")]
        if uncapped and remaining > 0:
            per_pid = remaining / len(uncapped)
            for pid in uncapped:
                allocated[pid] += per_pid
            remaining = 0.0

        result = PortfolioAllocResult(
            result_id=f"pa-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            allocated=allocated,
            residual=remaining,
        )
        self._history.append(result)
        return result

    def get_history(self) -> List[PortfolioAllocResult]:
        return list(self._history)
