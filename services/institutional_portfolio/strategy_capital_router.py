"""
Strategy Capital Router — Route Capital from Pool to Strategies

Distributes available capital to strategies based on coordinator
allocation results. Bridges CapitalIntelligence with portfolio layer.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapitalRoute:
    strategy_id: str
    amount: float
    source: str  # available, reallocation, reserve
    status: str = "PENDING"


class StrategyCapitalRouter:
    """
    Routes capital from CapitalPool to individual strategies.

    Implements the allocation decisions from CapitalCoordinator.
    """

    def __init__(
        self,
        router_id: Optional[str] = None,
        capital_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.router_id = router_id or f"scr-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self.config = config or {}
        self._routes: Dict[str, List[CapitalRoute]] = {}

    def route(self, allocations: Dict[str, float]) -> List[CapitalRoute]:
        """Execute capital routing from pool to strategies."""
        routes = []
        for sid, amount in allocations.items():
            route = CapitalRoute(
                strategy_id=sid,
                amount=amount,
                source="available",
                status="ROUTED" if amount > 0 else "REJECTED",
            )
            routes.append(route)
            self._routes.setdefault(sid, []).append(route)

            if self._capital_pool and amount > 0:
                self._capital_pool.allocate(amount, sid)

        return routes

    def get_strategy_routes(self, strategy_id: str) -> List[CapitalRoute]:
        return self._routes.get(strategy_id, [])

    def get_total_routed(self) -> float:
        all_routes = [r for routes in self._routes.values() for r in routes if r.status == "ROUTED"]
        return sum(r.amount for r in all_routes)
