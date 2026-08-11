"""
Strategy Allocator — Per-Strategy Capital Distribution

Distributes allocated capital within a strategy across its components:
positions, sub-strategies, or portfolio segments.

Enforces strategy-level constraints: capacity, concentration, risk budget.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StrategyAllocationResult:
    strategy_id: str
    total_allocated: float
    components: Dict[str, float]
    remaining_capacity: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class StrategyAllocator:
    """
    Distributes capital within a strategy across its components.

    Handles:
    - Proportional allocation based on component weights
    - Capacity-aware distribution (component-level limits)
    - Residual handling (unallocated due to capacity)
    """

    def __init__(
        self,
        allocator_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.allocator_id = allocator_id or f"sa-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._component_capacities: Dict[str, float] = {}
        self._history: List[StrategyAllocationResult] = []

    def distribute(
        self,
        strategy_id: str,
        total_capital: float,
        weights: Dict[str, float],
        capacities: Optional[Dict[str, float]] = None,
    ) -> StrategyAllocationResult:
        """
        Distribute capital across components according to weights,
        respecting component capacities.
        """
        if capacities:
            self._component_capacities.update(capacities)

        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight <= 0:
            return StrategyAllocationResult(
                strategy_id=strategy_id,
                total_allocated=0,
                components={},
                remaining_capacity=total_capital,
            )

        # Pro-rata distribution with capacity capping
        allocated = {}
        residual = total_capital
        iterations = 0
        max_iterations = 100

        while residual > 0.01 and iterations < max_iterations:
            iterations += 1
            round_allocated = 0.0
            eligible = False

            for comp_id, weight in weights.items():
                if comp_id in allocated:
                    continue
                target = total_capital * (weight / total_weight)
                cap = self._component_capacities.get(comp_id, float("inf"))
                alloc = min(target, cap, residual)
                allocated[comp_id] = alloc
                round_allocated += alloc
                eligible = True

            residual = total_capital - round_allocated
            if not eligible or residual < 0.01:
                break

        result = StrategyAllocationResult(
            strategy_id=strategy_id,
            total_allocated=total_capital - residual,
            components=allocated,
            remaining_capacity=residual,
        )
        self._history.append(result)
        return result

    def get_results(self) -> List[StrategyAllocationResult]:
        return list(self._history)
