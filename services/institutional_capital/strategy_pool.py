"""
Strategy Pool — Central Registry of All Production Strategies

The StrategyPool holds every strategy with its:
- capital_allocation, risk_budget, capacity, utilization
- performance, drawdown, correlation
- state, lifecycle, autonomy level

It is the entry point for the Allocation Optimizer to query
strategy attributes needed for capital allocation decisions.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class StrategyPoolState(str, Enum):
    ACTIVE = "ACTIVE"
    RECONCILING = "RECONCILING"
    CLOSED = "CLOSED"


@dataclass
class StrategyRecord:
    strategy_id: str
    name: str = ""
    strategy_type: str = ""
    status: str = "ACTIVE"
    capital_allocation: float = 0.0
    risk_budget: float = 0.0
    capacity: float = float("inf")
    utilization: float = 0.0
    performance: float = 0.0
    drawdown: float = 0.0
    correlation: float = 0.0
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe: float = 0.0
    autonomy_level: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyPool:
    """
    Central registry and query layer for all production strategies.

    Provides the Allocation Optimizer with strategy attributes to
    compute optimal capital allocation.
    """

    def __init__(
        self,
        pool_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.pool_id = pool_id or f"sp-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self.state = StrategyPoolState.ACTIVE
        self._strategies: Dict[str, StrategyRecord] = {}

    def register(self, record: StrategyRecord) -> None:
        self._strategies[record.strategy_id] = record
        logger.info(f"Strategy registered: {record.strategy_id}")

    def update(
        self, strategy_id: str, **kwargs
    ) -> Optional[StrategyRecord]:
        rec = self._strategies.get(strategy_id)
        if not rec:
            return None
        for k, v in kwargs.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        rec.updated_at = datetime.utcnow()
        return rec

    def get(self, strategy_id: str) -> Optional[StrategyRecord]:
        return self._strategies.get(strategy_id)

    def get_all(self) -> Dict[str, StrategyRecord]:
        return dict(self._strategies)

    def get_active(self) -> Dict[str, StrategyRecord]:
        return {k: v for k, v in self._strategies.items() if v.status == "ACTIVE"}

    def get_allocations(self) -> Dict[str, float]:
        return {k: v.capital_allocation for k, v in self._strategies.items()}

    def get_capacities(self) -> Dict[str, float]:
        return {k: v.capacity for k, v in self._strategies.items()}

    def get_expected_returns(self) -> Dict[str, float]:
        return {k: v.expected_return for k, v in self._strategies.items()}

    def get_expected_risks(self) -> Dict[str, float]:
        return {k: v.expected_risk for k, v in self._strategies.items()}

    def get_exposure_matrix(self) -> Dict[str, Dict[str, float]]:
        """Return strategy × strategy correlation/exposure matrix."""
        ids = list(self._strategies.keys())
        matrix = {}
        for s1 in ids:
            matrix[s1] = {}
            for s2 in ids:
                if s1 == s2:
                    matrix[s1][s2] = 1.0
                else:
                    matrix[s1][s2] = self._strategies[s1].correlation
        return matrix

    def detect_overlaps(self) -> List[Dict[str, Any]]:
        """Detect strategy clusters with high correlation."""
        clusters = []
        ids = list(self._strategies.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                s1, s2 = ids[i], ids[j]
                corr = self._strategies[s1].correlation
                if abs(corr) > 0.70:
                    clusters.append({
                        "strategy_a": s1,
                        "strategy_b": s2,
                        "correlation": corr,
                        "severity": "HIGH" if abs(corr) > 0.85 else "MEDIUM",
                    })
        return clusters

    def get_count(self) -> int:
        return len(self._strategies)

    def get_total_allocation(self) -> float:
        return sum(v.capital_allocation for v in self._strategies.values())

    def get_summary(self) -> Dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "strategy_count": self.get_count(),
            "active_count": len(self.get_active()),
            "total_allocation": self.get_total_allocation(),
            "allocations": self.get_allocations(),
            "capacities": self.get_capacities(),
        }
