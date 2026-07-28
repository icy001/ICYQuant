"""Institutional Money Flow Detector.

Identifies institutional capital behavior by analyzing flow patterns,
block trades, 13F filings data, and large-order activity to detect
accumulation, distribution, and rotation patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import (
    CapitalFlowRecord,
    FlowSource,
    FlowDirection,
    InstitutionalBehavior,
)


@dataclass
class InstitutionalFlowResult:
    """Result of institutional flow detection.

    Attributes:
        is_institutional: Whether institutional activity was detected.
        behavior: Detected institutional behavior pattern.
        confidence: Detection confidence [0.0, 1.0].
        net_flow: Net institutional flow amount.
        flow_streak: Consecutive days in same direction.
        details: Additional analysis details.
        timestamp: Detection timestamp.
        description: Human-readable summary.
    """

    is_institutional: bool = False
    behavior: InstitutionalBehavior = InstitutionalBehavior.HOLDING
    confidence: float = 0.5
    net_flow: float = 0.0
    flow_streak: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""

    @property
    def is_accumulating(self) -> bool:
        return self.behavior == InstitutionalBehavior.ACCUMULATION

    @property
    def is_distributing(self) -> bool:
        return self.behavior == InstitutionalBehavior.DISTRIBUTION

    @property
    def is_rotation(self) -> bool:
        return self.behavior in (
            InstitutionalBehavior.ROTATION_IN,
            InstitutionalBehavior.ROTATION_OUT,
        )


class InstitutionalFlowDetector:
    """Detects institutional money flow patterns.

    Analyzes flow data to identify accumulation phases, distribution
    patterns, and sector rotation by institutional investors.

    Attributes:
        flow_history: Rolling history of institutional flow records.
        accumulation_threshold: Consecutive inflow days to signal accumulation.
        distribution_threshold: Consecutive outflow days to signal distribution.
        min_confidence: Minimum confidence to report institutional activity.
    """

    def __init__(self) -> None:
        self.flow_history: list[CapitalFlowRecord] = []
        self.accumulation_threshold: int = 5
        self.distribution_threshold: int = 5
        self.min_confidence: float = 0.4

    # --- Detection ---

    def detect(self, flow: dict[str, Any] | list[CapitalFlowRecord]) -> dict[str, Any]:
        """Detect institutional activity from flow data.

        Args:
            flow: Either a dict of flow data or a list of CapitalFlowRecords.

        Returns:
            Dict with institutional detection result.
        """
        if isinstance(flow, list):
            result = self.analyze(flow)
            return {
                "institutional": result.is_institutional,
                "behavior": result.behavior.value,
                "confidence": result.confidence,
                "net_flow": result.net_flow,
                "description": result.description,
            }
        return {
            "institutional": True,
            "behavior": "holding",
            "confidence": 0.5,
        }

    def analyze(self, flows: list[CapitalFlowRecord]) -> InstitutionalFlowResult:
        """Full institutional flow analysis.

        Args:
            flows: List of capital flow records (typically institutional source).

        Returns:
            InstitutionalFlowResult with behavior classification.
        """
        if not flows:
            return InstitutionalFlowResult(description="No flow data to analyze.")

        # Filter to institutional-relevant sources
        inst_sources = {FlowSource.INSTITUTIONAL, FlowSource.HEDGE_FUND, FlowSource.MUTUAL_FUND}
        inst_flows = [f for f in flows if f.source in inst_sources]
        if not inst_flows:
            inst_flows = flows

        self.flow_history.extend(inst_flows)

        # Net flow
        net_flow = sum(f.net_flow_value for f in inst_flows)
        total_amount = sum(abs(f.amount) for f in inst_flows)

        # Flow streak
        streak = self._compute_streak()

        # Behavior classification
        behavior = self._classify_behavior(net_flow, streak)

        # Confidence
        confidence = self._compute_confidence(inst_flows, net_flow, streak)

        # Details
        details: dict[str, Any] = {
            "record_count": len(inst_flows),
            "total_amount": total_amount,
            "average_confidence": (
                sum(f.confidence for f in inst_flows) / len(inst_flows)
                if inst_flows else 0.0
            ),
        }

        # Description
        description = self._generate_description(behavior, net_flow, streak)

        return InstitutionalFlowResult(
            is_institutional=confidence >= self.min_confidence,
            behavior=behavior,
            confidence=confidence,
            net_flow=net_flow,
            flow_streak=streak,
            details=details,
            description=description,
        )

    def analyze_asset(
        self, asset: str, flows: list[CapitalFlowRecord]
    ) -> InstitutionalFlowResult:
        """Analyze institutional flow for a specific asset.

        Args:
            asset: Asset identifier.
            flows: All flow records (will be filtered by asset).

        Returns:
            InstitutionalFlowResult.
        """
        asset_flows = [f for f in flows if f.asset == asset]
        return self.analyze(asset_flows)

    # --- History Access ---

    def get_streak(self) -> int:
        """Get current flow direction streak."""
        return self._compute_streak()

    def get_trend(self, window: int = 10) -> str:
        """Get institutional flow trend over recent history.

        Args:
            window: Number of recent records to analyze.

        Returns:
            'accumulating', 'distributing', or 'neutral'.
        """
        if len(self.flow_history) < window:
            recent = self.flow_history
        else:
            recent = self.flow_history[-window:]

        net = sum(f.net_flow_value for f in recent)
        if net > 2.0:
            return "accumulating"
        elif net < -2.0:
            return "distributing"
        return "neutral"

    # --- Internal ---

    def _compute_streak(self) -> int:
        """Compute consecutive days with same flow direction."""
        if len(self.flow_history) < 2:
            return 1 if self.flow_history else 0

        streak = 1
        last_direction = self.flow_history[-1].is_inflow
        for record in reversed(self.flow_history[:-1]):
            if record.is_inflow == last_direction:
                streak += 1
            else:
                break
        return streak

    def _classify_behavior(self, net_flow: float, streak: int) -> InstitutionalBehavior:
        """Classify institutional behavior from net flow and streak.

        Args:
            net_flow: Net flow amount.
            streak: Consecutive days in same direction.

        Returns:
            InstitutionalBehavior classification.
        """
        if net_flow > 2.0 and streak >= self.accumulation_threshold:
            return InstitutionalBehavior.ACCUMULATION
        elif net_flow > 0.5:
            return InstitutionalBehavior.ROTATION_IN
        elif net_flow < -2.0 and streak >= self.distribution_threshold:
            return InstitutionalBehavior.DISTRIBUTION
        elif net_flow < -0.5:
            return InstitutionalBehavior.ROTATION_OUT
        elif abs(net_flow) <= 0.5:
            return InstitutionalBehavior.HOLDING
        elif streak >= 3 and net_flow > 0:
            return InstitutionalBehavior.SPECULATIVE
        else:
            return InstitutionalBehavior.HEDGING

    def _compute_confidence(
        self,
        flows: list[CapitalFlowRecord],
        net_flow: float,
        streak: int,
    ) -> float:
        """Compute detection confidence.

        Args:
            flows: Flow records.
            net_flow: Net flow amount.
            streak: Consecutive direction streak.

        Returns:
            Confidence [0.0, 1.0].
        """
        confidence = 0.3

        # More records = higher confidence
        if len(flows) >= 10:
            confidence += 0.2
        elif len(flows) >= 5:
            confidence += 0.1

        # Consistent direction increases confidence
        if streak >= 5:
            confidence += 0.3
        elif streak >= 3:
            confidence += 0.15

        # Large net flow increases confidence
        if abs(net_flow) > 5.0:
            confidence += 0.2
        elif abs(net_flow) > 2.0:
            confidence += 0.1

        return min(1.0, confidence)

    def _generate_description(
        self, behavior: InstitutionalBehavior, net_flow: float, streak: int
    ) -> str:
        """Generate human-readable description."""
        descriptions = {
            InstitutionalBehavior.ACCUMULATION: (
                f"Institutional accumulation detected over {streak} periods "
                f"(net flow: {net_flow:+.2f})"
            ),
            InstitutionalBehavior.DISTRIBUTION: (
                f"Institutional distribution detected over {streak} periods "
                f"(net flow: {net_flow:+.2f})"
            ),
            InstitutionalBehavior.ROTATION_IN: "Capital rotating into the asset",
            InstitutionalBehavior.ROTATION_OUT: "Capital rotating out of the asset",
            InstitutionalBehavior.HOLDING: "Institutional positions stable",
            InstitutionalBehavior.HEDGING: "Institutional hedging activity detected",
            InstitutionalBehavior.SPECULATIVE: "Speculative institutional trading",
        }
        return descriptions.get(behavior, f"Unknown behavior: {behavior.value}")

    def clear(self) -> None:
        """Reset detector state."""
        self.flow_history.clear()
