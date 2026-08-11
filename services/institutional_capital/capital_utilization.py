"""
Capital Utilization — Track How Much Capital Is Actually Deployed

Measures: deployed / allocated, allocated / total, idle capital detection.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UtilizationSnapshot:
    pool_id: str
    total: float = 0.0
    allocated: float = 0.0
    deployed: float = 0.0
    reserved: float = 0.0
    available: float = 0.0
    allocation_rate: float = 0.0
    deployment_rate: float = 0.0
    idle_capital: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapitalUtilization:
    """
    Tracks capital utilization metrics across the pool.

    Key metrics:
    - Allocation Rate = Allocated / Total
    - Deployment Rate = Deployed / Allocated
    - Idle Capital = Available + (Allocated - Deployed)
    """

    def __init__(
        self,
        util_id: Optional[str] = None,
        capital_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.util_id = util_id or f"cu-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self.config = config or {}
        self._snapshots: list = []
        self._strategy_utilization: Dict[str, float] = {}

    def take_snapshot(self) -> UtilizationSnapshot:
        if not self._capital_pool:
            return UtilizationSnapshot(pool_id=self.util_id)

        total = self._capital_pool.total_capital
        allocated = self._capital_pool.allocated_capital
        deployed = self._capital_pool.deployed_capital

        snap = UtilizationSnapshot(
            pool_id=self._capital_pool.pool_id,
            total=total,
            allocated=allocated,
            deployed=deployed,
            reserved=self._capital_pool.reserved_capital,
            available=self._capital_pool.available_capital,
            allocation_rate=allocated / total if total > 0 else 0.0,
            deployment_rate=deployed / allocated if allocated > 0 else 0.0,
            idle_capital=self._capital_pool.available_capital + (allocated - deployed),
        )
        self._snapshots.append(snap)
        return snap

    def update_strategy_utilization(self, strategy_id: str, utilized: float) -> None:
        self._strategy_utilization[strategy_id] = utilized

    def get_idle_capital(self) -> float:
        if self._snapshots:
            return self._snapshots[-1].idle_capital
        return 0.0

    def get_allocation_rate(self) -> float:
        if self._snapshots:
            return self._snapshots[-1].allocation_rate
        return 0.0

    def get_deployment_rate(self) -> float:
        if self._snapshots:
            return self._snapshots[-1].deployment_rate
        return 0.0

    def detect_underutilization(self, threshold: float = 0.50) -> Dict[str, float]:
        return {
            sid: util
            for sid, util in self._strategy_utilization.items()
            if util < threshold
        }

    def get_summary(self) -> Dict[str, Any]:
        latest = self._snapshots[-1] if self._snapshots else None
        return {
            "util_id": self.util_id,
            "allocation_rate": latest.allocation_rate if latest else 0,
            "deployment_rate": latest.deployment_rate if latest else 0,
            "idle_capital": latest.idle_capital if latest else 0,
            "underutilized_strategies": self.detect_underutilization(),
        }
