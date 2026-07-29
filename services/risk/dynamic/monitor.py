"""Dynamic Risk Monitor - real-time portfolio risk monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import time

from .models import (
    RiskSnapshot, PositionRisk, RiskLevel, RiskAction,
    MarketRegime, MarketRegimeSnapshot, RiskThresholds,
)


class RiskMonitor:
    """Real-time Dynamic Risk Monitor.

    Continuously monitors:
    - Portfolio-level risk metrics
    - Strategy-level risk
    - Position-level risk
    - Market regime risk

    Detects regime changes and triggers risk decisions.
    """

    def __init__(self, thresholds: Optional[RiskThresholds] = None):
        self.thresholds = thresholds or RiskThresholds()
        self.snapshots: List[RiskSnapshot] = []
        self.position_risks: Dict[str, PositionRisk] = {}
        self._last_regime = MarketRegime.NORMAL
        self._alerts: List[Dict] = []

    def collect_snapshot(
        self,
        portfolio_id: str,
        volatility: float,
        var_95: float,
        var_99: float,
        cvar_95: float,
        cvar_99: float,
        drawdown: float,
        max_drawdown: float,
        exposure: Dict[str, float],
        concentration_ratio: float,
        sharpe_ratio: float = 0.0,
        position_count: int = 0,
        leverage: float = 1.0,
    ) -> RiskSnapshot:
        """Collect a point-in-time risk snapshot.

        Args:
            portfolio_id: Portfolio identifier.
            volatility: Current portfolio volatility.
            var_95: 95% Value at Risk.
            var_99: 99% Value at Risk.
            cvar_95: 95% Conditional VaR.
            cvar_99: 99% Conditional VaR.
            drawdown: Current drawdown.
            max_drawdown: Maximum historical drawdown.
            exposure: Exposure breakdown by sector/asset.
            concentration_ratio: Portfolio concentration ratio.
            sharpe_ratio: Current Sharpe ratio.
            position_count: Number of positions.
            leverage: Current leverage.

        Returns:
            RiskSnapshot object.
        """
        risk_level = self._determine_risk_level(
            volatility, var_95, drawdown, concentration_ratio, sharpe_ratio)
        market_regime = self._detect_regime(volatility, drawdown, concentration_ratio)

        snapshot = RiskSnapshot(
            portfolio_id=portfolio_id,
            timestamp=datetime.utcnow(),
            volatility=volatility,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            drawdown=drawdown,
            max_drawdown=max_drawdown,
            exposure=exposure,
            concentration_ratio=concentration_ratio,
            sharpe_ratio=sharpe_ratio,
            risk_level=risk_level,
            market_regime=market_regime,
            position_count=position_count,
            leverage=leverage,
        )
        self.snapshots.append(snapshot)

        # Check for alerts
        self._check_thresholds(snapshot)

        # Track regime changes
        if market_regime != self._last_regime:
            self._alerts.append({
                "type": "REGIME_CHANGE",
                "from": self._last_regime.value,
                "to": market_regime.value,
                "timestamp": snapshot.timestamp.isoformat(),
                "severity": "HIGH" if market_regime == MarketRegime.CRISIS else "MEDIUM",
            })
            self._last_regime = market_regime

        return snapshot

    def update_position_risk(
        self,
        symbol: str,
        weight: float,
        notional: float,
        volatility: float,
        var_95: float,
        cvar_95: float,
        marginal_risk: float,
        risk_contribution_pct: float,
        beta: float = 1.0,
        correlation_to_portfolio: float = 0.7,
    ):
        """Update risk metrics for a single position.

        Args:
            symbol: Asset symbol.
            weight: Position weight.
            notional: Position notional value.
            volatility: Position volatility.
            var_95: Position 95% VaR.
            cvar_95: Position 95% CVaR.
            marginal_risk: Marginal risk contribution.
            risk_contribution_pct: Risk contribution percentage.
            beta: Position beta.
            correlation_to_portfolio: Correlation to portfolio.
        """
        self.position_risks[symbol] = PositionRisk(
            symbol=symbol,
            weight=weight,
            notional=notional,
            volatility=volatility,
            var_95=var_95,
            cvar_95=cvar_95,
            marginal_risk=marginal_risk,
            risk_contribution_pct=risk_contribution_pct,
            beta=beta,
            correlation_to_portfolio=correlation_to_portfolio,
        )

    def get_risk_decision(self) -> Dict[str, Any]:
        """Generate a risk-based action decision.

        Returns:
            Dict with risk decision recommendation.
        """
        if not self.snapshots:
            return {"action": "NONE", "reason": "No data"}

        latest = self.snapshots[-1]

        # Determine action based on risk level
        action_map = {
            RiskLevel.LOW: RiskAction.NONE,
            RiskLevel.NORMAL: RiskAction.NONE,
            RiskLevel.ELEVATED: RiskAction.REDUCE_POSITION,
            RiskLevel.HIGH: RiskAction.REDUCE_POSITION,
            RiskLevel.CRITICAL: RiskAction.STOP_TRADING,
        }
        action = action_map.get(latest.risk_level, RiskAction.NONE)

        # Compute reduction percentage
        reduction_pct = self._compute_reduction_pct(latest)

        # Target exposure adjustments
        target_exposure = self._compute_target_exposure(latest, reduction_pct)

        # Position-level adjustments
        position_adjustments = self._compute_position_adjustments(reduction_pct)

        return {
            "action": action.value,
            "risk_level": latest.risk_level.value,
            "market_regime": latest.market_regime.value,
            "reduction_pct": reduction_pct,
            "target_exposure": target_exposure,
            "position_adjustments": position_adjustments,
            "reason": self._generate_reason(latest, reduction_pct),
            "urgency": self._compute_urgency(latest),
            "top_risk_contributors": self._get_top_contributors(3),
        }

    def get_latest_snapshot(self) -> Optional[RiskSnapshot]:
        """Get the most recent risk snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    def get_risk_trend(self, metric: str = "volatility") -> List[float]:
        """Get trend of a specific risk metric."""
        attr_map = {
            "volatility": "volatility",
            "var_95": "var_95", "var": "var_95",
            "cvar": "cvar_95",
            "drawdown": "drawdown",
            "concentration": "concentration_ratio",
            "sharpe": "sharpe_ratio",
        }
        attr = attr_map.get(metric, metric)
        return [getattr(s, attr, 0.0) for s in self.snapshots]

    def get_alerts(self) -> List[Dict]:
        """Get all generated risk alerts."""
        return list(self._alerts)

    def get_regime(self) -> MarketRegime:
        """Get current market regime."""
        return self._last_regime

    def get_regime_assessment(self) -> MarketRegimeSnapshot:
        """Get full market regime assessment."""
        if not self.snapshots:
            return MarketRegimeSnapshot(
                regime=MarketRegime.NORMAL,
                confidence=0.5,
                indicators={},
                transition_probability={},
            )

        latest = self.snapshots[-1]
        indicators = {
            "volatility": latest.volatility,
            "drawdown": latest.drawdown,
            "concentration": latest.concentration_ratio,
        }

        # Transition probabilities (simplified)
        transition = {
            "to_normal": 0.5,
            "to_high_vol": 0.3,
            "to_crisis": 0.2,
        }

        return MarketRegimeSnapshot(
            regime=latest.market_regime,
            confidence=0.75,
            indicators=indicators,
            transition_probability=transition,
        )

    # ---- Internal helpers ----

    def _determine_risk_level(
        self, vol: float, var_95: float, dd: float, conc: float, sharpe: float,
    ) -> RiskLevel:
        """Classify overall risk level."""
        if (vol > self.thresholds.volatility_critical or
                dd > self.thresholds.drawdown_critical or
                abs(var_95) > self.thresholds.var_critical):
            return RiskLevel.CRITICAL
        if (vol > self.thresholds.volatility_high or
                dd > self.thresholds.drawdown_high or
                abs(var_95) > self.thresholds.var_high):
            return RiskLevel.HIGH
        if (vol > self.thresholds.max_volatility or
                dd > self.thresholds.drawdown_elevated or
                abs(var_95) > self.thresholds.var_elevated or
                conc > self.thresholds.max_concentration):
            return RiskLevel.ELEVATED
        if vol < self.thresholds.target_volatility * 0.5:
            return RiskLevel.LOW
        return RiskLevel.NORMAL

    def _detect_regime(self, vol: float, dd: float, conc: float) -> MarketRegime:
        """Detect current market regime."""
        if vol > 0.45 or dd > 0.25:
            return MarketRegime.CRISIS
        if vol > 0.25 or dd > 0.10:
            return MarketRegime.HIGH_VOL
        if vol < 0.08 and dd < 0.02:
            return MarketRegime.RECOVERY
        return MarketRegime.NORMAL

    def _compute_reduction_pct(self, snapshot: RiskSnapshot) -> float:
        """Compute percentage reduction needed."""
        if snapshot.risk_level in (RiskLevel.LOW, RiskLevel.NORMAL):
            return 0.0
        elif snapshot.risk_level == RiskLevel.ELEVATED:
            return 0.25
        elif snapshot.risk_level == RiskLevel.HIGH:
            return 0.50
        elif snapshot.risk_level == RiskLevel.CRITICAL:
            return 0.75
        return 0.0

    def _compute_target_exposure(self, snapshot: RiskSnapshot,
                                  reduction_pct: float) -> Dict[str, float]:
        """Compute target exposure after reduction."""
        target = {}
        for sector, exp in snapshot.exposure.items():
            target[sector] = exp * (1.0 - reduction_pct)
        return target

    def _compute_position_adjustments(self, reduction_pct: float) -> List[Dict[str, float]]:
        """Compute per-position adjustments."""
        if reduction_pct == 0:
            return []
        adjustments = []
        for symbol, risk in self.position_risks.items():
            adjustments.append({
                "symbol": symbol,
                "current_weight": risk.weight,
                "target_weight": risk.weight * (1.0 - reduction_pct),
                "reduction_pct": reduction_pct,
            })
        return adjustments

    def _generate_reason(self, snapshot: RiskSnapshot, reduction_pct: float) -> str:
        if reduction_pct == 0:
            return "Risk metrics within acceptable thresholds"
        reasons = []
        if snapshot.volatility > self.thresholds.max_volatility:
            reasons.append(f"volatility {snapshot.volatility:.1%} exceeds {self.thresholds.max_volatility:.1%}")
        if abs(snapshot.var_95) > self.thresholds.max_var_95:
            reasons.append(f"VaR95 {abs(snapshot.var_95):.1%} exceeds {self.thresholds.max_var_95:.1%}")
        if snapshot.drawdown > self.thresholds.max_drawdown:
            reasons.append(f"drawdown {snapshot.drawdown:.1%} exceeds {self.thresholds.max_drawdown:.1%}")
        return "; ".join(reasons) if reasons else f"Risk level: {snapshot.risk_level.value}"

    def _compute_urgency(self, snapshot: RiskSnapshot) -> int:
        """Compute urgency on 1-10 scale."""
        if snapshot.market_regime == MarketRegime.CRISIS:
            return 10
        if snapshot.risk_level == RiskLevel.CRITICAL:
            return 9
        if snapshot.risk_level == RiskLevel.HIGH:
            return 7
        if snapshot.risk_level == RiskLevel.ELEVATED:
            return 4
        return 1

    def _get_top_contributors(self, n: int = 3) -> List[Dict]:
        """Get top N risk-contributing positions."""
        sorted_risks = sorted(
            self.position_risks.values(),
            key=lambda r: r.risk_score(),
            reverse=True,
        )
        return [
            {
                "symbol": r.symbol,
                "weight": r.weight,
                "risk_contribution_pct": r.risk_contribution_pct,
                "volatility": r.volatility,
            }
            for r in sorted_risks[:n]
        ]

    def _check_thresholds(self, snapshot: RiskSnapshot):
        """Check if any risk thresholds are breached."""
        if snapshot.volatility > self.thresholds.volatility_high:
            self._alerts.append({
                "type": "VOLATILITY_HIGH",
                "value": snapshot.volatility,
                "threshold": self.thresholds.volatility_high,
                "timestamp": snapshot.timestamp.isoformat(),
            })
        if snapshot.drawdown > self.thresholds.drawdown_high:
            self._alerts.append({
                "type": "DRAWDOWN_HIGH",
                "value": snapshot.drawdown,
                "threshold": self.thresholds.drawdown_high,
                "timestamp": snapshot.timestamp.isoformat(),
            })
        if abs(snapshot.var_95) > self.thresholds.var_elevated:
            self._alerts.append({
                "type": "VAR_BREACH",
                "value": snapshot.var_95,
                "threshold": self.thresholds.var_elevated,
                "timestamp": snapshot.timestamp.isoformat(),
            })
