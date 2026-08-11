"""
Portfolio Capacity — Portfolio-Level Capital Constraints

Similar to strategy capacity but at the portfolio level.
Ensures individual portfolios don't exceed their market impact limits.
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioCapacityProfile:
    portfolio_id: str
    optimal_capital: float
    max_capacity: float
    current_capital: float = 0.0

    @property
    def utilization(self) -> float:
        if self.max_capacity <= 0:
            return 1.0
        return min(1.0, self.current_capital / self.max_capacity)

    @property
    def remaining(self) -> float:
        return max(0.0, self.max_capacity - self.current_capital)


class PortfolioCapacity:
    """Manages portfolio-level capital capacity constraints."""

    def __init__(
        self,
        capacity_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.capacity_id = capacity_id or f"pcap-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._profiles: Dict[str, PortfolioCapacityProfile] = {}

    def register(self, portfolio_id: str, optimal: float, max_cap: float) -> PortfolioCapacityProfile:
        profile = PortfolioCapacityProfile(
            portfolio_id=portfolio_id,
            optimal_capital=optimal,
            max_capacity=max_cap,
        )
        self._profiles[portfolio_id] = profile
        return profile

    def update(self, portfolio_id: str, current: float) -> None:
        profile = self._profiles.get(portfolio_id)
        if profile:
            profile.current_capital = current

    def can_accept(self, portfolio_id: str, amount: float) -> bool:
        profile = self._profiles.get(portfolio_id)
        if not profile:
            return True
        return profile.remaining >= amount

    def get(self, portfolio_id: str) -> Optional[PortfolioCapacityProfile]:
        return self._profiles.get(portfolio_id)

    def get_all(self) -> Dict[str, PortfolioCapacityProfile]:
        return dict(self._profiles)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "capacity_id": self.capacity_id,
            "portfolios": {
                pid: {
                    "optimal": p.optimal_capital,
                    "max": p.max_capacity,
                    "current": p.current_capital,
                    "utilization": p.utilization,
                }
                for pid, p in self._profiles.items()
            },
        }
