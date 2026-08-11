"""
Capital Conflict Resolver — Resolve Capital Allocation Conflicts

When strategies compete for limited capital, resolve conflicts by:
1. Priority score ranking
2. Marginal efficiency comparison
3. Continuous optimization if multiple strategies are close
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConflictResolution:
    resolution_id: str
    strategy_id: str
    requested: float
    allocated: float
    resolution: str  # FULL, PARTIAL, REJECTED, DEFERRED
    reason: str


class CapitalConflictResolver:
    """
    Resolves capital conflicts between competing strategies.

    Resolution strategies:
    - Priority-based: highest priority gets capital first
    - Efficiency-based: best marginal efficiency wins
    - Hybrid: priority × efficiency composite ranking
    """

    def __init__(
        self,
        resolver_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.resolver_id = resolver_id or f"ccr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._strategy = self.config.get("resolution_strategy", "priority")
        self._resolutions: List[ConflictResolution] = []

    def resolve(
        self,
        requests: Dict[str, float],
        priorities: Dict[str, float],
        available_capital: float,
        marginal_efficiencies: Optional[Dict[str, float]] = None,
    ) -> List[ConflictResolution]:
        """Resolve capital conflicts and produce allocation plan."""
        marginal_efficiencies = marginal_efficiencies or {}
        self._resolutions = []

        # Build composite ranking
        ranked = self._rank(requests, priorities, marginal_efficiencies)
        remaining = available_capital

        for strategy_id, _ in ranked:
            requested = requests[strategy_id]
            alloc = min(requested, remaining)
            remaining -= alloc

            if alloc >= requested * 0.99:
                res = "FULL"
                reason = "Fully allocated"
            elif alloc > 0:
                res = "PARTIAL"
                reason = f"Allocated {alloc}/{requested}"
            elif remaining <= 0:
                res = "REJECTED"
                reason = "No capital available"
            else:
                res = "DEFERRED"
                reason = "Deferred to next cycle"

            self._resolutions.append(ConflictResolution(
                resolution_id=f"cr-{uuid.uuid4().hex[:8]}",
                strategy_id=strategy_id,
                requested=requested,
                allocated=alloc,
                resolution=res,
                reason=reason,
            ))

        return self._resolutions

    def _rank(
        self,
        requests: Dict[str, float],
        priorities: Dict[str, float],
        marginal_efficiencies: Dict[str, float],
    ) -> List[Tuple[str, float]]:
        """Build composite ranking of strategies."""
        scores = {}
        for sid in requests:
            if self._strategy == "efficiency":
                scores[sid] = marginal_efficiencies.get(sid, 0)
            elif self._strategy == "hybrid":
                scores[sid] = priorities.get(sid, 0) * marginal_efficiencies.get(sid, 1.0)
            else:  # priority
                scores[sid] = priorities.get(sid, 0)
        return sorted(scores.items(), key=lambda x: -x[1])

    def get_rejected(self) -> List[ConflictResolution]:
        return [r for r in self._resolutions if r.resolution == "REJECTED"]
