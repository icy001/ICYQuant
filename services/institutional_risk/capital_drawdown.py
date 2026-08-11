"""CapitalDrawdown — capital pool-level drawdown tracking.

The highest level of drawdown monitoring, aggregating across
all portfolios and strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.drawdown_engine import (
    DrawdownEngine,
    DrawdownLevel,
    DrawdownState,
)


@dataclass
class CapitalDrawdownProfile:
    """Capital pool drawdown profile."""

    total_capital: float = 0.0
    peak_capital: float = 0.0
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    recovery_needed_pct: float = 0.0
    portfolio_contributions: Dict[str, float] = field(default_factory=dict)
    total_portfolio_drawdowns: int = 0
    portfolios_in_drawdown: int = 0
    status: str = "NORMAL"  # NORMAL, CAUTION, DEFENSIVE, CRITICAL
    drawdown_velocity: float = 0.0


class CapitalDrawdownAnalyzer:
    """Capital pool-level drawdown analysis.

    Aggregates drawdown signals from all portfolios and strategies
    to produce a unified capital-level view.

    Usage::

        analyzer = CapitalDrawdownAnalyzer(capital=100_000_000)
        analyzer.update_portfolio("pf_1", 45_000_000)
        analyzer.update_portfolio("pf_2", 55_000_000)
        profile = analyzer.analyze()
    """

    def __init__(
        self,
        capital: float,
        drawdown_engine: Optional[DrawdownEngine] = None,
    ):
        self._engine = drawdown_engine or DrawdownEngine()
        self._portfolio_values: Dict[str, float] = {}
        self._capital = capital
        self._peak_capital = capital
        self._max_drawdown = 0.0

        # thresholds
        self.caution_threshold = 10.0
        self.defensive_threshold = 20.0
        self.critical_threshold = 30.0

    @property
    def capital(self) -> float:
        return self._capital

    def update_capital(self, total_capital: float) -> DrawdownState:
        """Update the total capital pool value."""
        self._capital = total_capital
        if total_capital > self._peak_capital:
            self._peak_capital = total_capital

        dd_pct = 0.0
        if self._peak_capital > 0:
            dd_pct = (self._peak_capital - total_capital) / self._peak_capital * 100

        self._max_drawdown = max(self._max_drawdown, dd_pct)

        return self._engine.update("capital", total_capital, DrawdownLevel.CAPITAL)

    def update_portfolio(self, portfolio_id: str, value: float) -> None:
        """Update a portfolio's value for contribution tracking."""
        self._portfolio_values[portfolio_id] = value
        self._engine.update(portfolio_id, value, DrawdownLevel.PORTFOLIO)

    def analyze(self) -> CapitalDrawdownProfile:
        """Produce a capital-level drawdown profile."""
        state = self._engine.get_state("capital")

        dd_pct = state.drawdown_pct if state else 0.0

        # status
        status = "NORMAL"
        if dd_pct >= self.critical_threshold:
            status = "CRITICAL"
        elif dd_pct >= self.defensive_threshold:
            status = "DEFENSIVE"
        elif dd_pct >= self.caution_threshold:
            status = "CAUTION"

        # portfolio contributions
        contribs: Dict[str, float] = {}
        portfolios_in_dd = 0
        total_in_dd = 0
        for pid, val in self._portfolio_values.items():
            p_state = self._engine.get_state(pid)
            if p_state and p_state.in_drawdown:
                contribs[pid] = p_state.drawdown_pct
                portfolios_in_dd += 1
                total_in_dd += 1

        # recovery
        recovery = self._engine.compute_recovery_needed("capital")

        # velocity: drawdown change per unit time
        velocity = 0.0
        if state and state.in_drawdown and state.drawdown_start_time:
            import time
            days = max((time.time() - state.drawdown_start_time) / 86400, 1)
            velocity = dd_pct / days

        return CapitalDrawdownProfile(
            total_capital=self._capital,
            peak_capital=self._peak_capital,
            current_drawdown_pct=dd_pct,
            max_drawdown_pct=self._max_drawdown,
            recovery_needed_pct=recovery,
            portfolio_contributions=contribs,
            total_portfolio_drawdowns=total_in_dd,
            portfolios_in_drawdown=portfolios_in_dd,
            status=status,
            drawdown_velocity=velocity,
        )

    def reset(self) -> None:
        """Reset all tracking."""
        self._engine.reset()
        self._portfolio_values.clear()
        self._peak_capital = self._capital
        self._max_drawdown = 0.0
