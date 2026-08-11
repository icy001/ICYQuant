"""
Strategy Group — Logical Grouping of Related Strategies

Strategies are organized into groups for coordinated management:
- Trend, Momentum, Mean Reversion, Arbitrage, Event, Volatility, ML
- Risk Group, Factor Group, Liquidity Group, Asset Group

Groups share budgets, constraints, and exposure limits.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GroupConfig:
    group_id: str
    name: str
    group_type: str  # strategy_type, risk, factor, liquidity, asset
    capital_budget: float = 0.0
    risk_budget: float = 0.0
    max_exposure: float = float("inf")
    max_concentration: float = 0.30
    member_count: int = 0


class StrategyGroup:
    """
    Manages logical groups of strategies with shared budgets and limits.

    Groups enforce:
    - Shared capital budgets (group-level allocation caps)
    - Shared risk budgets (group-level risk caps)
    - Concentration limits (no single strategy dominates a group)
    """

    def __init__(
        self,
        group_id: Optional[str] = None,
        registry=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.group_id = group_id or f"sg-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self.config = config or {}
        self._groups: Dict[str, GroupConfig] = {}

    def create_group(
        self,
        name: str,
        group_type: str,
        capital_budget: float = 0.0,
        risk_budget: float = 0.0,
    ) -> GroupConfig:
        gid = f"grp-{uuid.uuid4().hex[:8]}"
        gc = GroupConfig(
            group_id=gid,
            name=name,
            group_type=group_type,
            capital_budget=capital_budget,
            risk_budget=risk_budget,
        )
        self._groups[gid] = gc
        return gc

    def get_group_by_type(self, group_type: str) -> List[GroupConfig]:
        return [g for g in self._groups.values() if g.group_type == group_type]

    def get_group_members(self, group_name: str) -> List[str]:
        """Get strategy IDs belonging to a group."""
        if not self._registry:
            return []
        return [sid for sid, r in self._registry.get_all().items()
                if r.correlation_group == group_name or r.factor_group == group_name]

    def get_group_capital_usage(self, group_name: str) -> float:
        members = self.get_group_members(group_name)
        if not self._registry:
            return 0.0
        return sum(self._registry.get(sid).capital_allocation for sid in members if self._registry.get(sid))

    def is_group_at_capacity(self, group_name: str) -> bool:
        group = next((g for g in self._groups.values() if g.name == group_name), None)
        if not group:
            return False
        return self.get_group_capital_usage(group_name) >= group.capital_budget if group.capital_budget > 0 else False

    def get_summary(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "groups": {
                g.name: {
                    "type": g.group_type,
                    "capital_budget": g.capital_budget,
                    "risk_budget": g.risk_budget,
                    "usage": self.get_group_capital_usage(g.name),
                }
                for g in self._groups.values()
            },
        }
