"""Strategy Coordinator – coordinates resources and permissions across strategies."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StrategyStatus(Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"


@dataclass
class Strategy:
    name: str
    priority: int = 0
    status: StrategyStatus = StrategyStatus.ACTIVE
    allocation_pct: float = 0.0
    max_exposure: float = 0.0
    current_exposure: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyCoordinator:
    """Coordinates resources, risk, and permissions across multiple strategies.

    Handles priority-based allocation, conflict resolution, and status management.
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, Strategy] = {}

    def register(self, strategy: Strategy) -> None:
        self._strategies[strategy.name] = strategy

    def unregister(self, name: str) -> Optional[Strategy]:
        return self._strategies.pop(name, None)

    def get(self, name: str) -> Optional[Strategy]:
        return self._strategies.get(name)

    def allocate(self, strategies: List[Strategy]) -> List[Strategy]:
        """Sort strategies by priority (highest first).

        Args:
            strategies: list of Strategy objects.

        Returns:
            Sorted list, highest priority first.
        """
        return sorted(strategies, key=lambda x: x.priority, reverse=True)

    def allocate_resources(self, total_capital: float) -> Dict[str, float]:
        """Allocate capital to active strategies by priority-weighted share.

        Only ACTIVE strategies receive allocation.
        """
        active = [s for s in self._strategies.values() if s.status == StrategyStatus.ACTIVE]
        if not active:
            return {}

        total_priority = sum(s.priority for s in active)
        if total_priority == 0:
            return {}

        allocation: Dict[str, float] = {}
        for s in active:
            allocation[s.name] = round(total_capital * s.priority / total_priority, 2)

        return allocation

    def set_status(self, name: str, status: StrategyStatus) -> bool:
        """Update a strategy's status."""
        s = self._strategies.get(name)
        if s is None:
            return False
        s.status = status
        return True

    def pause_all(self) -> None:
        """Pause all strategies."""
        for s in self._strategies.values():
            if s.status == StrategyStatus.ACTIVE:
                s.status = StrategyStatus.PAUSED

    def resume_all(self) -> None:
        """Resume all paused strategies."""
        for s in self._strategies.values():
            if s.status == StrategyStatus.PAUSED:
                s.status = StrategyStatus.ACTIVE

    def get_active_strategies(self) -> List[Strategy]:
        return [s for s in self._strategies.values() if s.status == StrategyStatus.ACTIVE]

    def get_status_summary(self) -> Dict[str, int]:
        """Count strategies by status."""
        summary: Dict[str, int] = {}
        for s in self._strategies.values():
            summary[s.status.value] = summary.get(s.status.value, 0) + 1
        return summary

    @property
    def strategy_count(self) -> int:
        return len(self._strategies)
