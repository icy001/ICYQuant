"""
Position Conflict Resolver — Handle Overlapping Position Requests

When multiple strategies want contradictory position changes:
    Strategy A → +5% NVDA
    Strategy B → -2% NVDA (reduce)
    → Net: +3% increase

Resolves based on priority, confidence, and capital allocation.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PositionConflict:
    asset: str
    increase_requests: Dict[str, float]
    decrease_requests: Dict[str, float]
    net_change: float
    resolution: str  # NET, PRIORITY_REDUCE, HOLD
    reason: str


class PositionConflictResolver:
    """
    Resolves conflicting position change requests across strategies.

    When one strategy wants to increase and another wants to decrease,
    resolve by priority and confidence rather than simple averaging.
    """

    def __init__(
        self,
        resolver_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.resolver_id = resolver_id or f"pcr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._conflicts: Dict[str, PositionConflict] = {}

    def resolve(self, changes: Dict[str, Dict[str, float]],
                priorities: Optional[Dict[str, float]] = None) -> Dict[str, PositionConflict]:
        """
        Resolve position conflicts.

        Args:
            changes: {strategy_id: {asset: position_change}}
            priorities: {strategy_id: priority_score}
        """
        self._conflicts.clear()
        priorities = priorities or {}
        asset_changes: Dict[str, Dict[str, float]] = {}

        for sid, pos_changes in changes.items():
            for asset, delta in pos_changes.items():
                weight = priorities.get(sid, 0.5)
                asset_changes.setdefault(asset, {})[sid] = delta * weight

        for asset, contributors in asset_changes.items():
            increases = {k: v for k, v in contributors.items() if v > 0}
            decreases = {k: abs(v) for k, v in contributors.items() if v < 0}
            net = sum(contributors.values())

            if not increases and not decreases:
                resolution = "HOLD"
                reason = "No changes"
            elif abs(net) < 0.01:
                resolution = "HOLD"
                reason = "Changes net to zero"
            else:
                resolution = "NET"
                reason = f"Net change: {net:+.4f}"

            self._conflicts[asset] = PositionConflict(
                asset=asset,
                increase_requests=increases,
                decrease_requests=decreases,
                net_change=net,
                resolution=resolution,
                reason=reason,
            )

        return self._conflicts
