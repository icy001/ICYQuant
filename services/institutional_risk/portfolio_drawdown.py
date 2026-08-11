"""PortfolioDrawdown — portfolio-level drawdown tracking and analysis.

Extends the DrawdownEngine with portfolio-specific metrics
including contribution analysis across constituent strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.drawdown_engine import (
    DrawdownEngine,
    DrawdownLevel,
    DrawdownRecord,
    DrawdownState,
)


@dataclass
class PortfolioDrawdownProfile:
    """Portfolio drawdown analysis result."""

    portfolio_id: str
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_value: float = 0.0
    current_value: float = 0.0
    recovery_needed_pct: float = 0.0
    strategy_contributions: Dict[str, float] = field(default_factory=dict)
    drawdown_duration_days: float = 0.0
    drawdown_velocity: float = 0.0  # dd% per day
    worst_strategy: Optional[str] = None
    worst_strategy_dd: float = 0.0


class PortfolioDrawdownAnalyzer:
    """Portfolio-level drawdown analysis.

    Tracks drawdown at the portfolio level and attributes
    contribution across constituent strategies.

    Usage::

        analyzer = PortfolioDrawdownAnalyzer()
        analyzer.update("portfolio_1", 50_000_000, strategy_values={...})
        profile = analyzer.analyze("portfolio_1")
    """

    def __init__(self, drawdown_engine: Optional[DrawdownEngine] = None):
        self._engine = drawdown_engine or DrawdownEngine()
        self._portfolio_values: Dict[str, List[float]] = {}
        self._strategy_contribution_history: Dict[str, Dict[str, List[float]]] = {}

    def update(
        self,
        portfolio_id: str,
        current_value: float,
        strategy_values: Optional[Dict[str, float]] = None,
    ) -> DrawdownState:
        """Update portfolio drawdown tracking.

        Args:
            portfolio_id: portfolio identifier
            current_value: total portfolio value
            strategy_values: {strategy_id: current_value} for contribution analysis
        """
        state = self._engine.update(portfolio_id, current_value, DrawdownLevel.PORTFOLIO)

        # track strategy contributions
        if strategy_values:
            if portfolio_id not in self._strategy_contribution_history:
                self._strategy_contribution_history[portfolio_id] = {}
            for sid, val in strategy_values.items():
                if sid not in self._strategy_contribution_history[portfolio_id]:
                    self._strategy_contribution_history[portfolio_id][sid] = []
                self._strategy_contribution_history[portfolio_id][sid].append(val)

        return state

    def analyze(self, portfolio_id: str) -> PortfolioDrawdownProfile:
        """Generate a portfolio drawdown analysis profile."""
        state = self._engine.get_state(portfolio_id)
        if not state:
            return PortfolioDrawdownProfile(portfolio_id=portfolio_id)

        engine = self._engine
        recovery = engine.compute_recovery_needed(portfolio_id)

        # strategy contributions
        strategy_contribs: Dict[str, float] = {}
        worst_sid = None
        worst_dd = 0.0

        contrib_history = self._strategy_contribution_history.get(portfolio_id, {})
        for sid, values in contrib_history.items():
            if len(values) >= 2:
                peak = max(values)
                current = values[-1]
                dd = (peak - current) / max(peak, 1e-9) * 100
                strategy_contribs[sid] = dd
                if dd > worst_dd:
                    worst_dd = dd
                    worst_sid = sid

        # drawdown velocity
        velocity = 0.0
        if state.in_drawdown and state.drawdown_start_time:
            import time
            days = max((time.time() - state.drawdown_start_time) / 86400, 1)
            velocity = state.drawdown_pct / days

        return PortfolioDrawdownProfile(
            portfolio_id=portfolio_id,
            current_drawdown_pct=state.drawdown_pct,
            max_drawdown_pct=state.max_drawdown_pct,
            peak_value=state.peak_value,
            current_value=state.current_value,
            recovery_needed_pct=recovery,
            strategy_contributions=strategy_contribs,
            drawdown_duration_days=(
                (time.time() - state.drawdown_start_time) / 86400
                if state.drawdown_start_time else 0.0
            ),
            drawdown_velocity=velocity,
            worst_strategy=worst_sid,
            worst_strategy_dd=worst_dd,
        )

    def reset(self, portfolio_id: Optional[str] = None) -> None:
        """Reset tracking for a portfolio or all."""
        if portfolio_id:
            self._portfolio_values.pop(portfolio_id, None)
            self._strategy_contribution_history.pop(portfolio_id, None)
        else:
            self._engine.reset()
            self._portfolio_values.clear()
            self._strategy_contribution_history.clear()

import time  # noqa: E402
