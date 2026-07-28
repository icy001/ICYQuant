"""Crisis Early Warning System.

Multi-indicator early warning system that detects crisis precursors
before they become full-blown market events. Uses leading indicators,
anomaly detection, and pattern recognition to provide actionable
warnings with quantified lead time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CrisisPhase(str, Enum):
    """Market crisis lifecycle phases."""

    NORMAL = "normal"
    BUILDUP = "buildup"
    PRECURSOR = "precursor"
    TRIGGER = "trigger"
    ACCELERATION = "acceleration"
    STABILIZATION = "stabilization"


class WarningSeverity(str, Enum):
    """Early warning severity levels."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class WarningType(str, Enum):
    """Type of early warning signal."""

    VOLATILITY_BREAKOUT = "volatility_breakout"
    CORRELATION_SPIKE = "correlation_spike"
    LIQUIDITY_FREEZE = "liquidity_freeze"
    CREDIT_STRESS = "credit_stress"
    MOMENTUM_CRASH = "momentum_crash"
    SAFE_HAVEN_SURGE = "safe_haven_surge"
    TAIL_RISK_EXPANSION = "tail_risk_expansion"
    MARGIN_PRESSURE = "margin_pressure"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class CrisisWarning:
    """An early warning signal for impending market stress.

    Attributes:
        warning_id: Unique warning identifier.
        warning_type: Type of warning signal.
        severity: Severity classification.
        trigger_value: The value that triggered the warning.
        threshold: Activation threshold.
        lead_time_days: Estimated lead time before event.
        description: Human-readable description.
        recommended_action: Suggested defensive action.
        confidence: Warning confidence [0.0, 1.0].
        timestamp: Warning generation time.
        metadata: Additional context.
    """

    warning_id: str = ""
    warning_type: WarningType = WarningType.VOLATILITY_BREAKOUT
    severity: WarningSeverity = WarningSeverity.LOW
    trigger_value: float = 0.0
    threshold: float = 0.0
    lead_time_days: int = 5
    description: str = ""
    recommended_action: str = ""
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_urgent(self) -> bool:
        return self.severity in (WarningSeverity.HIGH, WarningSeverity.CRITICAL)

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.5 and self.severity != WarningSeverity.LOW


@dataclass
class CrisisWarningResult:
    """Result of crisis early warning analysis.

    Attributes:
        current_phase: Current crisis lifecycle phase.
        warnings: Active warning signals.
        composite_alert: Overall alert level.
        aggregate_severity: Average warning severity.
        description: Human-readable summary.
        confidence: Analysis confidence.
        estimated_lead_time: Estimated time to crisis (worst case).
        timestamp: Analysis timestamp.
    """

    current_phase: CrisisPhase = CrisisPhase.NORMAL
    warnings: list[CrisisWarning] = field(default_factory=list)
    composite_alert: float = 0.0  # 0.0 = no alert, 1.0 = maximum alert
    aggregate_severity: WarningSeverity = WarningSeverity.LOW
    description: str = ""
    confidence: float = 0.5
    estimated_lead_time: int = 30
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def active_warnings(self) -> list[CrisisWarning]:
        return [w for w in self.warnings if w.is_actionable]

    @property
    def urgent_warnings(self) -> list[CrisisWarning]:
        return [w for w in self.warnings if w.is_urgent]

    @property
    def should_defend(self) -> bool:
        return self.composite_alert >= 0.5

    @property
    def defense_level(self) -> float:
        """Defense positioning: 0=none, 1=full defense."""
        if self.composite_alert >= 0.8:
            return 0.9
        elif self.composite_alert >= 0.6:
            return 0.6
        elif self.composite_alert >= 0.4:
            return 0.3
        return 0.0


class CrisisEarlyWarningSystem:
    """Multi-indicator crisis early warning system.

    Monitors leading indicators including volatility regimes, correlation
    spikes, liquidity conditions, credit stress, and safe-haven demand
    to detect crisis precursors with quantified lead time estimates.

    Attributes:
        warning_indicators: Per-indicator history.
        vol_threshold: Volatility breakout threshold.
        corr_threshold: Correlation spike threshold.
        credit_threshold: Credit stress threshold.
    """

    def __init__(self) -> None:
        self.warning_indicators: dict[str, list[float]] = {}
        self.vol_threshold: float = 25.0  # VIX
        self.corr_threshold: float = 0.7
        self.credit_threshold: float = 2.5  # spread %
        self._warning_counter: int = 0

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyze(self,
                vix: float = 15.0,
                vix_change: float = 0.0,
                avg_correlation: float = 0.2,
                credit_spread: float = 1.0,
                credit_change: float = 0.0,
                liquidity_stress: float = 0.1,
                safe_haven_demand: float = 0.0,
                market_breadth: float = 0.5) -> CrisisWarningResult:
        """Run crisis early warning analysis.

        Args:
            vix: VIX index level.
            vix_change: VIX daily change (ratio).
            avg_correlation: Average cross-asset correlation.
            credit_spread: IG credit spread.
            credit_change: Credit spread daily change.
            liquidity_stress: Liquidity stress (0-1).
            safe_haven_demand: Safe haven flow indicator (0-1).
            market_breadth: Market breadth indicator (0-1).

        Returns:
            CrisisWarningResult with warnings and phase.
        """
        warnings: list[CrisisWarning] = []

        # Volatility breakout
        warnings.extend(self._detect_volatility_breakout(vix, vix_change))

        # Correlation spike
        warnings.extend(self._detect_correlation_spike(avg_correlation))

        # Credit stress
        warnings.extend(self._detect_credit_stress(credit_spread, credit_change))

        # Liquidity freeze
        warnings.extend(self._detect_liquidity_freeze(liquidity_stress))

        # Safe haven surge
        warnings.extend(self._detect_safe_haven_surge(safe_haven_demand))

        # Momentum crash (market breadth collapse)
        warnings.extend(self._detect_momentum_crash(market_breadth))

        # Composite alert
        composite = self._compute_composite_alert(warnings)
        severity = self._classify_severity(composite)
        phase = self._determine_phase(warnings, composite)
        confidence = self._compute_warning_confidence(warnings, composite)
        description = self._generate_description(warnings, phase, composite)
        lead_time = self._estimate_lead_time(warnings, composite)

        return CrisisWarningResult(
            current_phase=phase,
            warnings=warnings,
            composite_alert=composite,
            aggregate_severity=severity,
            description=description,
            confidence=confidence,
            estimated_lead_time=lead_time,
        )

    # ------------------------------------------------------------------
    # Individual Detectors
    # ------------------------------------------------------------------

    def _detect_volatility_breakout(self, vix: float, vix_change: float) -> list[CrisisWarning]:
        warnings: list[CrisisWarning] = []
        if vix >= 35.0:
            warnings.append(self._create_warning(
                WarningType.VOLATILITY_BREAKOUT, WarningSeverity.CRITICAL,
                vix, 35.0, 1,
                f"VIX={vix:.0f} – extreme volatility regime",
                "Reduce all risk positions, increase cash allocation",
            ))
        elif vix >= self.vol_threshold:
            severity = WarningSeverity.HIGH if vix_change > 0.1 else WarningSeverity.MODERATE
            warnings.append(self._create_warning(
                WarningType.VOLATILITY_BREAKOUT, severity,
                vix, self.vol_threshold, 5,
                f"VIX={vix:.0f} – volatility breakout",
                "Reduce leverage, add tail hedges",
            ))
        return warnings

    def _detect_correlation_spike(self, avg_corr: float) -> list[CrisisWarning]:
        warnings: list[CrisisWarning] = []
        if avg_corr >= 0.85:
            warnings.append(self._create_warning(
                WarningType.CORRELATION_SPIKE, WarningSeverity.CRITICAL,
                avg_corr, 0.85, 3,
                f"Correlation={avg_corr:.2f} – diversification collapsed",
                "Seek uncorrelated assets, raise cash",
            ))
        elif avg_corr >= self.corr_threshold:
            warnings.append(self._create_warning(
                WarningType.CORRELATION_SPIKE, WarningSeverity.HIGH,
                avg_corr, self.corr_threshold, 7,
                f"Correlation={avg_corr:.2f} – diversification at risk",
                "Reduce crowded positions, add gold/bonds",
            ))
        return warnings

    def _detect_credit_stress(self, credit_spread: float,
                              credit_change: float) -> list[CrisisWarning]:
        warnings: list[CrisisWarning] = []
        if credit_spread >= 3.0:
            warnings.append(self._create_warning(
                WarningType.CREDIT_STRESS, WarningSeverity.CRITICAL,
                credit_spread, 3.0, 10,
                f"Credit spread={credit_spread:.1f}% – severe credit stress",
                "Exit high-yield, move to IG/short duration",
            ))
        elif credit_spread >= self.credit_threshold:
            severity = WarningSeverity.HIGH if credit_change > 0.2 else WarningSeverity.MODERATE
            warnings.append(self._create_warning(
                WarningType.CREDIT_STRESS, severity,
                credit_spread, self.credit_threshold, 14,
                f"Credit spread={credit_spread:.1f}% widening",
                "Reduce credit exposure, add quality bonds",
            ))
        return warnings

    def _detect_liquidity_freeze(self, liquidity_stress: float) -> list[CrisisWarning]:
        warnings: list[CrisisWarning] = []
        if liquidity_stress >= 0.7:
            warnings.append(self._create_warning(
                WarningType.LIQUIDITY_FREEZE, WarningSeverity.CRITICAL,
                liquidity_stress, 0.7, 2,
                f"Liquidity stress={liquidity_stress:.1%} – near freeze",
                "Suspend trading, maintain maximum liquidity",
            ))
        elif liquidity_stress >= 0.4:
            warnings.append(self._create_warning(
                WarningType.LIQUIDITY_FREEZE, WarningSeverity.HIGH,
                liquidity_stress, 0.4, 5,
                f"Liquidity deteriorating ({liquidity_stress:.1%})",
                "Reduce position sizes, increase limit order usage",
            ))
        return warnings

    def _detect_safe_haven_surge(self, safe_haven_demand: float) -> list[CrisisWarning]:
        warnings: list[CrisisWarning] = []
        if safe_haven_demand >= 0.8:
            warnings.append(self._create_warning(
                WarningType.SAFE_HAVEN_SURGE, WarningSeverity.CRITICAL,
                safe_haven_demand, 0.8, 3,
                "Massive rotation into safe havens (gold/bonds/cash)",
                "Follow flow – reduce risk assets, add gold",
            ))
        elif safe_haven_demand >= 0.5:
            warnings.append(self._create_warning(
                WarningType.SAFE_HAVEN_SURGE, WarningSeverity.MODERATE,
                safe_haven_demand, 0.5, 7,
                "Safe haven demand increasing",
                "Consider partial reallocation to defensive assets",
            ))
        return warnings

    def _detect_momentum_crash(self, market_breadth: float) -> list[CrisisWarning]:
        warnings: list[CrisisWarning] = []
        if market_breadth <= 0.2:
            warnings.append(self._create_warning(
                WarningType.MOMENTUM_CRASH, WarningSeverity.CRITICAL,
                market_breadth, 0.2, 5,
                f"Market breadth={market_breadth:.2f} – momentum crash",
                "Avoid momentum strategies, position for mean reversion",
            ))
        elif market_breadth <= 0.35:
            warnings.append(self._create_warning(
                WarningType.MOMENTUM_CRASH, WarningSeverity.HIGH,
                market_breadth, 0.35, 10,
                f"Market breadth narrowing ({market_breadth:.2f})",
                "Reduce momentum factor exposure",
            ))
        return warnings

    # ------------------------------------------------------------------
    # Composite
    # ------------------------------------------------------------------

    def _compute_composite_alert(self, warnings: list[CrisisWarning]) -> float:
        if not warnings:
            return 0.0
        severity_scores = {
            WarningSeverity.LOW: 0.2,
            WarningSeverity.MODERATE: 0.4,
            WarningSeverity.HIGH: 0.65,
            WarningSeverity.CRITICAL: 0.85,
        }
        total = 0.0
        weights = 0.0
        for w in warnings:
            sev = severity_scores.get(w.severity, 0.2)
            total += sev * w.confidence
            weights += w.confidence
        if weights == 0:
            return 0.0
        # Non-linear composite: multiple warnings compound
        base = total / weights
        multiplier = min(1.5, 1.0 + len(warnings) * 0.1)
        return min(1.0, base * multiplier)

    def _classify_severity(self, composite: float) -> WarningSeverity:
        if composite >= 0.8:
            return WarningSeverity.CRITICAL
        elif composite >= 0.6:
            return WarningSeverity.HIGH
        elif composite >= 0.3:
            return WarningSeverity.MODERATE
        return WarningSeverity.LOW

    def _determine_phase(self, warnings: list[CrisisWarning],
                         composite: float) -> CrisisPhase:
        if composite >= 0.7:
            return CrisisPhase.TRIGGER
        elif composite >= 0.5:
            return CrisisPhase.PRECURSOR
        elif composite >= 0.3 and len(warnings) >= 3:
            return CrisisPhase.BUILDUP
        elif len(warnings) >= 1:
            return CrisisPhase.BUILDUP
        return CrisisPhase.NORMAL

    def _compute_warning_confidence(self, warnings: list[CrisisWarning],
                                      composite: float) -> float:
        if not warnings:
            return 0.2
        avg_conf = sum(w.confidence for w in warnings) / len(warnings)
        # Higher composite = higher confidence
        return min(1.0, avg_conf * 0.7 + composite * 0.3)

    def _estimate_lead_time(self, warnings: list[CrisisWarning],
                            composite: float) -> int:
        """Estimate worst-case lead time before crisis event."""
        if not warnings:
            return 60
        min_lead = min(w.lead_time_days for w in warnings)
        # In crisis, lead time is short; in buildup, long
        if composite >= 0.7:
            return max(1, min_lead // 2)
        elif composite >= 0.5:
            return max(3, min_lead)
        return max(7, min_lead)

    def _generate_description(self, warnings: list[CrisisWarning],
                                phase: CrisisPhase, composite: float) -> str:
        if phase == CrisisPhase.NORMAL:
            return "No crisis signals detected – conditions normal"
        sev_labels = {
            CrisisPhase.BUILDUP: "Buildup",
            CrisisPhase.PRECURSOR: "Precursor",
            CrisisPhase.TRIGGER: "Trigger",
            CrisisPhase.ACCELERATION: "Acceleration",
            CrisisPhase.STABILIZATION: "Stabilization",
        }
        label = sev_labels.get(phase, "Unknown")
        w_types = [w.warning_type.value for w in warnings[:3] if w.is_urgent]
        if w_types:
            return f"{label} phase (alert={composite:.2f}). Warnings: {', '.join(w_types)}"
        return f"{label} phase (alert={composite:.2f}). {len(warnings)} warning(s) active"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_warning(self, wtype: WarningType, severity: WarningSeverity,
                        trigger: float, threshold: float, lead_days: int,
                        description: str, action: str) -> CrisisWarning:
        self._warning_counter += 1
        conf_map = {
            WarningSeverity.LOW: 0.4,
            WarningSeverity.MODERATE: 0.55,
            WarningSeverity.HIGH: 0.7,
            WarningSeverity.CRITICAL: 0.85,
        }
        return CrisisWarning(
            warning_id=f"CW-{self._warning_counter:06d}",
            warning_type=wtype,
            severity=severity,
            trigger_value=trigger,
            threshold=threshold,
            lead_time_days=lead_days,
            description=description,
            recommended_action=action,
            confidence=conf_map.get(severity, 0.5),
        )

    # ------------------------------------------------------------------
    # Quick Scan
    # ------------------------------------------------------------------

    def quick_scan(self, vix: float = 0.0,
                   credit_spread: float = 0.0) -> dict[str, Any]:
        """Fast scan for most urgent warning signals."""
        vix_warn = vix >= self.vol_threshold
        credit_warn = credit_spread >= self.credit_threshold

        alerts: list[str] = []
        if vix_warn:
            alerts.append(f"VIX elevated ({vix:.0f})")
        if credit_warn:
            alerts.append(f"Credit stress ({credit_spread:.1f}%)")

        return {
            "has_warnings": vix_warn or credit_warn,
            "alerts": alerts,
            "vix_alert": vix_warn,
            "credit_alert": credit_warn,
        }

    def clear(self) -> None:
        self.warning_indicators.clear()
        self._warning_counter = 0
