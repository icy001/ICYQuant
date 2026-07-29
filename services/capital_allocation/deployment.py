from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DeploymentPhase(str, Enum):
    INITIATION = "INITIATION"
    SCALING = "SCALING"
    FULL = "FULL"
    REDUCING = "REDUCING"
    EXITING = "EXITING"


class DeploymentUrgency(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    WITHIN_DAY = "WITHIN_DAY"
    WITHIN_WEEK = "WITHIN_WEEK"
    OPPORTUNISTIC = "OPPORTUNISTIC"


class DeploymentMethod(str, Enum):
    SINGLE = "SINGLE"
    STAGED = "STAGED"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ADAPTIVE = "ADAPTIVE"


@dataclass
class CapitalPlan:
    plan_id: str
    symbol: str
    total_allocation: float
    current_deployed: float
    remaining: float
    phases: List[Dict[str, Any]] = field(default_factory=list)
    method: DeploymentMethod = DeploymentMethod.STAGED
    urgency: DeploymentUrgency = DeploymentUrgency.WITHIN_DAY
    constraints: List[str] = field(default_factory=list)
    max_single_tranche: float = 0.0
    cooldown_hours: float = 4.0


@dataclass
class DeploymentTranche:
    tranche_id: str
    symbol: str
    amount: float
    percentage: float
    conditions: List[str] = field(default_factory=list)
    status: str = "PENDING"


class CapitalDeploymentAgent:
    """Capital Deployment Agent - autonomously plans and executes capital deployment."""

    def __init__(self):
        self.plans: List[CapitalPlan] = []
        self.plan_count = 0

    def deploy(self, decision):
        """Generate a capital deployment plan from an investment decision.

        Args:
            decision: The investment decision (str, dict, or CapitalPlan).

        Returns:
            Dict containing the capital plan.
        """
        if isinstance(decision, CapitalPlan):
            return self._process_plan(decision)
        if isinstance(decision, dict):
            return self._deploy_from_dict(decision)
        return {"capital_plan": decision}

    def _process_plan(self, plan: CapitalPlan) -> dict:
        self.plans.append(plan)
        return self._to_dict(plan)

    def _deploy_from_dict(self, data: dict) -> dict:
        self.plan_count += 1

        decision_data = data.get("decision", data)
        symbol = decision_data.get("symbol", "UNKNOWN")
        decision_type = decision_data.get("decision", "BUY")
        conviction = decision_data.get("conviction_score", 50)
        position_pct = decision_data.get("position_size_pct", 0.05)

        total_allocation = self._calculate_allocation(decision_type, conviction, position_pct)
        method = self._select_method(decision_type, conviction, total_allocation)
        urgency = self._determine_urgency(decision_type)
        phases = self._plan_phases(symbol, total_allocation, method, conviction)
        constraints = self._derive_constraints(decision_data)

        plan = CapitalPlan(
            plan_id=f"CAP_{self.plan_count:04d}",
            symbol=symbol,
            total_allocation=round(total_allocation, 4),
            current_deployed=0.0,
            remaining=round(total_allocation, 4),
            phases=phases,
            method=method,
            urgency=urgency,
            constraints=constraints,
            max_single_tranche=round(total_allocation * 0.4, 4),
            cooldown_hours=self._calc_cooldown(conviction),
        )
        self.plans.append(plan)
        return self._to_dict(plan)

    def _calculate_allocation(self, decision_type: str, conviction: float, position_pct: float) -> float:
        if decision_type == "STRONG_BUY":
            return max(0.05, min(0.15, position_pct))
        if decision_type == "BUY":
            return max(0.02, min(0.08, position_pct))
        if decision_type == "HOLD":
            return max(0.0, min(0.02, position_pct))
        if decision_type in ("REDUCE", "SELL", "REJECT"):
            return 0.0
        return 0.0

    def _select_method(self, decision_type: str, conviction: float, allocation: float) -> DeploymentMethod:
        if allocation <= 0:
            return DeploymentMethod.SINGLE
        if conviction >= 85:
            return DeploymentMethod.STAGED
        if conviction >= 70:
            return DeploymentMethod.VWAP
        if conviction >= 50:
            return DeploymentMethod.TWAP
        return DeploymentMethod.ADAPTIVE

    def _determine_urgency(self, decision_type: str) -> DeploymentUrgency:
        mapping = {
            "STRONG_BUY": DeploymentUrgency.IMMEDIATE,
            "BUY": DeploymentUrgency.WITHIN_DAY,
            "SELL": DeploymentUrgency.IMMEDIATE,
            "STRONG_SELL": DeploymentUrgency.IMMEDIATE,
            "REDUCE": DeploymentUrgency.WITHIN_DAY,
            "HOLD": DeploymentUrgency.OPPORTUNISTIC,
            "REJECT": DeploymentUrgency.WITHIN_DAY,
        }
        return mapping.get(decision_type, DeploymentUrgency.WITHIN_WEEK)

    def _plan_phases(self, symbol: str, total: float, method: DeploymentMethod, conviction: float) -> List[dict]:
        if total <= 0:
            return [{
                "phase": 1, "tranche": "EXIT",
                "amount": abs(total), "percentage": 100.0,
                "trigger": "Execute immediately",
                "status": "PENDING",
            }]

        phases = []
        if method == DeploymentMethod.STAGED:
            splits = [(0.40, "Initial entry - conviction driven"),
                       (0.35, "Scale up - thesis confirmation"),
                       (0.25, "Full deployment - trend confirmed")]
        elif method == DeploymentMethod.VWAP:
            splits = [(0.50, "VWAP tranche 1 - morning session"),
                       (0.30, "VWAP tranche 2 - mid-day"),
                       (0.20, "VWAP tranche 3 - closing session")]
        elif method == DeploymentMethod.TWAP:
            splits = [(0.34, "TWAP tranche 1"), (0.33, "TWAP tranche 2"),
                       (0.33, "TWAP tranche 3")]
        else:
            splits = [(0.33, "Adaptive tranche 1 - price < VWAP"),
                       (0.33, "Adaptive tranche 2 - volume > avg"),
                       (0.34, "Adaptive tranche 3 - momentum confirmed")]

        for i, (pct, trigger) in enumerate(splits, 1):
            phases.append({
                "phase": i,
                "tranche": f"T{i}",
                "amount": round(total * pct, 4),
                "percentage": round(pct * 100, 1),
                "trigger": trigger,
                "status": "PENDING",
            })

        return phases

    def _derive_constraints(self, data: dict) -> List[str]:
        constraints = [
            "Maximum 40% in single tranche",
            "Minimum 4 hours between tranches",
            "Pause if adverse news during deployment",
        ]
        risk_controls = data.get("risk_controls", [])
        if risk_controls:
            constraints.extend(risk_controls[:2])
        return constraints

    def _calc_cooldown(self, conviction: float) -> float:
        if conviction >= 85:
            return 2.0
        if conviction >= 70:
            return 4.0
        if conviction >= 50:
            return 8.0
        return 24.0

    def _to_dict(self, plan: CapitalPlan) -> dict:
        return {
            "capital_plan": {
                "plan_id": plan.plan_id,
                "symbol": plan.symbol,
                "total_allocation": plan.total_allocation,
                "current_deployed": plan.current_deployed,
                "remaining": plan.remaining,
                "phases": plan.phases,
                "method": plan.method.value,
                "urgency": plan.urgency.value,
                "constraints": plan.constraints,
                "max_single_tranche": plan.max_single_tranche,
                "cooldown_hours": plan.cooldown_hours,
            }
        }

    def get_plans(self, symbol: Optional[str] = None) -> List[CapitalPlan]:
        """Get all capital plans, optionally filtered by symbol."""
        if symbol:
            return [p for p in self.plans if p.symbol == symbol]
        return list(self.plans)

    def get_deployed_capital(self) -> float:
        """Get total deployed capital across all plans."""
        return sum(p.current_deployed for p in self.plans)
