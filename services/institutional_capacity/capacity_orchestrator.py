"""
Capacity Orchestrator — Orchestrates capacity assessment across all strategies and assets.

Integrates with Multi-Strategy Portfolio (Part 1.2) to provide capacity-aware
portfolio construction, ensuring that target allocations respect real-world
market and execution capacity constraints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capacity_intelligence import CapacityIntelligence
from .capacity_manager import CapacityManager, CapacityProfile
from .capacity_controller import CapacityController, CapacityControlResult


@dataclass
class OrchestrationResult:
    """Result of capacity-aware orchestration over a portfolio."""

    orchestration_id: str = field(default_factory=lambda: f"CO-{uuid.uuid4().hex[:8]}")

    # Portfolio-level
    total_requested: float = 0.0
    total_approved: float = 0.0
    total_rejected: float = 0.0
    utilization: float = 0.0

    # Per-strategy results
    results: Dict[str, CapacityControlResult] = field(default_factory=dict)

    # Capacity efficiency
    capacity_efficiency: float = 0.0  # approved / requested

    # Issues
    constrained_strategies: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orchestration_id": self.orchestration_id,
            "total_requested": self.total_requested,
            "total_approved": self.total_approved,
            "total_rejected": self.total_rejected,
            "capacity_efficiency": self.capacity_efficiency,
            "constrained_strategies": self.constrained_strategies,
            "warnings": self.warnings,
        }


class CapacityOrchestrator:
    """Orchestrates capacity checks across the full portfolio."""

    def __init__(self):
        self._manager = CapacityManager()
        self._controller = CapacityController(self._manager._intelligence)
        self._results: List[OrchestrationResult] = []

    @property
    def manager(self) -> CapacityManager:
        return self._manager

    @property
    def controller(self) -> CapacityController:
        return self._controller

    def orchestrate(
        self,
        requests: List[Tuple[str, str, float, float, float, float]],
    ) -> OrchestrationResult:
        """Orchestrate capacity assessment for a batch of requests.

        Each request: (strategy_id, asset, requested_capital, adv, vol, spread_bps)
        """
        result = OrchestrationResult()

        for sid, asset, capital, adv, vol, spread in requests:
            control = self._controller.check(sid, asset, capital, adv, vol, spread)
            result.results[sid] = control
            result.total_requested += control.requested
            result.total_approved += control.approved
            result.total_rejected += (control.requested - control.approved)

            if control.action != CapacityControllerAction.PROCEED and control.action != CapacityControllerAction.REJECT:
                result.constrained_strategies.append(sid)

        result.capacity_efficiency = result.total_approved / max(result.total_requested, 1.0)

        if result.constrained_strategies:
            result.warnings.append(f"{len(result.constrained_strategies)} strategies constrained by capacity limits")

        self._results.append(result)
        return result

    def history(self) -> List[OrchestrationResult]:
        return list(self._results)

    def summary(self) -> Dict[str, Any]:
        return {
            "orchestrations": len(self._results),
            "capacity": self._manager.summary(),
            "controller": self._controller.summary(),
        }
