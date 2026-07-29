"""Market Impact Controller.

Real-time execution control based on market impact monitoring.
Adjusts execution parameters during live order execution to
stay within impact budget.

Monitors realized impact vs. projected impact and adapts:
- Slice size (reduce if exceeding impact budget)
- Slice frequency (slow down if market moving against)
- Algorithm switch (escalate to POV if impact too high)

Integrates with Liquidity Engine for live microstructure data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================


class ImpactBudgetStatus(str, Enum):
    """Status of impact budget consumption."""

    ON_TRACK = "ON_TRACK"         # Within expected range
    APPROACHING_LIMIT = "APPROACHING_LIMIT"  # Near budget limit
    EXCEEDED = "EXCEEDED"        # Over budget, need adjustment
    SEVERE = "SEVERE"            # Far over budget, emergency


class AdjustmentAction(str, Enum):
    """Action to take when impact exceeds budget."""

    NONE = "NONE"
    REDUCE_SLICE_SIZE = "REDUCE_SLICE_SIZE"
    SLOW_DOWN = "SLOW_DOWN"
    SWITCH_ALGORITHM = "SWITCH_ALGORITHM"
    PAUSE = "PAUSE"
    CANCEL = "CANCEL"


# =============================================================================
# Dataclass
# =============================================================================


@dataclass
class ImpactBudget:
    """Execution impact budget and tracking."""

    order_id: str
    symbol: str
    max_total_cost_bps: float = 20.0       # Max acceptable total cost (bps)
    projected_cost_bps: float = 0.0        # Pre-execution estimate
    realized_cost_bps: float = 0.0         # Actual realized so far
    remaining_budget_bps: float = 0.0      # Budget - realized
    budget_consumed_pct: float = 0.0       # % of budget consumed
    status: ImpactBudgetStatus = ImpactBudgetStatus.ON_TRACK
    slice_count: int = 0
    total_slices: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.remaining_budget_bps = self.max_total_cost_bps - self.realized_cost_bps
        if self.max_total_cost_bps > 0:
            self.budget_consumed_pct = self.realized_cost_bps / self.max_total_cost_bps
        self.status = self._compute_status()

    def _compute_status(self) -> ImpactBudgetStatus:
        if self.budget_consumed_pct >= 1.5:
            return ImpactBudgetStatus.SEVERE
        elif self.budget_consumed_pct >= 1.0:
            return ImpactBudgetStatus.EXCEEDED
        elif self.budget_consumed_pct >= 0.8:
            return ImpactBudgetStatus.APPROACHING_LIMIT
        return ImpactBudgetStatus.ON_TRACK


# =============================================================================
# Impact Controller
# =============================================================================


class ImpactController:
    """Real-time impact monitoring and adjustment.

    Tracks realized impact against budget during execution and
    recommends adjustments when limits are approached or exceeded.

    Usage:
        controller = ImpactController()
        budget = controller.create_budget(
            order_id="ORD_001",
            symbol="NVDA",
            max_total_cost_bps=15.0,
            projected_cost_bps=8.0,
            total_slices=10,
        )
        # After each slice fill:
        action = controller.check_budget(budget, realized_cost_so_far=12.0)
        if action != AdjustmentAction.NONE:
            print(f"Action needed: {action.value}")
    """

    def __init__(self) -> None:
        self._budgets: Dict[str, ImpactBudget] = {}

    def create_budget(
        self,
        order_id: str,
        symbol: str,
        max_total_cost_bps: float = 20.0,
        projected_cost_bps: float = 0.0,
        total_slices: int = 1,
    ) -> ImpactBudget:
        """Create an impact budget for an order.

        Args:
            order_id: Order identifier
            symbol: Trading symbol
            max_total_cost_bps: Maximum acceptable total cost
            projected_cost_bps: Pre-execution impact estimate
            total_slices: Total planned slices

        Returns:
            ImpactBudget tracking object
        """
        budget = ImpactBudget(
            order_id=order_id,
            symbol=symbol,
            max_total_cost_bps=max_total_cost_bps,
            projected_cost_bps=projected_cost_bps,
            total_slices=total_slices,
        )
        self._budgets[order_id] = budget
        return budget

    def update_budget(
        self,
        order_id: str,
        realized_cost_bps: float,
        slice_num: int,
    ) -> ImpactBudget:
        """Update budget with realized costs.

        Args:
            order_id: Order identifier
            realized_cost_bps: Cumulated realized cost so far
            slice_num: Current slice number

        Returns:
            Updated ImpactBudget
        """
        budget = self._budgets.get(order_id)
        if budget is None:
            raise ValueError(f"No budget found for order {order_id}")

        budget.realized_cost_bps = realized_cost_bps
        budget.slice_count = slice_num
        budget.remaining_budget_bps = budget.max_total_cost_bps - realized_cost_bps
        budget.budget_consumed_pct = (
            realized_cost_bps / budget.max_total_cost_bps
            if budget.max_total_cost_bps > 0 else 0.0
        )
        budget.status = budget._compute_status()
        budget.timestamp = datetime.utcnow()

        return budget

    def get_budget(self, order_id: str) -> Optional[ImpactBudget]:
        """Get budget by order ID."""
        return self._budgets.get(order_id)

    def check_budget(
        self,
        budget: ImpactBudget,
        remaining_slices: Optional[int] = None,
    ) -> AdjustmentAction:
        """Check budget status and recommend adjustment.

        Args:
            budget: ImpactBudget to check
            remaining_slices: Remaining slices (for pacing calc)

        Returns:
            Recommended AdjustmentAction
        """
        if budget.status == ImpactBudgetStatus.SEVERE:
            # Check if any budget left
            if budget.remaining_budget_bps <= -20:
                return AdjustmentAction.CANCEL
            return AdjustmentAction.SWITCH_ALGORITHM

        elif budget.status == ImpactBudgetStatus.EXCEEDED:
            return AdjustmentAction.REDUCE_SLICE_SIZE

        elif budget.status == ImpactBudgetStatus.APPROACHING_LIMIT:
            # If consuming faster than projected
            if remaining_slices is not None and budget.slice_count > 0:
                consumed_pct = budget.slice_count / budget.total_slices
                if budget.budget_consumed_pct > consumed_pct * 1.2:
                    return AdjustmentAction.SLOW_DOWN
            return AdjustmentAction.REDUCE_SLICE_SIZE

        return AdjustmentAction.NONE

    def should_adjust(
        self,
        budget: ImpactBudget,
        current_slice_cost_bps: float,
        remaining_slices: int,
    ) -> Dict[str, Any]:
        """Determine if and how to adjust execution.

        Args:
            budget: Current ImpactBudget
            current_slice_cost_bps: Cost of the most recent slice
            remaining_slices: Number of slices remaining

        Returns:
            Dict with adjustment recommendations
        """
        action = self.check_budget(budget, remaining_slices)

        # Calculate recommended parameters
        recommendations = {
            "action": action.value,
            "budget_status": budget.status.value,
            "remaining_budget_bps": round(budget.remaining_budget_bps, 2),
            "budget_consumed_pct": f"{budget.budget_consumed_pct:.1%}",
        }

        if action == AdjustmentAction.REDUCE_SLICE_SIZE:
            # Reduce to 50% of original size
            recommendations["new_slice_factor"] = 0.5
        elif action == AdjustmentAction.SLOW_DOWN:
            # Double the time between slices
            recommendations["new_slice_factor"] = 0.7
            recommendations["delay_factor"] = 2.0
        elif action == AdjustmentAction.SWITCH_ALGORITHM:
            recommendations["suggested_algorithm"] = "POV"
            recommendations["new_slice_factor"] = 0.33
        elif action == AdjustmentAction.CANCEL:
            recommendations["reason"] = "Impact budget severely exceeded"

        return recommendations

    def get_per_slice_budget(
        self,
        budget: ImpactBudget,
        total_slices: int,
        slice_num: int,
    ) -> float:
        """Get the impact budget for a specific slice.

        Distributes remaining budget across remaining slices.

        Args:
            budget: ImpactBudget
            total_slices: Total planned slices
            slice_num: Current slice number (1-indexed)

        Returns:
            Budget for this slice in bps
        """
        remaining = total_slices - slice_num + 1
        if remaining <= 0:
            return 0.0

        return max(0.0, budget.remaining_budget_bps / remaining)
