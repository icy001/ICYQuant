"""
Rebalance Engine — Dynamic Portfolio Rebalancing Orchestrator

Orchestrates the complete rebalancing pipeline:
    1. Detect → drift, risk drift, regime change, performance triggers
    2. Evaluate → expected benefit vs cost
    3. Optimize → compute optimal adjustment path
    4. Execute → through TurnoverController and DriftController
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RebalanceAction(str, Enum):
    REBALANCE = "REBALANCE"
    SKIP = "SKIP"
    SCHEDULE = "SCHEDULE"
    PARTIAL = "PARTIAL"


@dataclass
class RebalancePlan:
    plan_id: str
    action: RebalanceAction = RebalanceAction.SKIP
    target_weights: Dict[str, float] = field(default_factory=dict)
    current_weights: Dict[str, float] = field(default_factory=dict)
    deltas: Dict[str, float] = field(default_factory=dict)
    expected_cost: float = 0.0
    expected_benefit: float = 0.0
    net_benefit: float = 0.0
    total_turnover: float = 0.0
    triggers: List[str] = field(default_factory=list)


class RebalanceEngine:
    """
    Dynamic portfolio rebalancing engine.

    Decides when and how to rebalance based on:
    - Weight drift
    - Risk drift
    - Factor drift
    - Strategy performance changes
    - Market regime shifts
    - Capital changes
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        trigger=None,
        scheduler=None,
        optimizer=None,
        turnover_controller=None,
        drift_controller=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"re-{uuid.uuid4().hex[:12]}"
        self._trigger = trigger
        self._scheduler = scheduler
        self._optimizer = optimizer
        self._turnover = turnover_controller
        self._drift = drift_controller
        self.config = config or {}
        self._plans: List[RebalancePlan] = []

    def should_rebalance(self) -> bool:
        if self._trigger:
            return self._trigger.check()
        return False

    def execute(self) -> RebalancePlan:
        """Execute a complete rebalancing cycle."""
        plan = RebalancePlan(plan_id=f"rp-{uuid.uuid4().hex[:8]}")

        # Collect triggers
        if self._trigger:
            triggers = self._trigger.get_active_triggers()
            plan.triggers = triggers

        if not plan.triggers:
            plan.action = RebalanceAction.SKIP
            self._plans.append(plan)
            return plan

        # Compute target weights
        if self._optimizer:
            target = self._optimizer.compute_rebalance()
            plan.target_weights = target

        if self._drift:
            plan.current_weights = self._drift.get_current_weights()
            plan.deltas = self._drift.compute_deltas(plan.target_weights)

        # Check if rebalance is worthwhile
        if self._turnover:
            cost_benefit = self._turnover.evaluate(plan.deltas)
            plan.expected_cost = cost_benefit.get("cost", 0)
            plan.expected_benefit = cost_benefit.get("benefit", 0)
            plan.net_benefit = plan.expected_benefit - plan.expected_cost
            plan.total_turnover = cost_benefit.get("turnover", 0)

            if plan.net_benefit <= 0:
                plan.action = RebalanceAction.SKIP
            else:
                plan.action = RebalanceAction.REBALANCE
        else:
            plan.action = RebalanceAction.REBALANCE

        self._plans.append(plan)
        return plan

    def get_last_plan(self) -> Optional[RebalancePlan]:
        return self._plans[-1] if self._plans else None
