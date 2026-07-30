"""ICYQuant Black Swan Detection & Auto-Protection.

Monitors for extreme events (market crashes, volatility spikes,
liquidity dropouts) and triggers automatic protection measures.

Usage::

    detector = BlackSwanDetector(BlackSwanConfig())
    event = detector.detect(market_data)
    if event.detected:
        actions = detector.trigger_protection(event)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from services.risk_intelligence.config import (
    BlackSwanConfig,
    BlackSwanIndicator,
)


# ============================================================================
# Data Types
# ============================================================================


class EventSeverity(str, Enum):
    """Black swan event severity."""
    NONE = "none"
    WARNING = "warning"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class IndicatorSignal:
    """Signal from a single black swan indicator."""
    indicator: BlackSwanIndicator
    triggered: bool
    value: float
    threshold: float
    score: float  # 0-100


@dataclass
class BlackSwanEvent:
    """Black swan detection event."""

    detected: bool = False
    severity: EventSeverity = EventSeverity.NONE
    composite_score: float = 0.0  # 0-100
    indicators: List[IndicatorSignal] = field(default_factory=list)
    triggered_indicators: List[BlackSwanIndicator] = field(default_factory=list)
    protections_activated: List[str] = field(default_factory=list)
    description: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "severity": self.severity.value,
            "composite_score": round(self.composite_score, 2),
            "triggered_indicators": [i.value for i in self.triggered_indicators],
            "protections_activated": self.protections_activated,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
        }


# ============================================================================
# Black Swan Detector
# ============================================================================


class BlackSwanDetector:
    """Black Swan Event Detector.

    Monitors multiple indicators simultaneously to detect
    extreme market events and triggers automatic protection.

    Detection Indicators:
        - Index crash (>X% single-day drop)
        - Volume surge (>Nx average)
        - Volatility spike (>Nx baseline)
        - Liquidity dropout (bid-ask spread explosion)
        - Correlation breakdown (cross-asset)
        - Credit spread explosion

    Usage::

        detector = BlackSwanDetector(BlackSwanConfig())
        event = detector.detect({
            "daily_return": -0.06,
            "volume": 5000000,
            "avg_volume_20d": 1000000,
            "volatility": 0.045,
            "baseline_vol": 0.012,
            "spread": 0.005,
            "avg_spread": 0.001,
        })
    """

    # Indicator default thresholds (adjustable via config)
    INDICATOR_THRESHOLDS: Dict[BlackSwanIndicator, float] = {
        BlackSwanIndicator.INDEX_CRASH: -0.05,
        BlackSwanIndicator.VOLUME_SURGE: 5.0,
        BlackSwanIndicator.VOLATILITY_SPIKE: 3.0,
        BlackSwanIndicator.LIQUIDITY_DROPOUT: 0.005,
        BlackSwanIndicator.CORRELATION_BREAKDOWN: 0.8,
        BlackSwanIndicator.SPREAD_EXPLOSION: 0.003,
    }

    INDICATOR_WEIGHTS: Dict[BlackSwanIndicator, float] = {
        BlackSwanIndicator.INDEX_CRASH: 0.25,
        BlackSwanIndicator.VOLUME_SURGE: 0.15,
        BlackSwanIndicator.VOLATILITY_SPIKE: 0.25,
        BlackSwanIndicator.LIQUIDITY_DROPOUT: 0.20,
        BlackSwanIndicator.CORRELATION_BREAKDOWN: 0.05,
        BlackSwanIndicator.SPREAD_EXPLOSION: 0.10,
    }

    def __init__(self, config: Optional[BlackSwanConfig] = None) -> None:
        self.config = config or BlackSwanConfig()
        self._history: List[BlackSwanEvent] = []
        self._protection_active: bool = False
        self._consecutive_signals: int = 0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, market_data: Dict[str, float]) -> BlackSwanEvent:
        """Detect black swan events from market data.

        Args:
            market_data: Dictionary with:
                - daily_return: float (single day return)
                - volume: float (current volume)
                - avg_volume_20d: float (20-day average volume)
                - volatility: float (current volatility)
                - baseline_vol: float (baseline volatility)
                - spread: float (current bid-ask spread)
                - avg_spread: float (average bid-ask spread)
                - correlations: Optional List[float] (cross-asset correlations)

        Returns:
            BlackSwanEvent with detection result.
        """
        indicators: List[IndicatorSignal] = []
        triggered: List[BlackSwanIndicator] = []

        # 1. Index crash
        crash = self._check_crash(market_data)
        indicators.append(crash)
        if crash.triggered:
            triggered.append(BlackSwanIndicator.INDEX_CRASH)

        # 2. Volume surge
        vol_surge = self._check_volume_surge(market_data)
        indicators.append(vol_surge)
        if vol_surge.triggered:
            triggered.append(BlackSwanIndicator.VOLUME_SURGE)

        # 3. Volatility spike
        vol_spike = self._check_volatility_spike(market_data)
        indicators.append(vol_spike)
        if vol_spike.triggered:
            triggered.append(BlackSwanIndicator.VOLATILITY_SPIKE)

        # 4. Liquidity dropout
        liq_drop = self._check_liquidity_dropout(market_data)
        indicators.append(liq_drop)
        if liq_drop.triggered:
            triggered.append(BlackSwanIndicator.LIQUIDITY_DROPOUT)

        # 5. Spread explosion
        spread_ex = self._check_spread_explosion(market_data)
        indicators.append(spread_ex)
        if spread_ex.triggered:
            triggered.append(BlackSwanIndicator.SPREAD_EXPLOSION)

        # 6. Correlation breakdown (optional)
        if "correlations" in market_data:
            corr_bd = self._check_correlation_breakdown(market_data)
            indicators.append(corr_bd)
            if corr_bd.triggered:
                triggered.append(BlackSwanIndicator.CORRELATION_BREAKDOWN)

        # Compute composite score
        composite = self._compute_composite(indicators)

        # Determine severity
        severity = self._determine_severity(composite, len(triggered))

        # Build event
        description = self._build_description(triggered, composite, severity)
        event = BlackSwanEvent(
            detected=len(triggered) > 0,
            severity=severity,
            composite_score=composite,
            indicators=indicators,
            triggered_indicators=triggered,
            description=description,
        )

        # Auto-protection
        if self.config.auto_protection and event.detected:
            protections = self.trigger_protection(event)
            event.protections_activated = protections

        # Consecutive signal tracking
        if event.detected:
            self._consecutive_signals += 1
        else:
            self._consecutive_signals = 0

        self._history.append(event)
        if len(self._history) > 500:
            self._history = self._history[-500:]

        return event

    # ------------------------------------------------------------------
    # Individual Indicators
    # ------------------------------------------------------------------

    def _check_crash(
        self, data: Dict[str, float]
    ) -> IndicatorSignal:
        """Check for index crash."""
        ret = data.get("daily_return", 0.0)
        threshold = self.config.crash_threshold_pct
        triggered = ret <= threshold
        score = min(100.0, abs(ret) / abs(threshold) * 50) if threshold != 0 else 0.0
        return IndicatorSignal(
            indicator=BlackSwanIndicator.INDEX_CRASH,
            triggered=triggered,
            value=ret,
            threshold=threshold,
            score=score,
        )

    def _check_volume_surge(
        self, data: Dict[str, float]
    ) -> IndicatorSignal:
        """Check for abnormal volume surge."""
        vol = data.get("volume", 0.0)
        avg = data.get("avg_volume_20d", 1.0)
        threshold_val = self.config.volume_surge_multiplier
        if avg > 0:
            ratio = vol / avg
        else:
            ratio = 1.0

        triggered = ratio >= threshold_val
        score = min(100.0, (ratio / threshold_val) * 50) if threshold_val > 0 else 0.0
        return IndicatorSignal(
            indicator=BlackSwanIndicator.VOLUME_SURGE,
            triggered=triggered,
            value=ratio,
            threshold=threshold_val,
            score=score,
        )

    def _check_volatility_spike(
        self, data: Dict[str, float]
    ) -> IndicatorSignal:
        """Check for volatility spike."""
        vol = data.get("volatility", 0.0)
        baseline = data.get("baseline_vol", 0.001)
        threshold_val = self.config.volatility_spike_multiplier
        if baseline > 0:
            ratio = vol / baseline
        else:
            ratio = 1.0

        triggered = ratio >= threshold_val
        score = min(100.0, (ratio / threshold_val) * 50) if threshold_val > 0 else 0.0
        return IndicatorSignal(
            indicator=BlackSwanIndicator.VOLATILITY_SPIKE,
            triggered=triggered,
            value=ratio,
            threshold=threshold_val,
            score=score,
        )

    def _check_liquidity_dropout(
        self, data: Dict[str, float]
    ) -> IndicatorSignal:
        """Check for liquidity dropout (spread widening)."""
        spread = data.get("spread", 0.0)
        threshold_val = self.config.liquidity_dropout_threshold_pct
        triggered = spread >= threshold_val
        score = min(100.0, (spread / max(threshold_val, 0.0001)) * 50)
        return IndicatorSignal(
            indicator=BlackSwanIndicator.LIQUIDITY_DROPOUT,
            triggered=triggered,
            value=spread,
            threshold=threshold_val,
            score=score,
        )

    def _check_spread_explosion(
        self, data: Dict[str, float]
    ) -> IndicatorSignal:
        """Check for credit/rate spread explosion."""
        spread = data.get("credit_spread", 0.0)
        avg_spread = data.get("avg_credit_spread", 0.001)
        threshold_val = 0.003  # Default: 30bps spike
        if avg_spread > 0:
            ratio = spread / avg_spread
        else:
            ratio = 1.0 obj
        triggered = ratio >= 3.0
        score = min(100.0, ratio * 25)
        return IndicatorSignal(
            indicator=BlackSwanIndicator.SPREAD_EXPLOSION,
            triggered=triggered,
            value=ratio,
            threshold=3.0,
            score=score,
        )

    def _check_correlation_breakdown(
        self, data: Dict[str, float]
    ) -> IndicatorSignal:
        """Check for cross-asset correlation breakdown."""
        correlations = data.get("correlations", [])
        if isinstance(correlations, list) and len(correlations) > 0:
            # High positive correlations converging to 1 = systemic
            max_corr = max(abs(c) for c in correlations)
        else:
            max_corr = 0.0

        threshold_val = 0.9
        triggered = max_corr >= threshold_val
        score = max_corr * 100
        return IndicatorSignal(
            indicator=BlackSwanIndicator.CORRELATION_BREAKDOWN,
            triggered=triggered,
            value=max_corr,
            threshold=threshold_val,
            score=score,
        )

    # ------------------------------------------------------------------
    # Composite & Severity
    # ------------------------------------------------------------------

    def _compute_composite(
        self, indicators: List[IndicatorSignal]
    ) -> float:
        """Compute weighted composite black swan score (0-100)."""
        total = 0.0
        total_weight = 0.0

        for ind in indicators:
            weight = self.INDICATOR_WEIGHTS.get(ind.indicator, 0.1)
            total += ind.score * weight
            total_weight += weight

        return total / total_weight if total_weight > 0 else 0.0

    def _determine_severity(
        self, score: float, num_triggered: int
    ) -> EventSeverity:
        """Determine event severity."""
        if score >= 80 and num_triggered >= 3:
            return EventSeverity.EXTREME
        elif score >= 60 and num_triggered >= 2:
            return EventSeverity.SEVERE
        elif score >= 30 and num_triggered >= 1:
            return EventSeverity.WARNING
        return EventSeverity.NONE

    def _build_description(
        self,
        triggered: List[BlackSwanIndicator],
        score: float,
        severity: EventSeverity,
    ) -> str:
        """Build human-readable event description."""
        indicator_names = [i.value for i in triggered]

        if severity == EventSeverity.EXTREME:
            return (
                f"EXTREME black swan signal: {', '.join(indicator_names)} "
                f"(score={score:.1f}). Immediate action required."
            )
        elif severity == EventSeverity.SEVERE:
            return (
                f"SEVERE black swan signal: {', '.join(indicator_names)} "
                f"(score={score:.1f}). Activate protection."
            )
        elif severity == EventSeverity.WARNING:
            return (
                f"Warning signal: {', '.join(indicator_names)} "
                f"(score={score:.1f}). Monitor closely."
            )
        return "No black swan signals detected."

    # ------------------------------------------------------------------
    # Auto-Protection
    # ------------------------------------------------------------------

    def trigger_protection(self, event: BlackSwanEvent) -> List[str]:
        """Trigger automatic protection measures based on event severity.

        Args:
            event: Detected BlackSwanEvent.

        Returns:
            List of protection actions activated.
        """
        actions: List[str] = []

        if event.severity == EventSeverity.EXTREME:
            actions = [
                "stop_opening",
                "reduce_leverage_to_minimum",
                "close_all_discretionary",
                "activate_safe_haven",
                "freeze_trading",
                "notify_risk_committee",
            ]
        elif event.severity == EventSeverity.SEVERE:
            actions = [
                "stop_opening",
                "reduce_leverage_by_75%",
                "freeze_high_risk",
                "activate_safe_haven",
            ]
        elif event.severity == EventSeverity.WARNING:
            actions = [
                "reduce_leverage_by_25%",
                "increase_hedge_ratios",
            ]

        self._protection_active = len(actions) > 0
        return actions

    def deactivate_protection(self) -> None:
        """Manually deactivate all protection measures."""
        self._protection_active = False
        self._consecutive_signals = 0

    def is_protection_active(self) -> bool:
        """Check if protection is currently active."""
        return self._protection_active

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(
        self, limit: int = 100, severity: Optional[EventSeverity] = None,
    ) -> List[BlackSwanEvent]:
        """Get recent detection history, optionally filtered."""
        events = self._history[-limit:]
        if severity:
            events = [e for e in events if e.severity == severity]
        return events

    def get_consecutive_signal_count(self) -> int:
        """Get count of consecutive positive detections."""
        return self._consecutive_signals
