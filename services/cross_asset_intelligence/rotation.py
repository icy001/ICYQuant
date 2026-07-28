"""Asset Rotation Detector.

Detects capital rotation patterns across asset classes and sectors.
Identifies when money flows from one asset class to another and
classifies rotation regimes (risk-on, risk-off, sectoral, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RotationType(str, Enum):
    """Type of asset rotation."""

    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    SECTOR_ROTATION = "sector_rotation"
    ASSET_CLASS_ROTATION = "asset_class_rotation"
    REGIONAL_ROTATION = "regional_rotation"
    STYLE_ROTATION = "style_rotation"
    FLIGHT_TO_QUALITY = "flight_to_quality"
    FLIGHT_TO_SAFETY = "flight_to_safety"
    NONE = "none"


class RotationRegime(str, Enum):
    """Current rotation regime."""

    RISK_SEEKING = "risk_seeking"
    DEFENSIVE = "defensive"
    INFLATION_PROTECTION = "inflation_protection"
    GROWTH_FAVORING = "growth_favoring"
    VALUE_FAVORING = "value_favoring"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class RotationEvent:
    """A detected rotation event.

    Attributes:
        rotation_type: Type of rotation.
        from_assets: Assets being rotated out of.
        to_assets: Assets being rotated into.
        strength: Rotation strength [0.0, 1.0].
        confidence: Detection confidence.
        description: Human-readable description.
        timestamp: Detection timestamp.
        leading_indicator: Leading asset signaling the rotation.
        metadata: Additional context.
    """

    rotation_type: RotationType = RotationType.NONE
    from_assets: list[str] = field(default_factory=list)
    to_assets: list[str] = field(default_factory=list)
    strength: float = 0.0
    confidence: float = 0.5
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    leading_indicator: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.strength >= 0.3 and self.confidence >= 0.5

    @property
    def is_risk_on(self) -> bool:
        return self.rotation_type == RotationType.RISK_ON

    @property
    def is_risk_off(self) -> bool:
        return self.rotation_type in (
            RotationType.RISK_OFF,
            RotationType.FLIGHT_TO_SAFETY,
            RotationType.FLIGHT_TO_QUALITY,
        )


@dataclass
class AssetRotationResult:
    """Complete rotation analysis result.

    Attributes:
        events: Detected rotation events.
        current_regime: Current rotation regime.
        regime_confidence: Regime classification confidence.
        recommendation: Suggested allocation shift.
        description: Human-readable summary.
        confidence: Overall analysis confidence.
        timestamp: Analysis timestamp.
    """

    events: list[RotationEvent] = field(default_factory=list)
    current_regime: RotationRegime = RotationRegime.NEUTRAL
    regime_confidence: float = 0.5
    recommendation: str = ""
    description: str = ""
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def should_rotate(self) -> bool:
        return len(self.events) > 0 and any(e.is_actionable for e in self.events)

    @property
    def active_rotations(self) -> list[RotationEvent]:
        return [e for e in self.events if e.is_actionable]


class AssetRotationDetector:
    """Detects capital rotation across asset classes.

    Monitors relative performance, flow patterns, and inter-market
    signals to identify when capital is rotating between asset classes,
    sectors, styles (growth/value), and regions.

    Attributes:
        performance_data: Per-asset performance tracking.
        flow_data: Per-asset flow tracking.
        rotation_threshold: Minimum relative performance gap for rotation.
        momentum_window: Window for momentum calculation.
    """

    def __init__(self) -> None:
        self.performance_data: dict[str, list[float]] = {}
        self.flow_data: dict[str, list[float]] = {}
        self.rotation_threshold: float = 3.0  # % relative performance
        self.momentum_window: int = 20

    # --- Data Management ---

    def add_performance(self, asset: str, pct_return: float) -> None:
        """Add a performance data point.

        Args:
            asset: Asset identifier.
            pct_return: Percentage return for the period.
        """
        if asset not in self.performance_data:
            self.performance_data[asset] = []
        self.performance_data[asset].append(pct_return)
        if len(self.performance_data[asset]) > 200:
            self.performance_data[asset] = self.performance_data[asset][-200:]

    def add_flow(self, asset: str, flow: float) -> None:
        """Add capital flow data for an asset.

        Args:
            asset: Asset identifier.
            flow: Net capital flow (positive = inflow, negative = outflow).
        """
        if asset not in self.flow_data:
            self.flow_data[asset] = []
        self.flow_data[asset].append(flow)
        if len(self.flow_data[asset]) > 200:
            self.flow_data[asset] = self.flow_data[asset][-200:]

    # --- Analysis ---

    def analyze(self, group_a: list[str], group_b: list[str],
                window: int | None = None, method: str = "relative_performance") -> dict[str, Any]:
        """Detect rotation from group A (from) to group B (to).

        Args:
            group_a: Assets being rotated out of (e.g., bonds).
            group_b: Assets being rotated into (e.g., equities).
            window: Lookback window.
            method: Detection method.

        Returns:
            Dict with rotation analysis.
        """
        w = window or self.momentum_window

        # Compute relative performance
        perf_a = self._group_performance(group_a, w)
        perf_b = self._group_performance(group_b, w)

        # Compute flow differential
        flow_a = self._group_flow(group_a, w)
        flow_b = self._group_flow(group_b, w)

        # Detect rotation
        rotation_type = self._classify_rotation(group_a, group_b, perf_a, perf_b)
        strength = self._compute_strength(perf_a, perf_b, flow_a, flow_b)
        confidence = self._compute_detection_confidence(group_a, group_b, perf_a, perf_b, flow_a, flow_b)
        description = self._generate_event_description(rotation_type, group_a, group_b, perf_a, perf_b)

        return {
            "rotation_type": rotation_type.value,
            "from_assets": group_a,
            "to_assets": group_b,
            "strength": strength,
            "confidence": confidence,
            "description": description,
        }

    def detect_risk_on_off(self) -> RotationEvent | None:
        """Detect risk-on / risk-off rotation.

        Returns:
            RotationEvent or None if no clear signal.
        """
        risk_on = ["SPX", "QQQ", "EEM", "HYG"]
        risk_off = ["TLT", "GLD", "VIX", "USD"]

        perf_on = self._group_performance(risk_on)
        perf_off = self._group_performance(risk_off)

        if perf_on > 5.0 and perf_off < 0:
            return RotationEvent(
                rotation_type=RotationType.RISK_ON,
                from_assets=risk_off,
                to_assets=risk_on,
                strength=min(1.0, perf_on / 20.0),
                description=f"Risk-on: {perf_on:.1f}% vs {perf_off:.1f}% risk-off",
            )
        elif perf_off > 3.0 and perf_on < 0:
            return RotationEvent(
                rotation_type=RotationType.RISK_OFF,
                from_assets=risk_on,
                to_assets=risk_off,
                strength=min(1.0, perf_off / 15.0),
                description=f"Risk-off: {perf_off:.1f}% vs {perf_on:.1f}% risk-on",
            )
        return None

    def detect_sector_rotation(self, sectors: dict[str, float]) -> list[RotationEvent]:
        """Detect sector rotation from relative performance.

        Args:
            sectors: Dict of sector -> recent return.

        Returns:
            List of RotationEvent.
        """
        if len(sectors) < 2:
            return []

        events: list[RotationEvent] = []
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)

        top = sorted_sectors[:len(sorted_sectors) // 2]
        bottom = sorted_sectors[len(sorted_sectors) // 2:]

        top_strength = sum(s[1] for s in top) / len(top) if top else 0
        bottom_strength = sum(s[1] for s in bottom) / len(bottom) if bottom else 0

        if top_strength - bottom_strength > self.rotation_threshold:
            events.append(RotationEvent(
                rotation_type=RotationType.SECTOR_ROTATION,
                from_assets=[s[0] for s in bottom],
                to_assets=[s[0] for s in top],
                strength=min(1.0, (top_strength - bottom_strength) / 10.0),
                confidence=0.6,
                description=f"Sector rotation: {top_strength:.1f}% vs {bottom_strength:.1f}%",
            ))

        return events

    def detect_style_rotation(self,
                               growth_return: float,
                               value_return: float) -> RotationEvent | None:
        """Detect growth vs value rotation.

        Args:
            growth_return: Recent growth index return.
            value_return: Recent value index return.

        Returns:
            RotationEvent or None.
        """
        spread = growth_return - value_return
        if abs(spread) < self.rotation_threshold:
            return None

        if spread > 0:
            return RotationEvent(
                rotation_type=RotationType.STYLE_ROTATION,
                from_assets=["value"],
                to_assets=["growth"],
                strength=min(1.0, spread / 10.0),
                confidence=0.55 + 0.1 * (min(1.0, abs(spread) / 10.0)),
                description=f"Growth outperforming value by {spread:.1f}%",
            )
        else:
            return RotationEvent(
                rotation_type=RotationType.STYLE_ROTATION,
                from_assets=["growth"],
                to_assets=["value"],
                strength=min(1.0, abs(spread) / 10.0),
                confidence=0.55 + 0.1 * (min(1.0, abs(spread) / 10.0)),
                description=f"Value outperforming growth by {abs(spread):.1f}%",
            )

    def detect_flight_to_safety(self,
                                 equity_return: float,
                                 bond_return: float,
                                 gold_return: float) -> RotationEvent | None:
        """Detect flight to safety rotation.

        Args:
            equity_return: Recent equity return.
            bond_return: Recent treasury bond return.
            gold_return: Recent gold return.

        Returns:
            RotationEvent or None.
        """
        if equity_return < -5.0 and (bond_return > 0 or gold_return > 3.0):
            return RotationEvent(
                rotation_type=RotationType.FLIGHT_TO_SAFETY,
                from_assets=["equities"],
                to_assets=["bonds", "gold"],
                strength=min(1.0, abs(equity_return) / 15.0),
                confidence=0.7,
                description=f"Flight to safety: equities {equity_return:.1f}%, "
                            f"bonds {bond_return:.1f}%, gold {gold_return:.1f}%",
                leading_indicator="VIX" if abs(equity_return) > 7 else "",
            )
        return None

    def analyze_full(self) -> AssetRotationResult:
        """Comprehensive rotation analysis.

        Returns:
            AssetRotationResult with all detected rotations and regime.
        """
        events: list[RotationEvent] = []

        # Risk-on/off detection
        roro = self.detect_risk_on_off()
        if roro:
            events.append(roro)

        # Style rotation
        growth_perf = self._group_performance(["QQQ", "IWF"])
        value_perf = self._group_performance(["IWD", "VTV"])
        if abs(growth_perf) > 0 or abs(value_perf) > 0:
            style = self.detect_style_rotation(growth_perf, value_perf)
            if style:
                events.append(style)

        # Regime classification
        regime = self._classify_regime(events)
        regime_conf = self._regime_confidence(events, regime)
        recommendation = self._generate_recommendation(events, regime)
        confidence = self._overall_confidence(events)
        description = self._generate_result_description(events, regime)

        return AssetRotationResult(
            events=events,
            current_regime=regime,
            regime_confidence=regime_conf,
            recommendation=recommendation,
            description=description,
            confidence=confidence,
        )

    # --- Internal ---

    def _group_performance(self, group: list[str], window: int | None = None) -> float:
        w = window or self.momentum_window
        returns: list[float] = []
        for asset in group:
            hist = self.performance_data.get(asset, [])
            recent = hist[-w:] if len(hist) >= w else hist
            if recent:
                returns.append(sum(recent))
        return sum(returns) / len(returns) if returns else 0.0

    def _group_flow(self, group: list[str], window: int | None = None) -> float:
        w = window or self.momentum_window
        flows: list[float] = []
        for asset in group:
            hist = self.flow_data.get(asset, [])
            recent = hist[-w:] if len(hist) >= w else hist
            if recent:
                flows.append(sum(recent))
        return sum(flows) if flows else 0.0

    def _classify_rotation(self, group_a: list[str], group_b: list[str],
                           perf_a: float, perf_b: float) -> RotationType:
        spread = perf_b - perf_a
        a_lower = [s.lower() for s in group_a]
        b_lower = [s.lower() for s in group_b]

        risk_off_assets = {"tlt", "ief", "gld", "vix", "usd", "uup"}
        risk_on_assets = {"spx", "qqq", "iwm", "eem", "hyg", "xly"}

        a_is_risk_off = any(a in risk_off_assets for a in a_lower)
        b_is_risk_on = any(b in risk_on_assets for b in b_lower)
        a_is_risk_on = any(a in risk_on_assets for a in a_lower)
        b_is_risk_off = any(b in risk_off_assets for b in b_lower)

        if spread > self.rotation_threshold:
            if a_is_risk_off and b_is_risk_on:
                return RotationType.RISK_ON
            if a_is_risk_on and b_is_risk_off:
                return RotationType.RISK_OFF
            return RotationType.ASSET_CLASS_ROTATION
        elif spread < -self.rotation_threshold:
            if b_is_risk_off and a_is_risk_on:
                return RotationType.RISK_ON
            return RotationType.ASSET_CLASS_ROTATION

        return RotationType.NONE

    def _compute_strength(self, perf_a: float, perf_b: float,
                          flow_a: float, flow_b: float) -> float:
        perf_diff = abs(perf_b - perf_a)
        strength = min(1.0, perf_diff / 15.0)
        # Flow confirmation boosts strength
        if flow_b > 0 and flow_a < 0:
            strength += 0.15
        elif flow_b > flow_a:
            strength += 0.05
        return min(1.0, strength)

    def _compute_detection_confidence(self, group_a: list[str], group_b: list[str],
                                       perf_a: float, perf_b: float,
                                       flow_a: float, flow_b: float) -> float:
        confidence = 0.4
        spread = abs(perf_b - perf_a)
        if spread > 5.0:
            confidence += 0.3
        elif spread > 3.0:
            confidence += 0.15
        if (flow_b > 0 and flow_a < 0) or (flow_b < 0 and flow_a > 0):
            confidence += 0.15
        total_assets = len(group_a) + len(group_b)
        if total_assets >= 4:
            confidence += 0.1
        return min(1.0, confidence)

    def _generate_event_description(self, rotation_type: RotationType,
                                      group_a: list[str], group_b: list[str],
                                      perf_a: float, perf_b: float) -> str:
        spread = perf_b - perf_a
        direction = "into" if spread > 0 else "out of"
        return (f"{rotation_type.value}: {', '.join(group_b)} {direction} "
                f"{', '.join(group_a)} (spread={spread:.1f}%)")

    def _classify_regime(self, events: list[RotationEvent]) -> RotationRegime:
        if not events:
            return RotationRegime.NEUTRAL

        event_types = {e.rotation_type for e in events}

        if RotationType.RISK_ON in event_types:
            return RotationRegime.RISK_SEEKING
        if {RotationType.RISK_OFF, RotationType.FLIGHT_TO_SAFETY} & event_types:
            return RotationRegime.DEFENSIVE
        if RotationType.FLIGHT_TO_QUALITY in event_types:
            return RotationRegime.INFLATION_PROTECTION
        if RotationType.STYLE_ROTATION in event_types:
            for e in events:
                if e.rotation_type == RotationType.STYLE_ROTATION:
                    if "growth" in e.to_assets:
                        return RotationRegime.GROWTH_FAVORING
                    if "value" in e.to_assets:
                        return RotationRegime.VALUE_FAVORING

        return RotationRegime.NEUTRAL

    def _regime_confidence(self, events: list[RotationEvent],
                           regime: RotationRegime) -> float:
        if not events:
            return 0.3
        actionable = [e for e in events if e.is_actionable]
        if not actionable:
            return 0.3
        avg_conf = sum(e.confidence for e in actionable) / len(actionable)
        return min(1.0, avg_conf)

    def _generate_recommendation(self, events: list[RotationEvent],
                                  regime: RotationRegime) -> str:
        recs = {
            RotationRegime.RISK_SEEKING: "Increase risk asset exposure, favor growth/cyclical",
            RotationRegime.DEFENSIVE: "Reduce risk, increase bonds/gold/cash allocation",
            RotationRegime.INFLATION_PROTECTION: "Add TIPS, commodities, REITs exposure",
            RotationRegime.GROWTH_FAVORING: "Overweight growth stocks, long-duration assets",
            RotationRegime.VALUE_FAVORING: "Overweight value stocks, financials, energy",
            RotationRegime.NEUTRAL: "Maintain balanced allocation",
        }
        return recs.get(regime, "No strong rotation signal")

    def _overall_confidence(self, events: list[RotationEvent]) -> float:
        if not events:
            return 0.2
        actionable = [e for e in events if e.is_actionable]
        if not actionable:
            return 0.3
        avg_conf = sum(e.confidence for e in actionable) / len(actionable)
        avg_strength = sum(e.strength for e in actionable) / len(actionable)
        return min(1.0, avg_conf * 0.7 + avg_strength * 0.3)

    def _generate_result_description(self, events: list[RotationEvent],
                                       regime: RotationRegime) -> str:
        if not events:
            return "No active rotation detected"
        parts = [e.description for e in events if e.is_actionable]
        return f"Regime: {regime.value} | " + " | ".join(parts) if parts else f"Regime: {regime.value}"

    def clear(self) -> None:
        self.performance_data.clear()
        self.flow_data.clear()
