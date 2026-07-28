"""Cross-Asset Risk Monitor.

Monitors systemic risk conditions across the global multi-asset
ecosystem. Integrates volatility, correlation, liquidity, and
tail risk signals to assess portfolio vulnerability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .relationship import RiskRegime


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Systemic risk level."""

    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(str, Enum):
    """Risk category classification."""

    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    LIQUIDITY = "liquidity"
    CREDIT = "credit"
    CURRENCY = "currency"
    GEOPOLITICAL = "geopolitical"
    TAIL_RISK = "tail_risk"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class RiskComponent:
    """Individual risk component assessment.

    Attributes:
        category: Risk category.
        level: Risk severity level.
        score: Risk score [0.0, 1.0] (higher = more risk).
        weight: Component weight in overall assessment.
        signal: Specific risk signal description.
        metrics: Supporting metrics.
    """

    category: RiskCategory = RiskCategory.VOLATILITY
    level: RiskLevel = RiskLevel.MODERATE
    score: float = 0.5
    weight: float = 0.2
    signal: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class RiskMonitorResult:
    """Complete cross-asset risk assessment.

    Attributes:
        overall_level: Aggregate risk level.
        overall_score: Composite risk score [0.0, 1.0].
        components: Individual risk component assessments.
        current_regime: Current risk regime.
        max_drawdown_risk: Estimated max drawdown probability.
        tail_risk: Tail risk estimate.
        hedge_recommendation: Recommended hedging approach.
        description: Human-readable summary.
        confidence: Assessment confidence.
        timestamp: Assessment timestamp.
    """

    overall_level: RiskLevel = RiskLevel.MODERATE
    overall_score: float = 0.5
    components: list[RiskComponent] = field(default_factory=list)
    current_regime: RiskRegime = RiskRegime.NORMAL
    max_drawdown_risk: float = 0.1
    tail_risk: float = 0.05
    hedge_recommendation: str = ""
    description: str = ""
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_alarming(self) -> bool:
        return self.overall_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def requires_hedging(self) -> bool:
        return self.overall_level in (RiskLevel.ELEVATED, RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def risk_budget(self) -> float:
        """Suggested risk budget (fraction of max)."""
        return max(0.1, 1.0 - self.overall_score)

    @property
    def position_size_multiplier(self) -> float:
        """Position size multiplier based on risk level."""
        multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MODERATE: 0.8,
            RiskLevel.ELEVATED: 0.6,
            RiskLevel.HIGH: 0.4,
            RiskLevel.CRITICAL: 0.2,
        }
        return multipliers.get(self.overall_level, 0.5)


class CrossAssetRiskMonitor:
    """Monitors systemic cross-asset risk conditions.

    Aggregates risk signals from volatility, correlation breakdowns,
    liquidity compression, credit stress, and currency volatility
    to provide comprehensive portfolio risk assessment.

    Attributes:
        components: Active risk component assessments.
        vix_threshold_high: VIX level for elevated vol risk.
        vix_threshold_critical: VIX level for critical vol risk.
        credit_spread_critical: Credit spread for critical credit risk.
    """

    def __init__(self) -> None:
        self.components: list[RiskComponent] = []
        self.vix_threshold_high: float = 25.0
        self.vix_threshold_critical: float = 35.0
        self.credit_spread_critical: float = 3.0
        self._risk_history: list[float] = []

    # --- Component Assessment ---

    def assess_volatility_risk(self, vix: float,
                                equity_vol: float = 0.0) -> RiskComponent:
        """Assess volatility risk.

        Args:
            vix: VIX index level.
            equity_vol: Realized equity volatility.

        Returns:
            RiskComponent.
        """
        if vix >= self.vix_threshold_critical:
            level = RiskLevel.CRITICAL
            score = 0.9
        elif vix >= self.vix_threshold_high:
            level = RiskLevel.HIGH
            score = 0.7
        elif vix >= 20:
            level = RiskLevel.ELEVATED
            score = 0.5
        elif vix >= 15:
            level = RiskLevel.MODERATE
            score = 0.3
        else:
            level = RiskLevel.LOW
            score = 0.1

        desc = f"VIX={vix:.0f}"
        if equity_vol > 0:
            desc += f", RealVol={equity_vol:.1%}"

        return RiskComponent(
            category=RiskCategory.VOLATILITY,
            level=level,
            score=score,
            weight=0.20,
            signal=desc,
            metrics={"vix": vix, "realized_vol": equity_vol},
        )

    def assess_correlation_risk(self, avg_correlation: float,
                                 regime: str = "normal") -> RiskComponent:
        """Assess correlation/diversification risk.

        Args:
            avg_correlation: Average cross-asset correlation.
            regime: Correlation regime.

        Returns:
            RiskComponent.
        """
        if avg_correlation > 0.7 or regime == "crisis_convergence":
            level = RiskLevel.CRITICAL
            score = 0.9
        elif avg_correlation > 0.5:
            level = RiskLevel.HIGH
            score = 0.7
        elif avg_correlation > 0.3:
            level = RiskLevel.ELEVATED
            score = 0.5
        elif avg_correlation > 0.15:
            level = RiskLevel.MODERATE
            score = 0.3
        else:
            level = RiskLevel.LOW
            score = 0.15

        return RiskComponent(
            category=RiskCategory.CORRELATION,
            level=level,
            score=score,
            weight=0.15,
            signal=f"Corr={avg_correlation:.2f}, {regime}",
            metrics={"avg_correlation": avg_correlation},
        )

    def assess_liquidity_risk(self, bid_ask_spread: float = 0.0,
                               volume_change_pct: float = 0.0,
                               credit_spread: float = 1.0) -> RiskComponent:
        """Assess liquidity risk.

        Args:
            bid_ask_spread: Bid-ask spread widening.
            volume_change_pct: Volume change percentage.
            credit_spread: Credit spread level.

        Returns:
            RiskComponent.
        """
        score = 0.2
        signals: list[str] = []

        if credit_spread >= self.credit_spread_critical:
            score += 0.4
            signals.append(f"Credit spread wide ({credit_spread:.1f}%)")
        elif credit_spread >= 2.0:
            score += 0.25

        if bid_ask_spread > 0.001:
            score += 0.2
            signals.append("Widening bid-ask")

        if volume_change_pct < -20:
            score += 0.2
            signals.append(f"Volume declining {volume_change_pct:.0f}%")

        score = min(1.0, score)

        if score > 0.7:
            level = RiskLevel.CRITICAL
        elif score > 0.5:
            level = RiskLevel.HIGH
        elif score > 0.35:
            level = RiskLevel.ELEVATED
        elif score > 0.2:
            level = RiskLevel.MODERATE
        else:
            level = RiskLevel.LOW

        return RiskComponent(
            category=RiskCategory.LIQUIDITY,
            level=level,
            score=score,
            weight=0.15,
            signal=" | ".join(signals) if signals else "Liquidity normal",
            metrics={
                "credit_spread": credit_spread,
                "bid_ask": bid_ask_spread,
                "volume_change": volume_change_pct,
            },
        )

    def assess_currency_risk(self, dollar_trend: str,
                              em_currency_vol: float = 0.0) -> RiskComponent:
        """Assess currency volatility risk.

        Args:
            dollar_trend: USD trend direction.
            em_currency_vol: EM currency volatility.

        Returns:
            RiskComponent.
        """
        if dollar_trend == "strong_appreciation":
            level = RiskLevel.HIGH
            score = 0.75
        elif dollar_trend == "appreciation":
            level = RiskLevel.ELEVATED
            score = 0.55
        elif dollar_trend == "strong_depreciation":
            level = RiskLevel.ELEVATED
            score = 0.5
        elif dollar_trend == "depreciation":
            level = RiskLevel.MODERATE
            score = 0.3
        else:
            level = RiskLevel.LOW
            score = 0.15

        if em_currency_vol > 15:
            score = min(1.0, score + 0.2)
            if level == RiskLevel.LOW:
                level = RiskLevel.MODERATE

        return RiskComponent(
            category=RiskCategory.CURRENCY,
            level=level,
            score=score,
            weight=0.15,
            signal=f"USD {dollar_trend}" + (f", EM vol={em_currency_vol:.0f}" if em_currency_vol > 0 else ""),
            metrics={"dollar_trend": dollar_trend, "em_vol": em_currency_vol},
        )

    def assess_credit_risk(self, ig_spread: float,
                           hy_spread: float = 0.0) -> RiskComponent:
        """Assess credit market risk.

        Args:
            ig_spread: Investment grade credit spread.
            hy_spread: High yield credit spread.

        Returns:
            RiskComponent.
        """
        score = 0.15
        if ig_spread >= self.credit_spread_critical:
            score += 0.5
        elif ig_spread >= 2.0:
            score += 0.3
        if hy_spread > 5.0:
            score += 0.25
        score = min(1.0, score)

        if score > 0.7:
            level = RiskLevel.CRITICAL
        elif score > 0.5:
            level = RiskLevel.HIGH
        elif score > 0.35:
            level = RiskLevel.ELEVATED
        elif score > 0.2:
            level = RiskLevel.MODERATE
        else:
            level = RiskLevel.LOW

        return RiskComponent(
            category=RiskCategory.CREDIT,
            level=level,
            score=score,
            weight=0.15,
            signal=f"IG spread={ig_spread:.1f}%" + (f", HY={hy_spread:.1f}%" if hy_spread > 0 else ""),
            metrics={"ig_spread": ig_spread, "hy_spread": hy_spread},
        )

    def assess_tail_risk(self, skew: float = 0.0,
                          var_95: float = 0.0,
                          cvar: float = 0.0) -> RiskComponent:
        """Assess tail risk from options and statistical measures.

        Args:
            skew: Options skew.
            var_95: 95% Value at Risk.
            cvar: Conditional VaR.

        Returns:
            RiskComponent.
        """
        score = 0.15
        signals: list[str] = []

        if skew > 5:
            score += 0.3
            signals.append(f"Skew elevated ({skew:.0f})")
        if cvar > 5:
            score += 0.35
            signals.append(f"CVaR high ({cvar:.1f}%)")
        elif var_95 > 3:
            score += 0.2

        score = min(1.0, score)

        if score > 0.7:
            level = RiskLevel.CRITICAL
        elif score > 0.5:
            level = RiskLevel.HIGH
        elif score > 0.35:
            level = RiskLevel.ELEVATED
        else:
            level = RiskLevel.LOW if score < 0.2 else RiskLevel.MODERATE

        return RiskComponent(
            category=RiskCategory.TAIL_RISK,
            level=level,
            score=score,
            weight=0.20,
            signal=" | ".join(signals) if signals else "Tail risk normal",
            metrics={"skew": skew, "var_95": var_95, "cvar": cvar},
        )

    # --- Comprehensive Assessment ---

    def assess(self) -> RiskMonitorResult:
        """Run comprehensive cross-asset risk assessment.

        Returns:
            RiskMonitorResult with full risk analysis.
        """
        if not self.components:
            return RiskMonitorResult(
                overall_level=RiskLevel.MODERATE,
                overall_score=0.3,
                description="No risk components assessed",
                confidence=0.2,
            )

        # Weighted aggregate score
        total_weight = sum(c.weight for c in self.components)
        if total_weight == 0:
            return RiskMonitorResult(overall_level=RiskLevel.MODERATE, overall_score=0.3)

        weighted_score = sum(c.score * c.weight for c in self.components) / total_weight

        # Adjust for high-risk components
        high_risk_count = sum(1 for c in self.components if c.level in (RiskLevel.HIGH, RiskLevel.CRITICAL))
        if high_risk_count >= 3:
            weighted_score = min(1.0, weighted_score * 1.3)
        elif high_risk_count >= 2:
            weighted_score = min(1.0, weighted_score * 1.15)

        overall_level = self._classify_level(weighted_score)
        regime = self._classify_regime(self.components)
        confidence = self._compute_assessment_confidence(self.components)
        description = self._build_description(self.components, overall_level, regime)

        max_dd = self._estimate_max_drawdown(weighted_score)
        tail_risk = self._estimate_tail_risk(self.components)
        hedge_rec = self._recommend_hedge(self.components, overall_level, regime)

        self._risk_history.append(weighted_score)
        if len(self._risk_history) > 500:
            self._risk_history = self._risk_history[-500:]

        return RiskMonitorResult(
            overall_level=overall_level,
            overall_score=weighted_score,
            components=list(self.components),
            current_regime=regime,
            max_drawdown_risk=max_dd,
            tail_risk=tail_risk,
            hedge_recommendation=hedge_rec,
            description=description,
            confidence=confidence,
        )

    def run_full_assessment(self,
                             vix: float = 15.0,
                             avg_correlation: float = 0.2,
                             correlation_regime: str = "normal",
                             credit_spread: float = 1.0,
                             hy_spread: float = 0.0,
                             dollar_trend: str = "stable",
                             skew: float = 0.0,
                             var_95: float = 0.0) -> RiskMonitorResult:
        """Run full risk assessment with all parameters.

        Args:
            vix: VIX index level.
            avg_correlation: Average cross-asset correlation.
            correlation_regime: Correlation regime.
            credit_spread: IG credit spread.
            hy_spread: HY credit spread.
            dollar_trend: USD trend.
            skew: Options skew.
            var_95: 95% VaR.

        Returns:
            RiskMonitorResult.
        """
        self.components = [
            self.assess_volatility_risk(vix),
            self.assess_correlation_risk(avg_correlation, correlation_regime),
            self.assess_liquidity_risk(credit_spread=credit_spread),
            self.assess_currency_risk(dollar_trend),
            self.assess_credit_risk(credit_spread, hy_spread),
            self.assess_tail_risk(skew, var_95),
        ]
        return self.assess()

    # --- Risk Trend ---

    def get_risk_trend(self, window: int = 20) -> str:
        """Get trend of risk score over recent history.

        Args:
            window: Lookback window.

        Returns:
            Trend direction: rising/falling/stable.
        """
        if len(self._risk_history) < 2:
            return "stable"
        recent = self._risk_history[-window:] if len(self._risk_history) >= window else self._risk_history
        mid = len(recent) // 2
        first = sum(recent[:mid]) / mid
        second = sum(recent[mid:]) / max(1, len(recent) - mid)
        diff = second - first
        if diff > 0.05:
            return "rising"
        elif diff < -0.05:
            return "falling"
        return "stable"

    # --- Internal ---

    def _classify_level(self, score: float) -> RiskLevel:
        if score >= 0.8:
            return RiskLevel.CRITICAL
        elif score >= 0.6:
            return RiskLevel.HIGH
        elif score >= 0.4:
            return RiskLevel.ELEVATED
        elif score >= 0.25:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def _classify_regime(self, components: list[RiskComponent]) -> RiskRegime:
        vol_score = 0.0
        credit_score = 0.0
        corr_score = 0.0
        currency_score = 0.0

        for c in components:
            if c.category == RiskCategory.VOLATILITY:
                vol_score = c.score
            elif c.category == RiskCategory.CREDIT:
                credit_score = c.score
            elif c.category == RiskCategory.CORRELATION:
                corr_score = c.score
            elif c.category == RiskCategory.CURRENCY:
                currency_score = c.score

        if vol_score > 0.6 and corr_score > 0.5:
            return RiskRegime.RISK_OFF
        if credit_score > 0.5 and vol_score > 0.3:
            return RiskRegime.FLIGHT_TO_QUALITY
        if currency_score > 0.5:
            return RiskRegime.INFLATION_HEDGE if currency_score > 0.6 else RiskRegime.RISK_ON
        if vol_score < 0.3 and credit_score < 0.3:
            return RiskRegime.RISK_ON
        return RiskRegime.NORMAL

    def _compute_assessment_confidence(self, components: list[RiskComponent]) -> float:
        if not components:
            return 0.2
        confidence = 0.3
        # Components with clear signals increase confidence
        clear_signals = sum(1 for c in components if c.level != RiskLevel.MODERATE)
        confidence += 0.1 * min(3, clear_signals)
        # Components with metrics increase confidence
        with_metrics = sum(1 for c in components if len(c.metrics) >= 2)
        confidence += 0.1 * min(3, with_metrics)
        return min(1.0, confidence)

    def _build_description(self, components: list[RiskComponent],
                           level: RiskLevel, regime: RiskRegime) -> str:
        critical_components = [c for c in components if c.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)]
        parts = [f"Risk: {level.value} ({regime.value})"]
        for c in critical_components[:3]:
            parts.append(f"{c.category.value}: {c.level.value}")
        if not critical_components:
            parts.append("No critical risk signals")
        return " | ".join(parts)

    def _estimate_max_drawdown(self, risk_score: float) -> float:
        """Estimate max drawdown probability from risk score."""
        base = risk_score * 0.3
        # Non-linear: risk accelerates at higher levels
        if risk_score > 0.6:
            base *= 1.5
        return min(0.5, base)

    def _estimate_tail_risk(self, components: list[RiskComponent]) -> float:
        tail = next((c for c in components if c.category == RiskCategory.TAIL_RISK), None)
        if tail:
            return tail.score
        # Estimate from other components
        vol = next((c for c in components if c.category == RiskCategory.VOLATILITY), None)
        corr = next((c for c in components if c.category == RiskCategory.CORRELATION), None)
        est = 0.05
        if vol:
            est += vol.score * 0.05
        if corr and corr.score > 0.5:
            est += 0.05
        return min(0.3, est)

    def _recommend_hedge(self, components: list[RiskComponent],
                          level: RiskLevel, regime: RiskRegime) -> str:
        if level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            return "Hedge heavily: long VIX, long puts, reduce equities, add gold/bonds"
        elif level == RiskLevel.ELEVATED:
            return "Moderate hedging: raise cash 10-15%, add tail hedges, reduce leverage"
        elif regime == RiskRegime.RISK_OFF:
            return "Defensive allocation: overweight bonds, gold, and quality factors"
        elif regime == RiskRegime.FLIGHT_TO_QUALITY:
            return "Rotate to treasuries and investment grade, reduce EM exposure"
        return "Standard hedging: maintain 5-10% tail risk hedge allocation"

    def clear(self) -> None:
        self.components.clear()
        self._risk_history.clear()
