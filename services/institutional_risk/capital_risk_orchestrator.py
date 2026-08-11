"""CapitalRiskOrchestrator — top-level orchestrator for the risk subsystem.

Connects the Autonomous Control Plane with the full risk chain:
    Capital Governor → Portfolio Orchestrator → Capacity Intelligence
    → Capital Risk Engine → Stress Engine → Survival Guard
    → Normal / Emergency → Execution / Deleveraging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from services.institutional_risk.capital_risk_engine import (
    CapitalRiskConfig,
    CapitalRiskEngine,
    RiskEngineMode,
    RiskSnapshot,
)
from services.institutional_risk.capital_risk_manager import CapitalRiskManager
from services.institutional_risk.capital_risk_runtime import CapitalRiskRuntime
from services.institutional_risk.capital_risk_controller import (
    CapitalRiskController,
    RiskAction,
    RiskActionType,
    RiskDecision,
)


class OrchestratorState(Enum):
    """Orchestrator lifecycle states."""

    INIT = auto()
    RUNNING = auto()
    PAUSED = auto()
    DEFENSIVE = auto()
    EMERGENCY = auto()
    STOPPED = auto()


@dataclass
class OrchestratorConfig:
    """Configuration for the risk orchestrator."""

    auto_deleverage: bool = True
    auto_reallocate_risk: bool = True
    auto_emergency_exit: bool = False  # safety: requires explicit opt-in
    escalation_timeout_secs: float = 30.0
    max_daily_actions: int = 100
    audit_trail_enabled: bool = True


@dataclass
class RiskAuditEntry:
    """Audit trail entry for a risk action."""

    timestamp: float
    mode_before: str
    mode_after: str
    actions: List[str]
    survival_before: float
    survival_after: float
    reason: str


class CapitalRiskOrchestrator:
    """Top-level risk subsystem orchestrator.

    Integrates the risk engine, runtime, manager, and controller into
    a unified interface suitable for the Autonomous Control Plane.

    Usage::

        orchestrator = CapitalRiskOrchestrator()
        orchestrator.start(capital_pool=100_000_000)
        decision = orchestrator.tick(portfolio_states)
        orchestrator.execute(decision)
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self._engine = CapitalRiskEngine()
        self._runtime = CapitalRiskRuntime(engine_config=self._engine.config)
        self._manager = CapitalRiskManager(engine_config=self._engine.config)
        self._controller = CapitalRiskController(self._engine)
        self._state: OrchestratorState = OrchestratorState.INIT
        self._audit_trail: List[RiskAuditEntry] = []
        self._action_count_today: int = 0

    # ── properties ──────────────────────────────────────────────────

    @property
    def engine(self) -> CapitalRiskEngine:
        return self._engine

    @property
    def runtime(self) -> CapitalRiskRuntime:
        return self._runtime

    @property
    def manager(self) -> CapitalRiskManager:
        return self._manager

    @property
    def state(self) -> OrchestratorState:
        return self._state

    @property
    def mode(self) -> RiskEngineMode:
        return self._engine.mode

    # ── lifecycle ───────────────────────────────────────────────────

    def start(
        self,
        capital_pool: float,
        portfolio_states: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Start the orchestrator."""
        self._state = OrchestratorState.RUNNING
        self._manager.start(capital_pool, portfolio_states or {}, market_state)

    def stop(self) -> None:
        """Stop the orchestrator."""
        self._manager.stop()
        self._state = OrchestratorState.STOPPED

    def tick(
        self,
        portfolio_states: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
    ) -> RiskDecision:
        """Compute risk and produce a decision."""
        snapshot = self._manager.update(
            portfolio_states=portfolio_states,
            market_state=market_state,
        )

        # update orchestrator state
        if snapshot.mode in (RiskEngineMode.CRITICAL, RiskEngineMode.EMERGENCY):
            self._state = OrchestratorState.EMERGENCY
        elif snapshot.mode == RiskEngineMode.DEFENSIVE:
            self._state = OrchestratorState.DEFENSIVE
        else:
            self._state = OrchestratorState.RUNNING

        decision = self._controller.evaluate(snapshot)
        return decision

    # ── execution ───────────────────────────────────────────────────

    def execute(self, decision: RiskDecision) -> List[RiskAuditEntry]:
        """Execute the risk decision and record audit trail."""
        entries: List[RiskAuditEntry] = []
        snapshot_before = self._engine.latest_snapshot

        for action in decision.actions:
            if self._action_count_today >= self.config.max_daily_actions:
                break

            entry = RiskAuditEntry(
                timestamp=snapshot_before.timestamp if snapshot_before else 0,
                mode_before=self._engine.mode.name,
                mode_after=decision.mode.name,
                actions=[action.action_type.name],
                survival_before=snapshot_before.survival_score if snapshot_before else 100,
                survival_after=snapshot_before.survival_score if snapshot_before else 100,
                reason=action.reason,
            )
            entries.append(entry)
            self._action_count_today += 1

        if self.config.audit_trail_enabled:
            self._audit_trail.extend(entries)

        return entries

    # ── defensive behavior ──────────────────────────────────────────

    def enter_defensive(self, reason: str) -> RiskDecision:
        """Manually enter defensive mode."""
        actions = [
            RiskAction(RiskActionType.FREEZE_NEW_RISK, reason=reason, priority=10),
            RiskAction(RiskActionType.REDUCE_LEVERAGE, reason=reason, target_reduction_pct=30.0, priority=20),
            RiskAction(RiskActionType.INCREASE_RESERVE, reason=reason, target_reduction_pct=25.0, priority=30),
            RiskAction(RiskActionType.STRESS_CHECK, reason=reason, priority=40),
        ]
        decision = RiskDecision(
            mode=RiskEngineMode.DEFENSIVE,
            actions=actions,
            freeze_new_risk=True,
            require_stress_test=True,
            require_survival_check=True,
            summary=f"Defensive mode entered: {reason}",
        )
        return decision

    def enter_emergency(self, reason: str) -> RiskDecision:
        """Manually enter emergency mode."""
        actions = [
            RiskAction(RiskActionType.FREEZE_NEW_RISK, reason=reason, priority=5),
            RiskAction(RiskActionType.REDUCE_LEVERAGE, reason=reason, target_reduction_pct=50.0, priority=10),
            RiskAction(RiskActionType.REDUCE_POSITION, reason=reason, target_reduction_pct=40.0, priority=15),
            RiskAction(RiskActionType.INCREASE_RESERVE, reason=reason, target_reduction_pct=40.0, priority=20),
            RiskAction(RiskActionType.SURVIVAL_CHECK, reason=reason, priority=100),
        ]
        decision = RiskDecision(
            mode=RiskEngineMode.CRITICAL,
            actions=actions,
            freeze_new_risk=True,
            require_stress_test=True,
            require_survival_check=True,
            summary=f"Emergency mode entered: {reason}",
        )
        return decision

    # ── queries ─────────────────────────────────────────────────────

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get the full audit trail."""
        return [
            {
                "timestamp": e.timestamp,
                "mode_before": e.mode_before,
                "mode_after": e.mode_after,
                "actions": e.actions,
                "survival_before": e.survival_before,
                "survival_after": e.survival_after,
                "reason": e.reason,
            }
            for e in self._audit_trail
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        return {
            "state": self._state.name,
            "mode": self._engine.mode.name,
            "actions_today": self._action_count_today,
            "audit_entries": len(self._audit_trail),
            **self._manager.get_status(),
        }

    def reset_daily_counters(self) -> None:
        """Reset daily action counters."""
        self._action_count_today = 0
