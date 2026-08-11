"""
Portfolio Pool — Multi-Portfolio Allocation Hub

Sits between Strategy Pool and Execution Engine. Each portfolio
receives capital from strategies and distributes to positions.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRecord:
    portfolio_id: str
    name: str = ""
    strategy_id: Optional[str] = None
    capital: float = 0.0
    risk_budget: float = 0.0
    capacity: float = float("inf")
    expected_return: float = 0.0
    expected_risk: float = 0.0
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PortfolioPool:
    """
    Registry of all portfolios receiving capital from strategies.
    Each portfolio is linked to a strategy and receives a capital allocation.
    """

    def __init__(
        self,
        pool_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.pool_id = pool_id or f"pp-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._portfolios: Dict[str, PortfolioRecord] = {}

    def register(self, record: PortfolioRecord) -> None:
        self._portfolios[record.portfolio_id] = record

    def get(self, portfolio_id: str) -> Optional[PortfolioRecord]:
        return self._portfolios.get(portfolio_id)

    def get_by_strategy(self, strategy_id: str) -> List[PortfolioRecord]:
        return [p for p in self._portfolios.values() if p.strategy_id == strategy_id and p.active]

    def get_total_capital(self) -> float:
        return sum(p.capital for p in self._portfolios.values() if p.active)

    def get_all(self) -> Dict[str, PortfolioRecord]:
        return dict(self._portfolios)

    def get_allocations(self) -> Dict[str, float]:
        return {k: v.capital for k, v in self._portfolios.items() if v.active}

    def get_summary(self) -> Dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "portfolio_count": len(self._portfolios),
            "total_capital": self.get_total_capital(),
            "portfolios": {
                pid: {"name": p.name, "strategy": p.strategy_id, "capital": p.capital}
                for pid, p in self._portfolios.items() if p.active
            },
        }
