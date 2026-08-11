"""
Portfolio Allocator — Three-Level Capital Distribution

Distributes capital through three levels:
    Capital → Strategy → Portfolio → Position/Asset
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AllocationPlan:
    plan_id: str
    capital_allocation: Dict[str, float] = field(default_factory=dict)
    strategy_allocation: Dict[str, float] = field(default_factory=dict)
    position_allocation: Dict[str, float] = field(default_factory=dict)
    total_capital: float = 0.0


class PortfolioAllocator:
    """
    Executes three-level capital allocation:
    1. Capital → Strategy (from CapitalIntelligence)
    2. Strategy → Portfolio (within each strategy)
    3. Portfolio → Position/Asset
    """

    def __init__(
        self,
        allocator_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.allocator_id = allocator_id or f"palloc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._history: List[AllocationPlan] = []

    def allocate(
        self,
        capital: Dict[str, float],       # strategy_id → capital
        weights: Dict[str, float],        # asset → weight
        total_capital: float = 0.0,
    ) -> AllocationPlan:
        """
        Compute allocation at all three levels.

        capital: {strategy_id: capital_amount}
        weights: {asset: portfolio_weight}
        """
        position_allocation = {}
        for asset, weight in weights.items():
            position_allocation[asset] = total_capital * weight

        plan = AllocationPlan(
            plan_id=f"ap-{uuid.uuid4().hex[:8]}",
            capital_allocation=capital,
            strategy_allocation=capital,
            position_allocation=position_allocation,
            total_capital=total_capital,
        )
        self._history.append(plan)
        return plan
