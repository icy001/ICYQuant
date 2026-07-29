from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AlgoType(str, Enum):
    VWAP = "VWAP"
    TWAP = "TWAP"
    POV = "POV"
    IMPLEMENTATION_SHORTFALL = "IMPLEMENTATION_SHORTFALL"
    ICEBERG = "ICEBERG"
    ADAPTIVE = "ADAPTIVE"
    DARK_SEEK = "DARK_SEEK"


@dataclass
class AlgoConfig:
    algo_type: AlgoType
    start_time: str = "09:30"
    end_time: str = "16:00"
    participation_rate: float = 0.05
    max_slippage_bps: float = 10.0
    display_size_pct: float = 0.10
    urgency: str = "NORMAL"
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlgoResult:
    algo_type: AlgoType
    total_quantity: int
    filled_quantity: int
    avg_price: float
    benchmark_price: float
    slippage_bps: float
    fill_rate: float
    duration_seconds: float
    status: str = "COMPLETED"


class ExecutionAlgorithmEngine:
    """Execution Algorithm Engine - supports institutional algo trading strategies."""

    def __init__(self):
        self.supported_algos = list(AlgoType)

    def execute(self, strategy):
        """Execute an algorithmic trading strategy.

        Args:
            strategy: Algorithm specification - can be AlgoConfig dataclass or dict/symbol.

        Returns:
            Dict containing execution result.
        """
        if isinstance(strategy, AlgoConfig):
            return self._execute_algo(strategy)
        return {"algorithm": strategy}

    def _execute_algo(self, config: AlgoConfig) -> dict:
        return {
            "algorithm": {
                "algo_type": config.algo_type.value,
                "start_time": config.start_time,
                "end_time": config.end_time,
                "participation_rate": config.participation_rate,
                "max_slippage_bps": config.max_slippage_bps,
                "display_size_pct": config.display_size_pct,
                "status": "ACTIVE",
            }
        }

    def get_vwap_schedule(self, total_qty: int, num_intervals: int) -> List[Dict[str, Any]]:
        """Generate VWAP execution schedule."""
        schedule = []
        base_qty = total_qty // num_intervals
        remainder = total_qty % num_intervals
        for i in range(num_intervals):
            qty = base_qty + (1 if i < remainder else 0)
            schedule.append({
                "interval": i + 1,
                "quantity": qty,
                "cumulative_pct": round((sum(s["quantity"] for s in schedule) + qty) / total_qty, 4),
            })
        return schedule

    def get_twap_schedule(self, total_qty: int, duration_minutes: int, interval_minutes: int = 5) -> List[Dict[str, Any]]:
        """Generate TWAP execution schedule."""
        num_intervals = max(1, duration_minutes // interval_minutes)
        return self.get_vwap_schedule(total_qty, num_intervals)

    def validate_algo_params(self, config: AlgoConfig) -> bool:
        """Validate algorithm configuration parameters."""
        if config.participation_rate <= 0 or config.participation_rate > 1:
            return False
        if config.max_slippage_bps <= 0:
            return False
        if config.display_size_pct <= 0 or config.display_size_pct > 1:
            return False
        return True
