"""
Strategy Registry — Unified Strategy Catalog for Portfolio Orchestration

Maintains complete strategy metadata for the portfolio orchestrator:
- strategy_id, version, type, capital, risk budget
- priority, capacity, status
- correlation group, factor group, liquidity group

Answers: who is trading, with how much capital, what risk, what correlations.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RegistryRecord:
    strategy_id: str
    version: str = "1.0.0"
    strategy_type: str = ""
    capital_allocation: float = 0.0
    risk_budget: float = 0.0
    priority: int = 50
    capacity: float = float("inf")
    correlation_group: str = ""
    factor_group: str = ""
    liquidity_group: str = ""
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyRegistry:
    """
    Central registry of all strategies in the portfolio.

    Tracks strategy lifecycle: PENDING → ACTIVE → DEGRADED → QUARANTINED → RETIRED.
    Groups strategies by correlation, factor, and liquidity profiles.
    """

    def __init__(
        self,
        registry_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.registry_id = registry_id or f"sr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._strategies: Dict[str, RegistryRecord] = {}

    def register(self, record: RegistryRecord) -> None:
        self._strategies[record.strategy_id] = record

    def get(self, strategy_id: str) -> Optional[RegistryRecord]:
        return self._strategies.get(strategy_id)

    def get_all(self) -> Dict[str, RegistryRecord]:
        return dict(self._strategies)

    def get_active(self) -> Dict[str, RegistryRecord]:
        return {k: v for k, v in self._strategies.items() if v.status == "ACTIVE"}

    def get_by_group(self, group_type: str, group_name: str) -> List[RegistryRecord]:
        attr = f"{group_type}_group"
        return [v for v in self._strategies.values() if getattr(v, attr, "") == group_name]

    def get_by_correlation_group(self, group_name: str) -> List[RegistryRecord]:
        return self.get_by_group("correlation", group_name)

    def get_by_factor_group(self, group_name: str) -> List[RegistryRecord]:
        return self.get_by_group("factor", group_name)

    def get_by_liquidity_group(self, group_name: str) -> List[RegistryRecord]:
        return self.get_by_group("liquidity", group_name)

    def update_status(self, strategy_id: str, status: str) -> None:
        rec = self._strategies.get(strategy_id)
        if rec:
            rec.status = status
            rec.updated_at = datetime.utcnow()

    def get_total_capital(self) -> float:
        return sum(r.capital_allocation for r in self.get_active().values())

    def get_total_risk_budget(self) -> float:
        return sum(r.risk_budget for r in self.get_active().values())

    def get_correlation_groups(self) -> Set[str]:
        return {r.correlation_group for r in self._strategies.values() if r.correlation_group}

    def get_summary(self) -> Dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "total": len(self._strategies),
            "active": len(self.get_active()),
            "by_status": {s: sum(1 for r in self._strategies.values() if r.status == s) for s in
                          set(r.status for r in self._strategies.values())},
            "total_capital": self.get_total_capital(),
        }
