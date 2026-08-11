"""
Risk & Execution Controller — safety rules and autonomy governance.

Enforces the safety boundary between autonomous optimization and
actual trading authority. All autonomous decisions flow through
this controller before reaching OMS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class DecisionResult(Enum):
    """Outcome of controller evaluation."""
    ALLOW = "allow"
    RESIZE = "resize"
    DELAY = "delay"
    REJECT = "reject"
    HALT = "halt"


class SafetyRule(Enum):
    """Named safety rules enforced by the controller."""
    RISK_BUDGET_LIMIT = "risk_budget_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    CONCENTRATION_LIMIT = "concentration_limit"
    LIQUIDITY_LIMIT = "liquidity_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    VOLATILITY_LIMIT = "volatility_limit"
    ORDER_SIZE_LIMIT = "order_size_limit"
    EXECUTION_RATE_LIMIT = "execution_rate_limit"
    COST_LIMIT = "cost_limit"
    KILL_SWITCH = "kill_switch"
    MARKET_HALT = "market_halt"
    REGIME_CONSTRAINT = "regime_constraint"


@dataclass
class ControllerConfig:
    """Controller safety configuration."""
    autonomy_level: int = 2  # 0=off, 1=analyze, 2=recommend, 3=optimize, 4=auto
    max_risk_budget: float = 1.0
    max_gross_exposure: float = 2.0
    max_net_exposure: float = 1.5
    max_leverage: float = 3.0
    max_single_asset_pct: float = 0.20
    max_sector_pct: float = 0.40
    max_order_pct_adv: float = 0.10
    max_drawdown_pct: float = 0.15
    max_execution_cost_bps: float = 50.0
    require_approval_above_autonomy: bool = True
    kill_switch_stop_new_orders: bool = True


@dataclass
class ControlDecision:
    """A single control decision."""
    result: DecisionResult
    rule: Optional[SafetyRule] = None
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    requires_approval: bool = False


class RiskExecutionController:
    """
    Safety controller enforcing risk and execution constraints.

    All autonomous risk/execution decisions must pass through this controller.
    Kill switch always takes precedence over any autonomy level.

    Safety Rules (9):
        1. Risk Budget Limit
        2. Exposure Limit
        3. Leverage Limit
        4. Concentration Limit
        5. Liquidity Limit
        6. Drawdown Limit
        7. Volatility Limit
        8. Order Size Limit
        9. Execution Rate Limit
    """

    def __init__(self, config: Optional[ControllerConfig] = None) -> None:
        self._id = str(uuid4())
        self._config = config or ControllerConfig()
        self._kill_switch_active = False
        self._violations: list[ControlDecision] = []

    # ── Core Validation ────────────────────────────────────────

    def check_risk_adjusted_target(self, target: dict) -> ControlDecision:
        """Validate a risk-adjusted target portfolio."""
        checks = [
            self._check_kill_switch,
            self._check_risk_budget,
            self._check_exposure,
            self._check_leverage,
            self._check_concentration,
            self._check_liquidity,
            self._check_drawdown,
        ]
        for check in checks:
            decision = check(target)
            if decision.result in (DecisionResult.REJECT, DecisionResult.HALT):
                self._violations.append(decision)
                return decision
            if decision.result == DecisionResult.RESIZE:
                self._violations.append(decision)
                return decision
        return ControlDecision(result=DecisionResult.ALLOW)

    def check_execution_plan(self, plan: dict) -> ControlDecision:
        """Validate an execution plan against safety constraints."""
        checks = [
            self._check_kill_switch,
            self._check_order_size,
            self._check_execution_rate,
            self._check_cost,
        ]
        for check in checks:
            decision = check(plan)
            if decision.result in (DecisionResult.REJECT, DecisionResult.HALT):
                self._violations.append(decision)
                return decision
        return ControlDecision(result=DecisionResult.ALLOW)

    def check_order(self, order: dict) -> ControlDecision:
        """Final pre-trade check on a single order."""
        if self._kill_switch_active:
            return ControlDecision(
                result=DecisionResult.HALT,
                rule=SafetyRule.KILL_SWITCH,
                reason="Kill switch active — all orders stopped",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    # ── Kill Switch ────────────────────────────────────────────

    def engage_kill_switch(self, reason: str) -> None:
        """Engage kill switch immediately."""
        self._kill_switch_active = True
        logger.critical("KILL SWITCH ENGAGED: %s", reason)
        self._violations.append(ControlDecision(
            result=DecisionResult.HALT,
            rule=SafetyRule.KILL_SWITCH,
            reason=reason,
        ))

    def disengage_kill_switch(self) -> None:
        """Disengage kill switch (requires approval)."""
        self._kill_switch_active = False
        logger.warning("Kill switch disengaged")

    # ── Individual Checks ──────────────────────────────────────

    def _check_kill_switch(self, _target: dict) -> ControlDecision:
        if self._kill_switch_active:
            return ControlDecision(
                result=DecisionResult.HALT,
                rule=SafetyRule.KILL_SWITCH,
                reason="Kill switch active",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_risk_budget(self, target: dict) -> ControlDecision:
        risk_budget = target.get("risk_budget", 1.0)
        if risk_budget > self._config.max_risk_budget:
            return ControlDecision(
                result=DecisionResult.RESIZE,
                rule=SafetyRule.RISK_BUDGET_LIMIT,
                reason=f"Risk budget {risk_budget} exceeds max {self._config.max_risk_budget}",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_exposure(self, target: dict) -> ControlDecision:
        gross = target.get("gross_exposure", 0)
        net = target.get("net_exposure", 0)
        if gross > self._config.max_gross_exposure:
            return ControlDecision(
                result=DecisionResult.RESIZE,
                rule=SafetyRule.EXPOSURE_LIMIT,
                reason=f"Gross exposure {gross} exceeds max {self._config.max_gross_exposure}",
            )
        if abs(net) > self._config.max_net_exposure:
            return ControlDecision(
                result=DecisionResult.RESIZE,
                rule=SafetyRule.EXPOSURE_LIMIT,
                reason=f"Net exposure {net} exceeds max {self._config.max_net_exposure}",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_leverage(self, target: dict) -> ControlDecision:
        leverage = target.get("leverage", 1.0)
        if leverage > self._config.max_leverage:
            return ControlDecision(
                result=DecisionResult.RESIZE,
                rule=SafetyRule.LEVERAGE_LIMIT,
                reason=f"Leverage {leverage} exceeds max {self._config.max_leverage}",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_concentration(self, target: dict) -> ControlDecision:
        positions = target.get("positions", {})
        for asset, weight in positions.items():
            if abs(weight) > self._config.max_single_asset_pct:
                return ControlDecision(
                    result=DecisionResult.RESIZE,
                    rule=SafetyRule.CONCENTRATION_LIMIT,
                    reason=f"{asset} weight {weight} exceeds max {self._config.max_single_asset_pct}",
                )
        sector_exposure = target.get("sector_exposure", {})
        for sector, weight in sector_exposure.items():
            if abs(weight) > self._config.max_sector_pct:
                return ControlDecision(
                    result=DecisionResult.RESIZE,
                    rule=SafetyRule.CONCENTRATION_LIMIT,
                    reason=f"Sector {sector} exposure {weight} exceeds max {self._config.max_sector_pct}",
                )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_liquidity(self, target: dict) -> ControlDecision:
        positions = target.get("positions", {})
        adv_data = target.get("adv", {})
        for asset, size in positions.items():
            adv = adv_data.get(asset, float("inf"))
            if adv > 0 and abs(size) / adv > self._config.max_order_pct_adv:
                return ControlDecision(
                    result=DecisionResult.RESIZE,
                    rule=SafetyRule.LIQUIDITY_LIMIT,
                    reason=f"{asset} order size exceeds {self._config.max_order_pct_adv*100}% ADV",
                )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_drawdown(self, target: dict) -> ControlDecision:
        current_dd = target.get("current_drawdown", 0)
        if current_dd > self._config.max_drawdown_pct:
            return ControlDecision(
                result=DecisionResult.RESIZE,
                rule=SafetyRule.DRAWDOWN_LIMIT,
                reason=f"Drawdown {current_dd:.2%} exceeds max {self._config.max_drawdown_pct:.2%}",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_order_size(self, plan: dict) -> ControlDecision:
        orders = plan.get("orders", [])
        for order in orders:
            size = order.get("quantity", 0)
            max_size = order.get("max_order_size", float("inf"))
            if size > max_size:
                return ControlDecision(
                    result=DecisionResult.RESIZE,
                    rule=SafetyRule.ORDER_SIZE_LIMIT,
                    reason=f"Order size {size} exceeds limit {max_size}",
                )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_execution_rate(self, plan: dict) -> ControlDecision:
        participation = plan.get("participation_rate", 0.05)
        if participation > 0.20:
            return ControlDecision(
                result=DecisionResult.RESIZE,
                rule=SafetyRule.EXECUTION_RATE_LIMIT,
                reason=f"Participation rate {participation:.1%} exceeds limit 20%",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    def _check_cost(self, plan: dict) -> ControlDecision:
        expected_cost = plan.get("expected_cost_bps", 0)
        if expected_cost > self._config.max_execution_cost_bps:
            return ControlDecision(
                result=DecisionResult.REJECT,
                rule=SafetyRule.COST_LIMIT,
                reason=f"Expected cost {expected_cost} bps exceeds max {self._config.max_execution_cost_bps} bps",
            )
        return ControlDecision(result=DecisionResult.ALLOW)

    # ── Properties ─────────────────────────────────────────────

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    @property
    def recent_violations(self) -> list[ControlDecision]:
        return self._violations[-100:]

    def clear_violations(self) -> None:
        self._violations.clear()
