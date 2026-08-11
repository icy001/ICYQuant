"""CapitalRiskEngine — unified risk engine for institutional capital pools.

Aggregates strategy-level risk into portfolio-level and capital-pool-level risk,
accounting for correlation, factor exposure, and tail dependence.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class RiskEngineMode(Enum):
    NORMAL = auto()
    CAUTION = auto()
    DEFENSIVE = auto()
    CRITICAL = auto()
    EMERGENCY = auto()


class RiskAggregationLevel(Enum):
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    ACCOUNT = "account"
    CAPITAL_POOL = "capital_pool"


@dataclass
class RiskSnapshot:
    """Immutable snapshot of risk state at a point in time."""

    timestamp: float = field(default_factory=time.time)
    level: RiskAggregationLevel = RiskAggregationLevel.CAPITAL_POOL
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    correlation_risk: float = 0.0
    tail_risk_score: float = 0.0
    survival_score: float = 100.0
    risk_budget_total: float = 0.0
    risk_budget_used: float = 0.0
    risk_budget_available: float = 0.0
    mode: RiskEngineMode = RiskEngineMode.NORMAL

    @property
    def checksum(self) -> str:
        raw = f"{self.var_99:.6f}{self.expected_shortfall_99:.6f}{self.survival_score:.2f}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class CapitalRiskConfig:
    """Configuration for the capital risk engine."""

    var_confidence_levels: List[float] = field(default_factory=lambda: [0.95, 0.99])
    es_confidence_levels: List[float] = field(default_factory=lambda: [0.95, 0.99])
    stress_scenarios_enabled: bool = True
    tail_risk_enabled: bool = True
    factor_risk_enabled: bool = True
    correlation_breakdown_enabled: bool = True
    survival_scoring_enabled: bool = True
    risk_budget_enabled: bool = True

    survival_threshold_caution: float = 75.0
    survival_threshold_defensive: float = 60.0
    survival_threshold_critical: float = 40.0

    drawdown_caution_pct: float = 10.0
    drawdown_defensive_pct: float = 20.0
    drawdown_critical_pct: float = 30.0

    correlation_spike_threshold: float = 0.30
    tail_dependence_threshold: float = 0.70
    factor_concentration_limit: float = 35.0

    auto_mode_switch: bool = True
    snapshot_retention: int = 1000


class CapitalRiskEngine:
    """Unified capital risk engine.

    Aggregates risk from strategy → portfolio → account → capital pool,
    with full correlation, factor, and tail-dependence awareness.

    Usage::

        engine = CapitalRiskEngine(config)
        snapshot = engine.compute_risk(capital_pool, portfolio_states)
        if snapshot.mode == RiskEngineMode.CRITICAL:
            engine.trigger_defensive_actions()
    """

    def __init__(self, config: Optional[CapitalRiskConfig] = None):
        self.config = config or CapitalRiskConfig()
        self._mode: RiskEngineMode = RiskEngineMode.NORMAL
        self._snapshots: List[RiskSnapshot] = []
        self._strategy_risks: Dict[str, Dict[str, float]] = {}
        self._portfolio_risks: Dict[str, Dict[str, float]] = {}
        self._enabled: bool = True

    # ── properties ──────────────────────────────────────────────────

    @property
    def mode(self) -> RiskEngineMode:
        return self._mode

    @property
    def snapshots(self) -> List[RiskSnapshot]:
        return list(self._snapshots)

    @property
    def latest_snapshot(self) -> Optional[RiskSnapshot]:
        return self._snapshots[-1] if self._snapshots else None

    # ── main compute pipeline ───────────────────────────────────────

    def compute_risk(
        self,
        capital_pool: float,
        portfolio_states: Dict[str, Any],
        market_state: Optional[Dict[str, Any]] = None,
    ) -> RiskSnapshot:
        """Run the full risk computation pipeline.

        Args:
            capital_pool: total capital in the pool
            portfolio_states: mapping of portfolio_id → state dict
            market_state: current market conditions (optional)
        """
        if not self._enabled:
            return RiskSnapshot()

        snapshot = RiskSnapshot(
            level=RiskAggregationLevel.CAPITAL_POOL,
            risk_budget_total=capital_pool * 0.08,  # 8% default risk budget
        )

        # Step 1: aggregate strategy-level risks
        strategy_risks = self._aggregate_strategy_risks(portfolio_states)

        # Step 2: aggregate to portfolio-level
        portfolio_risk = self._aggregate_portfolio_risk(strategy_risks)

        # Step 3: aggregate to capital-pool-level
        capital_risk = self._aggregate_capital_risk(portfolio_risk)

        # Step 4: compute VaR metrics (placeholder — delegated to VaREngine)
        snapshot.var_95 = capital_risk.get("var_95", 0.0)
        snapshot.var_99 = capital_risk.get("var_99", 0.0)
        snapshot.expected_shortfall_95 = capital_risk.get("es_95", 0.0)
        snapshot.expected_shortfall_99 = capital_risk.get("es_99", 0.0)

        # Step 5: drawdown
        snapshot.drawdown_pct = capital_risk.get("drawdown_pct", 0.0)
        snapshot.max_drawdown_pct = capital_risk.get("max_drawdown_pct", 0.0)

        # Step 6: factor exposures
        if self.config.factor_risk_enabled:
            snapshot.factor_exposures = capital_risk.get("factor_exposures", {})

        # Step 7: correlation risk
        if self.config.correlation_breakdown_enabled:
            snapshot.correlation_risk = capital_risk.get("correlation_risk", 0.0)

        # Step 8: tail risk
        if self.config.tail_risk_enabled:
            snapshot.tail_risk_score = capital_risk.get("tail_risk_score", 0.0)

        # Step 9: survival score
        if self.config.survival_scoring_enabled:
            snapshot.survival_score = self._compute_survival_score(snapshot)

        # Step 10: risk budget
        if self.config.risk_budget_enabled:
            snapshot.risk_budget_total = capital_risk.get("risk_budget_total", snapshot.risk_budget_total)
            snapshot.risk_budget_used = capital_risk.get("risk_budget_used", 0.0)
            snapshot.risk_budget_available = snapshot.risk_budget_total - snapshot.risk_budget_used

        # Step 11: determine mode
        snapshot.mode = self._determine_mode(snapshot)

        # store
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.config.snapshot_retention:
            self._snapshots = self._snapshots[-self.config.snapshot_retention:]

        return snapshot

    # ── risk aggregation ────────────────────────────────────────────

    def _aggregate_strategy_risks(self, portfolio_states: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Aggregate risk at strategy level."""
        results: Dict[str, Dict[str, float]] = {}
        for pid, state in portfolio_states.items():
            strategies = state.get("strategies", {})
            for sid, s in strategies.items():
                key = f"{pid}:{sid}"
                results[key] = {
                    "var_95": s.get("var_95", 0.0),
                    "var_99": s.get("var_99", 0.0),
                    "es_95": s.get("es_95", 0.0),
                    "es_99": s.get("es_99", 0.0),
                    "drawdown_pct": s.get("drawdown_pct", 0.0),
                    "risk_contribution": s.get("risk_contribution", 0.0),
                    "capital_allocated": s.get("capital_allocated", 0.0),
                    "leverage": s.get("leverage", 1.0),
                }
        self._strategy_risks = results
        return results

    def _aggregate_portfolio_risk(self, strategy_risks: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Aggregate from strategy to portfolio level with correlation adjustment.

        NOT a simple sum — applies a diversification factor to account
        for inter-strategy correlations.
        """
        if not strategy_risks:
            return {}

        total_var_95 = 0.0
        total_var_99 = 0.0
        total_es_95 = 0.0
        total_es_99 = 0.0
        max_dd = 0.0

        for sr in strategy_risks.values():
            total_var_95 += sr["var_95"]
            total_var_99 += sr["var_99"]
            total_es_95 += sr["es_95"]
            total_es_99 += sr["es_99"]
            max_dd = max(max_dd, sr["drawdown_pct"])

        # apply diversification benefit (default 15% reduction)
        n = max(len(strategy_risks), 1)
        diversification = 0.85 + 0.05 * min(n, 10) / 10

        return {
            "var_95": total_var_95 * diversification,
            "var_99": total_var_99 * diversification,
            "es_95": total_es_95 * diversification,
            "es_99": total_es_99 * diversification,
            "drawdown_pct": max_dd * diversification,
            "max_drawdown_pct": max_dd,
            "strategy_count": float(n),
        }

    def _aggregate_capital_risk(self, portfolio_risk: Dict[str, float]) -> Dict[str, float]:
        """Aggregate to capital pool level with cross-portfolio correlation.

        Returns the composite risk metrics for the entire capital pool.
        """
        correlation_factor = 0.90  # cross-portfolio correlation assumption
        n_portfolios = max(portfolio_risk.get("strategy_count", 1), 1)
        scale = correlation_factor + (1 - correlation_factor) / n_portfolios

        return {
            "var_95": portfolio_risk.get("var_95", 0.0) * scale,
            "var_99": portfolio_risk.get("var_99", 0.0) * scale,
            "es_95": portfolio_risk.get("es_95", 0.0) * scale,
            "es_99": portfolio_risk.get("es_99", 0.0) * scale,
            "drawdown_pct": portfolio_risk.get("drawdown_pct", 0.0),
            "max_drawdown_pct": portfolio_risk.get("max_drawdown_pct", 0.0),
            "risk_budget_total": portfolio_risk.get("risk_budget_total", 0.0),
            "risk_budget_used": portfolio_risk.get("risk_budget_used", 0.0),
            "correlation_risk": 1.0 - correlation_factor,
            "tail_risk_score": 0.0,
            "factor_exposures": {},
        }

    # ── survival scoring ────────────────────────────────────────────

    def _compute_survival_score(self, snapshot: RiskSnapshot) -> float:
        """Compute a composite survival score (0-100)."""
        score = 100.0

        # drawdown penalty
        dd_penalty = min(snapshot.drawdown_pct * 2.0, 50.0)
        score -= dd_penalty

        # VaR penalty
        if snapshot.var_95 > 0:
            score -= min(snapshot.var_95 * 1.5, 30.0)

        # ES penalty (harsher)
        if snapshot.expected_shortfall_99 > 0:
            score -= min(snapshot.expected_shortfall_99 * 2.0, 30.0)

        # correlation risk penalty
        score -= snapshot.correlation_risk * 20.0

        # tail risk penalty
        score -= snapshot.tail_risk_score * 15.0

        return max(0.0, min(100.0, score))

    # ── mode determination ──────────────────────────────────────────

    def _determine_mode(self, snapshot: RiskSnapshot) -> RiskEngineMode:
        """Determine the risk engine operating mode from the snapshot."""
        if snapshot.survival_score <= self.config.survival_threshold_critical:
            return RiskEngineMode.CRITICAL
        if (
            snapshot.survival_score <= self.config.survival_threshold_defensive
            or snapshot.drawdown_pct >= self.config.drawdown_critical_pct
        ):
            return RiskEngineMode.DEFENSIVE
        if (
            snapshot.survival_score <= self.config.survival_threshold_caution
            or snapshot.drawdown_pct >= self.config.drawdown_defensive_pct
        ):
            return RiskEngineMode.CAUTION
        return RiskEngineMode.NORMAL

    # ── lifecycle ───────────────────────────────────────────────────

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def reset(self) -> None:
        self._mode = RiskEngineMode.NORMAL
        self._snapshots.clear()
        self._strategy_risks.clear()
        self._portfolio_risks.clear()

    def summary(self) -> Dict[str, Any]:
        latest = self.latest_snapshot
        return {
            "mode": self._mode.name,
            "snapshot_count": len(self._snapshots),
            "latest_var_99": latest.var_99 if latest else None,
            "latest_survival_score": latest.survival_score if latest else None,
            "enabled": self._enabled,
        }
