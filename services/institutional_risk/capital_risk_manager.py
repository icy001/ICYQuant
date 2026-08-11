"""CapitalRiskManager — lifecycle manager for the risk subsystem."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.capital_risk_engine import (
    CapitalRiskConfig,
    CapitalRiskEngine,
    RiskEngineMode,
    RiskSnapshot,
)
from services.institutional_risk.capital_risk_runtime import CapitalRiskRuntime, RuntimeRiskConfig


@dataclass
class RiskManagerConfig:
    """Configuration for the risk manager."""

    compute_interval_secs: float = 1.0
    auto_mode_switch: bool = True
    stress_on_mode_change: bool = True
    survival_on_mode_change: bool = True
    log_mode_transitions: bool = True
    max_snapshots: int = 10000


class CapitalRiskManager:
    """Manages the full risk subsystem lifecycle.

    Orchestrates the risk engine, runtime, and downstream actions.
    Runs a background monitoring loop.

    Usage::

        manager = CapitalRiskManager()
        manager.start(capital_pool=100_000_000, portfolio_states={...})
        # ...
        manager.stop()
    """

    def __init__(
        self,
        config: Optional[RiskManagerConfig] = None,
        engine_config: Optional[CapitalRiskConfig] = None,
        runtime_config: Optional[RuntimeRiskConfig] = None,
    ):
        self.config = config or RiskManagerConfig()
        self._engine = CapitalRiskEngine(engine_config)
        self._runtime = CapitalRiskRuntime(runtime_config, engine_config)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._mode_history: List[tuple[float, RiskEngineMode]] = []
        self._capital_pool: float = 0.0
        self._portfolio_states: Dict[str, Any] = {}
        self._market_state: Optional[Dict[str, Any]] = None

    # ── properties ──────────────────────────────────────────────────

    @property
    def engine(self) -> CapitalRiskEngine:
        return self._engine

    @property
    def runtime(self) -> CapitalRiskRuntime:
        return self._runtime

    @property
    def mode(self) -> RiskEngineMode:
        return self._engine.mode

    # ── lifecycle ───────────────────────────────────────────────────

    def start(
        self,
        capital_pool: float,
        portfolio_states: Dict[str, Any],
        market_state: Optional[Dict[str, Any]] = None,
        background: bool = False,
    ) -> None:
        """Start the risk manager."""
        self._capital_pool = capital_pool
        self._portfolio_states = portfolio_states
        self._market_state = market_state
        self._stop_event.clear()
        self._runtime.start()

        if background:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the risk manager."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._runtime.stop()

    def update(
        self,
        capital_pool: Optional[float] = None,
        portfolio_states: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
    ) -> RiskSnapshot:
        """Update state and compute a single risk snapshot."""
        if capital_pool is not None:
            self._capital_pool = capital_pool
        if portfolio_states is not None:
            self._portfolio_states = portfolio_states
        if market_state is not None:
            self._market_state = market_state

        snapshot = self._runtime.tick(
            self._capital_pool,
            self._portfolio_states,
            self._market_state,
        )

        # log mode transitions
        if self.config.log_mode_transitions and self._runtime.state.mode_transitioned_at:
            if not self._mode_history or self._mode_history[-1][1] != snapshot.mode:
                self._mode_history.append((time.time(), snapshot.mode))

        return snapshot

    # ── background loop ─────────────────────────────────────────────

    def _loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self.update()
            except Exception:
                pass
            self._stop_event.wait(self.config.compute_interval_secs)

    # ── queries ─────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get current risk manager status."""
        runtime_state = self._runtime.get_risk_state()
        return {
            "mode": runtime_state["mode"],
            "survival_score": runtime_state["survival_score"],
            "var_99": runtime_state["var_99"],
            "es_99": runtime_state["es_99"],
            "drawdown_pct": runtime_state["drawdown_pct"],
            "risk_budget_used": runtime_state["risk_budget_used"],
            "risk_budget_available": runtime_state["risk_budget_available"],
            "breaches": runtime_state["breaches"],
            "stress_events": runtime_state["stress_events"],
            "survival_events": runtime_state["survival_events"],
            "mode_transitions": len(self._mode_history),
            "running": self._runtime.running,
        }

    def get_mode_history(self) -> List[Dict[str, Any]]:
        """Get history of mode transitions."""
        return [
            {"timestamp": ts, "mode": mode.name}
            for ts, mode in self._mode_history
        ]

    def reset(self) -> None:
        """Reset the risk manager."""
        self._engine.reset()
        self._runtime.reset()
        self._mode_history.clear()
