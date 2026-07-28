"""Cross-Asset Signal Generator.

Synthesizes signals from all intelligence engines (equity-bond, dollar,
commodity, crypto, correlation) into unified trading and allocation
signals for target portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SignalPriority(str, Enum):
    """Signal priority level."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class SignalAction(str, Enum):
    """Recommended action from signal."""

    OVERWEIGHT = "overweight"
    MARKET_WEIGHT = "market_weight"
    UNDERWEIGHT = "underweight"
    HEDGE = "hedge"
    REDUCE = "reduce"
    EXIT = "exit"
    MONITOR = "monitor"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class SignalResult:
    """A generated cross-asset signal.

    Attributes:
        signal_id: Unique signal identifier.
        target_asset: Asset this signal applies to.
        action: Recommended action.
        priority: Signal priority level.
        score: Composite signal score [-1.0, 1.0].
        confidence: Signal confidence [0.0, 1.0].
        source_signals: Contributing sub-signals.
        rationale: Human-readable explanation.
        horizon: Signal horizon in days.
        urgency: Immediate action needed flag.
        timestamp: Signal generation time.
        metadata: Additional context.
    """

    signal_id: str = ""
    target_asset: str = ""
    action: SignalAction = SignalAction.MONITOR
    priority: SignalPriority = SignalPriority.LOW
    score: float = 0.0
    confidence: float = 0.5
    source_signals: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    horizon: int = 5
    urgency: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return (self.confidence >= 0.5 and self.action in (
            SignalAction.OVERWEIGHT,
            SignalAction.UNDERWEIGHT,
            SignalAction.HEDGE,
            SignalAction.REDUCE,
            SignalAction.EXIT,
        ))

    @property
    def direction(self) -> int:
        """Signal direction: 1=bullish, -1=bearish, 0=neutral."""
        if self.action == SignalAction.OVERWEIGHT:
            return 1
        elif self.action in (SignalAction.UNDERWEIGHT, SignalAction.REDUCE, SignalAction.EXIT):
            return -1
        return 0

    @property
    def absolute_score(self) -> float:
        return abs(self.score) * self.confidence

    @property
    def risk_budget_adjustment(self) -> float:
        """Suggested risk budget multiplier (0.0 to 2.0)."""
        return 1.0 + self.score * self.confidence


class CrossAssetSignalGenerator:
    """Generates unified trading signals from cross-asset analysis.

    Combines inputs from equity-bond, dollar, commodity, crypto,
    correlation, and rotation engines into coherent, actionable
    trading and allocation signals.

    Attributes:
        signal_threshold: Minimum absolute score for signal generation.
        confidence_threshold: Minimum confidence for actionable signal.
        sub_signals: Registry of sub-signal contributions.
        signal_history: History of generated signals.
    """

    def __init__(self) -> None:
        self.signal_threshold: float = 0.3
        self.confidence_threshold: float = 0.5
        self.sub_signals: dict[str, dict[str, Any]] = {}
        self.signal_history: list[SignalResult] = []

    # --- Sub-Signal Registration ---

    def register_equity_bond(self, pressure: str, valuation: str,
                             confidence: float = 0.5) -> None:
        """Register equity-bond signal contribution."""
        pressure_score = {
            "LOW": 0.5, "NEUTRAL": 0.0, "HIGH": -0.3, "CRITICAL": -0.7,
        }.get(pressure, 0.0)
        val_score = {
            "CHEAP": 0.6, "ATTRACTIVE": 0.3, "FAIR": 0.0,
            "RICH": -0.3, "OVERVAULED": -0.6,
        }.get(valuation, 0.0)

        self.sub_signals["equity_bond"] = {
            "score": (pressure_score * 0.6 + val_score * 0.4),
            "confidence": confidence,
            "weight": 0.15,
            "detail": f"Pressure:{pressure} | Val:{valuation}",
        }

    def register_dollar(self, trend: str, impact_gold: str,
                        confidence: float = 0.5) -> None:
        """Register dollar signal contribution."""
        trend_score = {
            "strong_depreciation": 0.6,
            "depreciation": 0.3,
            "stable": 0.0,
            "appreciation": -0.3,
            "strong_appreciation": -0.6,
        }.get(trend, 0.0)

        # Invert for equities: weak dollar = bullish
        self.sub_signals["dollar"] = {
            "score": trend_score,
            "confidence": confidence,
            "weight": 0.20,
            "detail": f"Trend:{trend} | Gold:{impact_gold}",
        }

    def register_commodity(self, gold_signal: str, copper_signal: str,
                           oil_signal: str, confidence: float = 0.5) -> None:
        """Register commodity signal contribution."""
        _m = {"BULLISH": 0.4, "NEUTRAL": 0.0, "BEARISH": -0.4}

        gold_score = _m.get(gold_signal, 0.0) * 0.3  # gold = risk-off
        copper_score = _m.get(copper_signal, 0.0) * 0.4  # copper = growth
        oil_score = _m.get(oil_signal, 0.0) * 0.3

        # Invert gold: bullish gold = bearish equities (risk-off)
        self.sub_signals["commodity"] = {
            "score": (-gold_score * 0.3 + copper_score * 0.4 + oil_score * 0.3),
            "confidence": confidence,
            "weight": 0.15,
            "detail": f"Gold:{gold_signal} | Cu:{copper_signal} | Oil:{oil_signal}",
        }

    def register_crypto(self, signal: str, risk_appetite: str,
                        confidence: float = 0.5) -> None:
        """Register crypto signal contribution."""
        crypto_score = {
            "BULLISH": 0.5, "NEUTRAL": 0.0, "BEARISH": -0.5,
        }.get(signal, 0.0)

        risk_modifier = {
            "risk_seeking": 0.2,
            "risk_neutral": 0.0,
            "risk_averse": -0.2,
            "extreme_fear": -0.4,
        }.get(risk_appetite, 0.0)

        self.sub_signals["crypto"] = {
            "score": crypto_score + risk_modifier,
            "confidence": confidence,
            "weight": 0.10,
            "detail": f"Signal:{signal} | Risk:{risk_appetite}",
        }

    def register_correlation(self, avg_correlation: float,
                             diversification_score: float,
                             regime: str = "normal",
                             confidence: float = 0.5) -> None:
        """Register correlation signal contribution."""
        # High correlation = diversification failing = negative signal
        corr_score = -avg_correlation * 0.5 + diversification_score * 0.5

        regime_modifier = {
            "crisis_convergence": -0.3,
            "decoupling": 0.1,
            "inverse": -0.1,
            "normal": 0.0,
        }.get(regime, 0.0)

        self.sub_signals["correlation"] = {
            "score": corr_score + regime_modifier,
            "confidence": confidence,
            "weight": 0.10,
            "detail": f"AvgCorr={avg_correlation:.2f} | Div={diversification_score:.2f} | {regime}",
        }

    def register_rotation(self, regime: str, confidence: float = 0.5) -> None:
        """Register rotation signal contribution."""
        regime_score = {
            "risk_seeking": 0.6,
            "growth_favoring": 0.4,
            "value_favoring": 0.1,
            "neutral": 0.0,
            "inflation_protection": -0.1,
            "defensive": -0.5,
        }.get(regime, 0.0)

        self.sub_signals["rotation"] = {
            "score": regime_score,
            "confidence": confidence,
            "weight": 0.15,
            "detail": f"Regime:{regime}",
        }

    # --- Signal Generation ---

    def generate(self, target_asset: str = "equity_portfolio",
                 horizon: int = 5) -> SignalResult:
        """Generate unified cross-asset signal.

        Args:
            target_asset: Target asset/portfolio.
            horizon: Signal horizon in days.

        Returns:
            SignalResult with action recommendation.
        """
        if not self.sub_signals:
            return SignalResult(
                signal_id="",
                target_asset=target_asset,
                action=SignalAction.MONITOR,
                priority=SignalPriority.LOW,
                score=0.0,
                confidence=0.2,
                source_signals={},
                rationale="No sub-signals registered",
                horizon=horizon,
            )

        # Weighted composite score
        total_weight = 0.0
        weighted_score = 0.0
        confidences: list[float] = []
        source_scores: dict[str, float] = {}

        for name, data in self.sub_signals.items():
            weight = data.get("weight", 0.1)
            score = data.get("score", 0.0)
            conf = data.get("confidence", 0.5)

            weighted_score += score * weight * conf
            total_weight += weight * conf
            confidences.append(conf)
            source_scores[name] = score

        composite_score = weighted_score / total_weight if total_weight > 0 else 0.0
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.2

        # Clamp
        composite_score = max(-1.0, min(1.0, composite_score))
        overall_confidence = min(1.0, overall_confidence)

        # Derive action
        action = self._derive_action(composite_score, overall_confidence)
        priority = self._derive_priority(composite_score, overall_confidence)
        rationale = self._build_rationale(composite_score, action, source_scores)
        urgency = priority in (SignalPriority.CRITICAL, SignalPriority.HIGH)

        signal_id = f"CAS-{target_asset}-{datetime.now():%Y%m%d%H%M}"

        result = SignalResult(
            signal_id=signal_id,
            target_asset=target_asset,
            action=action,
            priority=priority,
            score=composite_score,
            confidence=overall_confidence,
            source_signals=source_scores,
            rationale=rationale,
            horizon=horizon,
            urgency=urgency,
        )

        self.signal_history.append(result)
        if len(self.signal_history) > 500:
            self.signal_history = self.signal_history[-500:]

        return result

    def generate_for_asset(self, target_asset: str,
                           equity_bond_pressure: str = "NEUTRAL",
                           equity_bond_val: str = "FAIR",
                           dollar_trend: str = "stable",
                           dollar_gold: str = "neutral",
                           gold_signal: str = "NEUTRAL",
                           copper_signal: str = "NEUTRAL",
                           oil_signal: str = "NEUTRAL",
                           crypto_signal: str = "NEUTRAL",
                           crypto_risk: str = "risk_neutral",
                           avg_correlation: float = 0.3,
                           diversification: float = 0.5,
                           corr_regime: str = "normal",
                           rotation_regime: str = "neutral",
                           horizon: int = 5) -> SignalResult:
        """Generate signal with all sub-components provided explicitly.

        This is the primary interface for the service layer. All
        intelligence engines pass their results through this method.

        Args:
            target_asset: Target asset identifier.
            equity_bond_pressure: Equity pressure level.
            ...: All sub-signal parameters.

        Returns:
            SignalResult.
        """
        self.clear_sub_signals()

        self.register_equity_bond(equity_bond_pressure, equity_bond_val)
        self.register_dollar(dollar_trend, dollar_gold)
        self.register_commodity(gold_signal, copper_signal, oil_signal)
        self.register_crypto(crypto_signal, crypto_risk)
        self.register_correlation(avg_correlation, diversification, corr_regime)
        self.register_rotation(rotation_regime)

        return self.generate(target_asset, horizon)

    # --- Signal History ---

    def get_latest_signal(self) -> SignalResult | None:
        """Get the most recent signal."""
        return self.signal_history[-1] if self.signal_history else None

    def get_signal_trend(self, window: int = 10) -> str:
        """Get trend of recent signals."""
        recent = self.signal_history[-window:] if len(self.signal_history) >= window else self.signal_history
        if len(recent) < 2:
            return "stable"
        scores = [s.score for s in recent]
        mid = len(scores) // 2
        first = sum(scores[:mid]) / mid
        second = sum(scores[mid:]) / max(1, len(scores) - mid)
        diff = second - first
        if diff > 0.15:
            return "improving"
        elif diff < -0.15:
            return "deteriorating"
        return "stable"

    # --- Allocation Weights ---

    def get_allocation_multiplier(self, asset: str = "equities") -> float:
        """Get suggested allocation multiplier for an asset class.

        Args:
            asset: Asset class name.

        Returns:
            Multiplier around 1.0: <1 underweight, >1 overweight.
        """
        latest = self.get_latest_signal()
        if not latest or latest.confidence < self.confidence_threshold:
            return 1.0
        return 1.0 + latest.score * latest.confidence * 0.5

    # --- Internal ---

    def _derive_action(self, score: float, confidence: float) -> SignalAction:
        if confidence < self.confidence_threshold:
            return SignalAction.MONITOR
        if score > 0.5:
            return SignalAction.OVERWEIGHT
        elif score > 0.2:
            return SignalAction.MARKET_WEIGHT
        elif score < -0.5:
            return SignalAction.REDUCE
        elif score < -0.2:
            return SignalAction.UNDERWEIGHT
        return SignalAction.MONITOR

    def _derive_priority(self, score: float, confidence: float) -> SignalPriority:
        if confidence < 0.4:
            return SignalPriority.LOW
        abs_score = abs(score)
        if abs_score > 0.7 and confidence > 0.7:
            return SignalPriority.CRITICAL
        elif abs_score > 0.4:
            return SignalPriority.HIGH
        elif abs_score > 0.2:
            return SignalPriority.MEDIUM
        return SignalPriority.LOW

    def _build_rationale(self, score: float, action: SignalAction,
                         source_scores: dict[str, float]) -> str:
        direction = "bullish" if score > 0 else "bearish"
        parts = [f"Composite {direction} ({score:+.2f})"]

        # Highlight strongest contributors
        sorted_sources = sorted(source_scores.items(), key=lambda x: abs(x[1]), reverse=True)
        for name, val in sorted_sources[:3]:
            if abs(val) > 0.1:
                parts.append(f"{name}:{val:+.2f}")

        parts.append(f"→ {action.value}")
        return " | ".join(parts)

    def clear_sub_signals(self) -> None:
        self.sub_signals.clear()

    def clear(self) -> None:
        self.sub_signals.clear()
        self.signal_history.clear()
