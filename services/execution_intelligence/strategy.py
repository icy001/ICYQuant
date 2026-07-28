"""Execution Strategy Engine – select and configure execution algorithms."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .order import ExecutionOrder
from .plan import ExecutionPlan, Slice


@dataclass
class StrategyConfig:
    """Configuration for an execution strategy."""

    name: str  # "market", "VWAP", "TWAP", "POV", "adaptive"
    description: str = ""
    min_duration_seconds: int = 60
    max_duration_seconds: int = 3600
    recommended_for: List[str] = field(default_factory=list)
    min_participation: float = 0.0
    max_participation: float = 1.0


class ExecutionStrategyEngine:
    """Selects the optimal execution strategy based on order characteristics.

    Supports:
    - MARKET: immediate execution at best available price
    - VWAP: volume-weighted average price over duration
    - TWAP: time-weighted average price over duration
    - POV: percentage-of-volume, follow market volume
    - ADAPTIVE: AI-driven dynamic adjustment
    """

    STRATEGIES = {
        "market": StrategyConfig(
            name="market",
            description="Immediate execution at best available price",
            min_duration_seconds=0,
            max_duration_seconds=60,
            recommended_for=["urgent", "small_orders", "liquid"],
        ),
        "VWAP": StrategyConfig(
            name="VWAP",
            description="Volume-weighted average price execution",
            min_duration_seconds=300,
            max_duration_seconds=3600,
            recommended_for=["medium", "liquid", "low_impact"],
            min_participation=0.05,
            max_participation=0.15,
        ),
        "TWAP": StrategyConfig(
            name="TWAP",
            description="Time-weighted average price execution",
            min_duration_seconds=300,
            max_duration_seconds=3600,
            recommended_for=["medium", "illiquid", "steady"],
            min_participation=0.03,
            max_participation=0.10,
        ),
        "POV": StrategyConfig(
            name="POV",
            description="Percentage-of-volume: follow market participation",
            min_duration_seconds=120,
            max_duration_seconds=1800,
            recommended_for=["large", "liquid", "active"],
            min_participation=0.10,
            max_participation=0.25,
        ),
        "adaptive": StrategyConfig(
            name="adaptive",
            description="AI-driven dynamic execution that adjusts to conditions",
            min_duration_seconds=300,
            max_duration_seconds=7200,
            recommended_for=["complex", "volatile", "large"],
        ),
    }

    def __init__(self):
        pass

    def choose(self, urgency: str = "normal",
               quantity: int = 1000,
               avg_daily_volume: int = 1_000_000) -> str:
        """Select the best execution strategy.

        Args:
            urgency: "low", "normal", "high", "critical"
            quantity: Order size in shares.
            avg_daily_volume: Average daily volume.
        """
        participation = quantity / max(avg_daily_volume, 1)

        # Critical urgency → immediate market order
        if urgency == "critical":
            return "market"

        # High urgency → market for small, POV for large
        if urgency == "high":
            return "market" if participation < 0.05 else "POV"

        # Low urgency → TWAP for steady execution
        if urgency == "low":
            return "TWAP"

        # Normal urgency → VWAP is the default for medium/large
        if participation < 0.01:
            return "market"  # very small, just execute
        elif participation < 0.10:
            return "VWAP"
        elif participation < 0.25:
            return "POV"
        else:
            return "adaptive"  # very large, need smart execution

    def choose_for_order(self, order: ExecutionOrder,
                         avg_daily_volume: int = 1_000_000) -> str:
        """Select strategy for an ExecutionOrder."""
        return self.choose(
            urgency=order.urgency,
            quantity=order.quantity,
            avg_daily_volume=avg_daily_volume,
        )

    def create_plan(
        self,
        order: ExecutionOrder,
        strategy: Optional[str] = None,
        duration: Optional[int] = None,
        avg_daily_volume: int = 1_000_000,
        slices: Optional[int] = None,
    ) -> ExecutionPlan:
        """Generate a full execution plan for an order.

        Args:
            order: The order to plan execution for.
            strategy: Override auto-selected strategy.
            duration: Override duration in seconds.
            avg_daily_volume: Average daily volume for slicing.
            slices: Override number of slices.
        """
        strategy_name = strategy or self.choose_for_order(order, avg_daily_volume)

        # Determine duration
        if duration is not None:
            exec_duration = duration
        else:
            config = self.STRATEGIES.get(strategy_name, StrategyConfig(name=strategy_name))
            exec_duration = config.min_duration_seconds

        plan = ExecutionPlan(
            order_id=f"ORD-{order.symbol}-{order.side}",
            symbol=order.symbol,
            side=order.side,
            strategy=strategy_name,
            duration=exec_duration,
            urgency=order.urgency,
            total_quantity=order.quantity,
        )

        # Determine slice count
        if slices is not None:
            n_slices = slices
        elif strategy_name in ("market",):
            n_slices = 1
        elif strategy_name == "TWAP":
            n_slices = max(1, exec_duration // 60)
        elif strategy_name == "VWAP":
            n_slices = max(1, exec_duration // 120)
        elif strategy_name == "POV":
            n_slices = max(1, exec_duration // 90)
        else:
            n_slices = max(1, exec_duration // 60)

        # Create slices (guard against zero slices)
        if n_slices <= 0:
            n_slices = 1
        base_qty = order.quantity // n_slices
        remainder = order.quantity - base_qty * n_slices

        now = datetime.now()
        slice_interval = exec_duration / n_slices if n_slices > 0 else 0

        for i in range(n_slices):
            qty = base_qty + (1 if i < remainder else 0)
            if qty <= 0:
                continue
            s = Slice(
                slice_id=i + 1,
                quantity=qty,
                strategy=strategy_name,
                start_time=now + timedelta(seconds=i * slice_interval),
                end_time=now + timedelta(seconds=(i + 1) * slice_interval),
            )
            plan.slices.append(s)

        return plan

    def list_strategies(self) -> List[dict]:
        """Return all available strategies with metadata."""
        return [
            {
                "name": name,
                "description": cfg.description,
                "min_duration_seconds": cfg.min_duration_seconds,
                "max_duration_seconds": cfg.max_duration_seconds,
                "recommended_for": cfg.recommended_for,
            }
            for name, cfg in self.STRATEGIES.items()
        ]

    def get_strategy_config(self, name: str) -> Optional[StrategyConfig]:
        """Get configuration for a specific strategy."""
        return self.STRATEGIES.get(name)
