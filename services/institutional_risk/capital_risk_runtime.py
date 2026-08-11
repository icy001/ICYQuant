"""CapitalRiskRuntime — runtime state and live risk monitoring."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from services.institutional_risk.capital_risk_engine import (
    CapitalRiskConfig,
    CapitalRiskEngine,
    RiskEngineMode,
    RiskSnapshot,
)


@dataclass
class RuntimeRiskState:
    """Live risk state maintained by the runtime."""

    current_snapshot: Optional[RiskSnapshot] = None
    previous_snapshot: Optional[RiskSnapshot] = None
    mode: RiskEngineMode = RiskEngineMode.NORMAL
    mode_duration_secs: float = 0.0
    mode_transitioned_at: float = 0.0
    risk_budget_breaches: int = 0
    stress_events: int = 0
    survival_events: int = 0
    deleveraging_events: int = 0
    freeze_events: int = 0
    emergency_events: int = 0


@dataclass
class RuntimeRiskConfig:
    """Runtime configuration."""

    compute_interval_secs: float = 1.0
    mode_cooldown_secs: float = 5.0
    max_capital_pool_size: float = 1e9
    callback_on_mode_change: bool = True
    callback_on_breach: bool = True
    callback_on_survival_drop: bool = True
    survival_drop_threshold: float = 10.0


class CapitalRiskRuntime:
    """Live risk runtime — continuously monitors risk state.

    Manages the risk engine lifecycle and provides real-time risk snapshots.
    Triggers callbacks on material risk state changes.

    Usage::

        runtime = CapitalRiskRuntime()
        runtime.start()
        # ...
        state = runtime.get_risk_state()
    """

    def __init__(
        self,
        config: Optional[RuntimeRiskConfig] = None,
        engine_config: Optional[CapitalRiskConfig] = None,
    ):
        self.config = config or RuntimeRiskConfig()
        self._engine = CapitalRiskEngine(engine_config)
        self._state = RuntimeRiskState()
        self._running = False
        self._last_compute: float = 0.0
        self._callbacks: Dict[str, List[Callable[[RiskSnapshot], None]]] = {
            "mode_change": [],
            "breach": [],
            "survival_drop": [],
            "snapshot": [],
        }

    # ── properties ──────────────────────────────────────────────────

    @property
    def engine(self) -> CapitalRiskEngine:
        return self._engine

    @property
    def state(self) -> RuntimeRiskState:
        return self._state

    @property
    def running(self) -> bool:
        return self._running

    # ── lifecycle ───────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._state.mode_transitioned_at = time.time()

    def stop(self) -> None:
        self._running = False

    def tick(
        self,
        capital_pool: float,
        portfolio_states: Dict[str, Any],
        market_state: Optional[Dict[str, Any]] = None,
    ) -> RiskSnapshot:
        """Compute a risk snapshot and update runtime state."""
        now = time.time()
        snapshot = self._engine.compute_risk(capital_pool, portfolio_states, market_state)

        # update state
        self._state.previous_snapshot = self._state.current_snapshot
        self._state.current_snapshot = snapshot

        # detect mode change
        if snapshot.mode != self._state.mode:
            prev_mode = self._state.mode
            self._state.mode = snapshot.mode
            self._state.mode_transitioned_at = now
            self._state.mode_duration_secs = 0.0

            if self.config.callback_on_mode_change:
                self._dispatch("mode_change", snapshot)

            # event counters
            if snapshot.mode in (RiskEngineMode.CRITICAL, RiskEngineMode.EMERGENCY):
                self._state.emergency_events += 1
        else:
            self._state.mode_duration_secs = now - self._state.mode_transitioned_at

        # detect survival drop
        if self._state.previous_snapshot and self.config.callback_on_survival_drop:
            prev_score = self._state.previous_snapshot.survival_score
            curr_score = snapshot.survival_score
            if prev_score - curr_score >= self.config.survival_drop_threshold:
                self._state.survival_events += 1
                self._dispatch("survival_drop", snapshot)

        # detect budget breach
        if snapshot.risk_budget_available < 0 and self.config.callback_on_breach:
            self._state.risk_budget_breaches += 1
            self._dispatch("breach", snapshot)

        self._dispatch("snapshot", snapshot)
        self._last_compute = now
        return snapshot

    # ── callbacks ───────────────────────────────────────────────────

    def on(self, event: str, callback: Callable[[RiskSnapshot], None]) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _dispatch(self, event: str, snapshot: RiskSnapshot) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(snapshot)
            except Exception:
                pass

    # ── queries ─────────────────────────────────────────────────────

    def get_risk_state(self) -> Dict[str, Any]:
        snapshot = self._state.current_snapshot
        return {
            "mode": self._state.mode.name,
            "mode_duration_secs": self._state.mode_duration_secs,
            "var_99": snapshot.var_99 if snapshot else None,
            "es_99": snapshot.expected_shortfall_99 if snapshot else None,
            "drawdown_pct": snapshot.drawdown_pct if snapshot else None,
            "survival_score": snapshot.survival_score if snapshot else None,
            "risk_budget_used": snapshot.risk_budget_used if snapshot else None,
            "risk_budget_available": snapshot.risk_budget_available if snapshot else None,
            "breaches": self._state.risk_budget_breaches,
            "stress_events": self._state.stress_events,
            "survival_events": self._state.survival_events,
        }

    def reset(self) -> None:
        self._engine.reset()
        self._state = RuntimeRiskState()
        self._running = False
