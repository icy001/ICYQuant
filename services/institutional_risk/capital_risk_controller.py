"""CapitalRiskController — risk control actions and decision interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from services.institutional_risk.capital_risk_engine import (
    CapitalRiskEngine,
    RiskEngineMode,
    RiskSnapshot,
)


class RiskActionType(Enum):
    """Risk control action types."""

    NONE = auto()
    REDUCE_RISK = auto()
    INCREASE_HEDGE = auto()
    FREEZE_NEW_RISK = auto()
    REDUCE_LEVERAGE = auto()
    REDUCE_POSITION = auto()
    REDUCE_CORRELATION = auto()
    INCREASE_RESERVE = auto()
    EMERGENCY_EXIT = auto()
    REALLOCATE_RISK = auto()
    STRESS_CHECK = auto()
    SURVIVAL_CHECK = auto()


@dataclass
class RiskAction:
    """A risk control action."""

    action_type: RiskActionType
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    target_reduction_pct: float = 0.0
    reason: str = ""
    priority: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskDecision:
    """Top-level risk control decision."""

    mode: RiskEngineMode
    actions: List[RiskAction] = field(default_factory=list)
    freeze_new_risk: bool = False
    require_stress_test: bool = False
    require_survival_check: bool = False
    summary: str = ""


class CapitalRiskController:
    """Implements risk control decision logic.

    Translates risk snapshots into concrete risk actions based on
    the current risk engine mode and severity.

    Usage::

        controller = CapitalRiskController(engine)
        decision = controller.evaluate(snapshot)
        for action in decision.actions:
            execute(action)
    """

    def __init__(self, engine: CapitalRiskEngine):
        self._engine = engine

    # ── evaluation ──────────────────────────────────────────────────

    def evaluate(self, snapshot: Optional[RiskSnapshot] = None) -> RiskDecision:
        """Evaluate current risk state and produce a control decision."""
        if snapshot is None:
            snapshot = self._engine.latest_snapshot

        if snapshot is None:
            return RiskDecision(mode=RiskEngineMode.NORMAL)

        decision = RiskDecision(mode=snapshot.mode)

        if snapshot.mode == RiskEngineMode.NORMAL:
            decision.actions = self._normal_actions(snapshot)
        elif snapshot.mode == RiskEngineMode.CAUTION:
            decision.actions = self._caution_actions(snapshot)
        elif snapshot.mode == RiskEngineMode.DEFENSIVE:
            decision.actions = self._defensive_actions(snapshot)
        elif snapshot.mode in (RiskEngineMode.CRITICAL, RiskEngineMode.EMERGENCY):
            decision.actions = self._critical_actions(snapshot)

        decision.summary = self._build_summary(decision, snapshot)
        return decision

    # ── per-mode action generation ──────────────────────────────────

    def _normal_actions(self, snapshot: RiskSnapshot) -> List[RiskAction]:
        actions: List[RiskAction] = []
        # Check risk budget
        if snapshot.risk_budget_available < snapshot.risk_budget_total * 0.05:
            actions.append(RiskAction(
                action_type=RiskActionType.REDUCE_RISK,
                reason="Risk budget nearly exhausted",
                priority=90,
            ))
        # Check factor concentration
        for factor, exposure in snapshot.factor_exposures.items():
            if exposure > 35.0:
                actions.append(RiskAction(
                    action_type=RiskActionType.REDUCE_CORRELATION,
                    reason=f"Factor concentration breach: {factor}={exposure:.1f}",
                    target_reduction_pct=exposure - 35.0,
                    metadata={"factor": factor, "exposure": exposure},
                    priority=80,
                ))
        return actions

    def _caution_actions(self, snapshot: RiskSnapshot) -> List[RiskAction]:
        actions: List[RiskAction] = []
        actions.append(RiskAction(
            action_type=RiskActionType.FREEZE_NEW_RISK,
            reason="Caution mode — no new risk exposure",
            priority=50,
        ))
        decision = RiskDecision(mode=snapshot.mode)
        decision.freeze_new_risk = True

        if snapshot.drawdown_pct > 10.0:
            actions.append(RiskAction(
                action_type=RiskActionType.REDUCE_RISK,
                reason=f"Drawdown {snapshot.drawdown_pct:.1f}% exceeds caution threshold",
                target_reduction_pct=5.0,
                priority=60,
            ))
        return actions

    def _defensive_actions(self, snapshot: RiskSnapshot) -> List[RiskAction]:
        actions: List[RiskAction] = []
        actions.append(RiskAction(
            action_type=RiskActionType.FREEZE_NEW_RISK,
            reason="Defensive mode — freeze new risk",
            priority=30,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.REDUCE_LEVERAGE,
            reason="Defensive mode — reduce leverage",
            target_reduction_pct=30.0,
            priority=40,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.REDUCE_CORRELATION,
            reason="Defensive mode — reduce correlated clusters",
            target_reduction_pct=20.0,
            priority=45,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.INCREASE_RESERVE,
            reason="Defensive mode — increase capital reserve",
            target_reduction_pct=35.0,
            priority=50,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.STRESS_CHECK,
            reason="Defensive mode — stress test required",
            priority=60,
        ))
        return actions

    def _critical_actions(self, snapshot: RiskSnapshot) -> List[RiskAction]:
        actions: List[RiskAction] = []
        actions.append(RiskAction(
            action_type=RiskActionType.FREEZE_NEW_RISK,
            reason="Critical mode — absolute freeze",
            priority=10,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.REDUCE_LEVERAGE,
            reason="Critical mode — aggressive deleveraging",
            target_reduction_pct=50.0,
            priority=20,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.REDUCE_POSITION,
            reason="Critical mode — reduce high-beta positions",
            target_reduction_pct=40.0,
            priority=25,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.REDUCE_CORRELATION,
            reason="Critical mode — reduce all correlated clusters",
            target_reduction_pct=50.0,
            priority=30,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.INCREASE_RESERVE,
            reason="Critical mode — maximum reserve",
            target_reduction_pct=40.0,
            priority=35,
        ))
        actions.append(RiskAction(
            action_type=RiskActionType.SURVIVAL_CHECK,
            reason="Critical mode — survival check required",
            priority=100,
        ))
        return actions

    # ── summary ─────────────────────────────────────────────────────

    def _build_summary(self, decision: RiskDecision, snapshot: RiskSnapshot) -> str:
        parts = [f"Mode: {decision.mode.name}"]
        parts.append(f"Survival: {snapshot.survival_score:.0f}/100")
        parts.append(f"Drawdown: {snapshot.drawdown_pct:.1f}%")
        parts.append(f"VaR 99%: {snapshot.var_99:.2f}")
        parts.append(f"Actions: {len(decision.actions)}")
        if decision.freeze_new_risk:
            parts.append("FREEZE")
        return " | ".join(parts)
