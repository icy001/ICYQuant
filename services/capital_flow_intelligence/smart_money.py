"""Smart Money Tracker.

Tracks smart money (hedge funds, market makers, large institutional traders)
entry and exit patterns to follow the most informed capital in the market.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import (
    CapitalFlowRecord,
    FlowSource,
    FlowDirection,
    SmartMoneyAction,
)


@dataclass
class SmartMoneyResult:
    """Result of smart money tracking analysis.

    Attributes:
        action: Detected smart money action.
        confidence: Detection confidence [0.0, 1.0].
        signal_strength: Action signal strength [0.0, 1.0].
        details: Supporting analysis data.
        timestamp: Detection timestamp.
        description: Human-readable summary.
        alerts: Any risk alerts triggered.
    """

    action: SmartMoneyAction = SmartMoneyAction.WAITING
    confidence: float = 0.5
    signal_strength: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""
    alerts: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.action != SmartMoneyAction.WAITING

    @property
    def is_bullish(self) -> bool:
        return self.action in (SmartMoneyAction.ENTRY, SmartMoneyAction.ADDING)

    @property
    def is_bearish(self) -> bool:
        return self.action in (SmartMoneyAction.EXIT, SmartMoneyAction.REDUCING)

    @property
    def has_alerts(self) -> bool:
        return len(self.alerts) > 0


class SmartMoneyTracker:
    """Tracks and analyzes smart money behavior patterns.

    Monitors hedge funds, market makers, and institutional investors
    for entry/exit signals that indicate informed capital movement.

    Attributes:
        tracking_history: History of tracked flow records.
        entry_records: Records indicating entry activity.
        exit_records: Records indicating exit activity.
        min_confidence: Minimum confidence to report.
    """

    def __init__(self) -> None:
        self.tracking_history: list[CapitalFlowRecord] = []
        self.entry_records: list[CapitalFlowRecord] = []
        self.exit_records: list[CapitalFlowRecord] = []
        self.min_confidence: float = 0.4

    # --- Tracking ---

    def track(self, data: dict[str, Any] | list[CapitalFlowRecord]) -> dict[str, Any]:
        """Track smart money activity from flow data.

        Args:
            data: Flow data as dict or list of records.

        Returns:
            Dict with tracking signal.
        """
        if isinstance(data, list):
            result = self.analyze(data)
            return {
                "signal": result.action.value.upper(),
                "confidence": result.confidence,
                "strength": result.signal_strength,
                "description": result.description,
            }
        return {"signal": "WAITING", "confidence": 0.3}

    def analyze(self, flows: list[CapitalFlowRecord]) -> SmartMoneyResult:
        """Full smart money analysis.

        Args:
            flows: List of capital flow records.

        Returns:
            SmartMoneyResult with detected action.
        """
        if not flows:
            return SmartMoneyResult(description="No flow data to track.")

        # Filter to smart money sources
        smart_sources = {
            FlowSource.HEDGE_FUND,
            FlowSource.INSTITUTIONAL,
            FlowSource.OPTIONS,
            FlowSource.DARK_POOL,
        }
        smart_flows = [f for f in flows if f.source in smart_sources]
        if not smart_flows:
            smart_flows = flows

        self.tracking_history.extend(smart_flows)

        # Classify entries and exits
        entries = [f for f in smart_flows if f.is_inflow and f.is_significant]
        exits = [f for f in smart_flows if f.is_outflow and f.is_significant]
        self.entry_records.extend(entries)
        self.exit_records.extend(exits)

        # Determine action
        net_smart = sum(f.net_flow_value for f in smart_flows)
        action = self._determine_action(net_smart, len(entries), len(exits))

        # Signal strength
        signal_strength = self._compute_signal_strength(smart_flows, action)

        # Confidence
        confidence = self._compute_confidence(smart_flows, action)

        # Details
        details: dict[str, Any] = {
            "record_count": len(smart_flows),
            "entry_count": len(entries),
            "exit_count": len(exits),
            "net_smart_flow": net_smart,
            "total_amount": sum(abs(f.amount) for f in smart_flows),
        }

        # Description
        description = self._generate_description(action, net_smart, details)

        return SmartMoneyResult(
            action=action,
            confidence=confidence,
            signal_strength=signal_strength,
            details=details,
            description=description,
        )

    # --- Analysis ---

    def get_entry_exit_ratio(self) -> float:
        """Get entry-to-exit ratio from history.

        Returns:
            Ratio (entries / exits). >1 = more entries, <1 = more exits.
        """
        total_entries = len(self.entry_records)
        total_exits = len(self.exit_records)
        if total_exits == 0:
            return float(total_entries) if total_entries > 0 else 1.0
        return total_entries / total_exits

    def get_smart_money_trend(self, window: int = 10) -> str:
        """Get recent smart money trend.

        Args:
            window: Number of recent records.

        Returns:
            'entering', 'exiting', or 'neutral'.
        """
        if len(self.tracking_history) < window:
            recent = self.tracking_history
        else:
            recent = self.tracking_history[-window:]

        net = sum(f.net_flow_value for f in recent)
        if net > 1.5:
            return "entering"
        elif net < -1.5:
            return "exiting"
        return "neutral"

    # --- Internal ---

    def _determine_action(
        self, net_flow: float, entry_count: int, exit_count: int
    ) -> SmartMoneyAction:
        """Determine smart money action from flow analysis."""
        if net_flow > 3.0 and entry_count > exit_count + 3:
            return SmartMoneyAction.ENTRY
        elif net_flow > 1.0 and entry_count > exit_count:
            return SmartMoneyAction.ADDING
        elif net_flow < -3.0 and exit_count > entry_count + 3:
            return SmartMoneyAction.EXIT
        elif net_flow < -1.0 and exit_count > entry_count:
            return SmartMoneyAction.REDUCING
        return SmartMoneyAction.WAITING

    def _compute_signal_strength(
        self, flows: list[CapitalFlowRecord], action: SmartMoneyAction
    ) -> float:
        """Compute signal strength [0.0, 1.0]."""
        if not flows:
            return 0.0
        significant_flows = [f for f in flows if f.is_significant]
        if not significant_flows:
            return 0.0
        return min(1.0, len(significant_flows) / 10.0)

    def _compute_confidence(
        self, flows: list[CapitalFlowRecord], action: SmartMoneyAction
    ) -> float:
        """Compute tracking confidence."""
        confidence = 0.3

        # Active action is more confident
        if action != SmartMoneyAction.WAITING:
            confidence += 0.2

        # More flow records = higher confidence
        if len(flows) >= 10:
            confidence += 0.2
        elif len(flows) >= 5:
            confidence += 0.1

        # Average source confidence
        if flows:
            avg_conf = sum(f.confidence for f in flows) / len(flows)
            confidence += 0.1 * min(1.0, avg_conf)

        return min(1.0, confidence)

    def _generate_description(
        self,
        action: SmartMoneyAction,
        net_flow: float,
        details: dict[str, Any],
    ) -> str:
        """Generate human-readable description."""
        entry_c = details.get("entry_count", 0)
        exit_c = details.get("exit_count", 0)
        action_desc = {
            SmartMoneyAction.ENTRY: "Smart money entering position",
            SmartMoneyAction.EXIT: "Smart money exiting position",
            SmartMoneyAction.ADDING: "Smart money adding to position",
            SmartMoneyAction.REDUCING: "Smart money reducing position",
            SmartMoneyAction.WAITING: "Smart money on sidelines",
        }
        base = action_desc.get(action, "Unknown")
        return f"{base} (entries:{entry_c}, exits:{exit_c}, net:{net_flow:+.2f})"

    def clear(self) -> None:
        """Reset tracker state."""
        self.tracking_history.clear()
        self.entry_records.clear()
        self.exit_records.clear()
