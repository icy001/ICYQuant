"""Drawdown Intelligence Engine - analyzes drawdowns and provides recovery strategies."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DrawdownSeverity(str, Enum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"
    CATASTROPHIC = "CATASTROPHIC"


class DrawdownPhase(str, Enum):
    PEAK = "PEAK"
    DECLINING = "DECLINING"
    TROUGH = "TROUGH"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"


class RecoveryStrategy(str, Enum):
    HOLD = "HOLD"
    AVERAGE_DOWN = "AVERAGE_DOWN"
    REDUCE = "REDUCE"
    HEDGE = "HEDGE"
    STOP_LOSS = "STOP_LOSS"
    ROTATE = "ROTATE"


@dataclass
class DrawdownEvent:
    event_id: str
    start_date: str
    end_date: Optional[str]
    peak_value: float
    trough_value: float
    depth_pct: float
    duration_days: int
    recovery_days: int
    severity: DrawdownSeverity
    phase: DrawdownPhase
    cause: str
    positions_affected: List[str]


@dataclass
class DrawdownAnalysis:
    analysis_id: str
    active_drawdowns: List[DrawdownEvent]
    historical_drawdowns: List[DrawdownEvent]
    max_drawdown: float
    avg_drawdown: float
    avg_recovery_days: float
    underwater_ratio: float
    recovery_strategies: Dict[str, RecoveryStrategy]


class DrawdownIntelligenceEngine:
    """Drawdown Intelligence Engine.

    Identifies why drawdowns happened and how to recover.
    Provides drawdown analysis and recovery strategy recommendations.
    """

    def __init__(self):
        self.analyses: List[DrawdownAnalysis] = []
        self.drawdown_history: List[DrawdownEvent] = []

    def analyze(self, drawdown) -> Dict[str, Any]:
        """Analyze a drawdown and provide intelligence.

        Args:
            drawdown: Drawdown data to analyze.

        Returns:
            Dict with drawdown analysis.
        """
        if isinstance(drawdown, dict):
            return self._analyze_from_dict(drawdown)
        return {"drawdown": drawdown}

    def _analyze_from_dict(self, drawdown: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze drawdown from structured data."""
        equity_curve = drawdown.get("equity_curve", [])
        positions = drawdown.get("positions", [])
        dates = drawdown.get("dates", [])

        # Detect drawdown events
        events = self._detect_drawdown_events(equity_curve, dates, positions)

        active = [e for e in events if e.phase != DrawdownPhase.RECOVERED]
        historical = [e for e in events if e.phase == DrawdownPhase.RECOVERED]

        max_dd = max((e.depth_pct for e in events), default=0.0)
        avg_dd = sum(e.depth_pct for e in events) / len(events) if events else 0.0

        avg_recovery = (sum(e.recovery_days for e in historical) / len(historical)
                        if historical else 0.0)

        # Underwater ratio: proportion of time in drawdown
        underwater_days = sum(e.duration_days for e in events)
        total_days = len(equity_curve) if equity_curve else 1
        underwater_ratio = underwater_days / total_days if total_days > 0 else 0.0

        # Recovery strategies for active drawdowns
        strategies = {}
        for e in active:
            strategy = self._recommend_recovery(e, positions)
            strategies[e.event_id] = strategy

        analysis = DrawdownAnalysis(
            analysis_id=f"DD_{len(self.analyses):04d}",
            active_drawdowns=active,
            historical_drawdowns=historical,
            max_drawdown=max_dd,
            avg_drawdown=avg_dd,
            avg_recovery_days=avg_recovery,
            underwater_ratio=underwater_ratio,
            recovery_strategies=strategies,
        )
        self.analyses.append(analysis)
        self.drawdown_history.extend(events)

        return {
            "drawdown": drawdown,
            "max_drawdown": max_dd,
            "avg_drawdown": avg_dd,
            "avg_recovery_days": avg_recovery,
            "underwater_ratio": underwater_ratio,
            "active_drawdowns": [
                {
                    "id": e.event_id,
                    "depth": e.depth_pct,
                    "duration_days": e.duration_days,
                    "severity": e.severity.value,
                    "phase": e.phase.value,
                    "cause": e.cause,
                    "recovery_strategy": strategies.get(e.event_id, RecoveryStrategy.HOLD).value,
                }
                for e in active
            ],
            "historical_drawdown_count": len(historical),
            "summary": self._generate_summary(analysis),
        }

    def _detect_drawdown_events(self, equity: List[float], dates: List[str],
                                 positions: List[Dict]) -> List[DrawdownEvent]:
        """Detect all drawdown events from equity curve."""
        if len(equity) < 2:
            return []

        events = []
        peak_idx = 0
        peak_value = equity[0]
        in_drawdown = False
        drawdown_start = 0
        max_dd_depth = 0.0
        trough_value = equity[0]

        for i in range(1, len(equity)):
            val = equity[i]
            if val > peak_value:
                if in_drawdown:
                    # Drawdown ended
                    severity = self._classify_severity(max_dd_depth)
                    duration = i - drawdown_start
                    recovery_days = i - drawdown_start

                    events.append(DrawdownEvent(
                        event_id=f"DD_{len(events):04d}",
                        start_date=dates[drawdown_start] if dates else f"T{drawdown_start}",
                        end_date=dates[i] if dates else f"T{i}",
                        peak_value=peak_value,
                        trough_value=trough_value,
                        depth_pct=max_dd_depth,
                        duration_days=duration,
                        recovery_days=recovery_days,
                        severity=severity,
                        phase=DrawdownPhase.RECOVERED,
                        cause=self._diagnose_cause(max_dd_depth, positions),
                        positions_affected=[p.get("symbol", "UNKNOWN") for p in positions],
                    ))
                    in_drawdown = False

                peak_value = val
                peak_idx = i
            else:
                dd = (peak_value - val) / peak_value
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_start = peak_idx
                    max_dd_depth = 0.0
                    trough_value = val
                if dd > max_dd_depth:
                    max_dd_depth = dd
                    trough_value = val

        # Handle ongoing drawdown
        if in_drawdown:
            duration = len(equity) - drawdown_start
            events.append(DrawdownEvent(
                event_id=f"DD_{len(events):04d}",
                start_date=dates[drawdown_start] if dates else f"T{drawdown_start}",
                end_date=None,
                peak_value=peak_value,
                trough_value=trough_value,
                depth_pct=max_dd_depth,
                duration_days=duration,
                recovery_days=0,
                severity=self._classify_severity(max_dd_depth),
                phase=DrawdownPhase.DECLINING,
                cause=self._diagnose_cause(max_dd_depth, positions),
                positions_affected=[p.get("symbol", "UNKNOWN") for p in positions],
            ))

        return events

    def _classify_severity(self, depth: float) -> DrawdownSeverity:
        if depth < 0.05:
            return DrawdownSeverity.MILD
        elif depth < 0.10:
            return DrawdownSeverity.MODERATE
        elif depth < 0.20:
            return DrawdownSeverity.SEVERE
        elif depth < 0.40:
            return DrawdownSeverity.CRITICAL
        return DrawdownSeverity.CATASTROPHIC

    def _diagnose_cause(self, depth: float, positions: List[Dict]) -> str:
        if depth > 0.25:
            return "Systemic market event or strategy failure"
        elif depth > 0.15:
            return "Sector rotation or factor headwind"
        elif depth > 0.08:
            return "Temporary market correction"
        elif depth > 0.03:
            return "Normal portfolio fluctuation"
        return "Minor drawdown within normal range"

    def _recommend_recovery(self, event: DrawdownEvent,
                            positions: List[Dict]) -> RecoveryStrategy:
        if event.severity in (DrawdownSeverity.CATASTROPHIC, DrawdownSeverity.CRITICAL):
            return RecoveryStrategy.HEDGE
        elif event.severity == DrawdownSeverity.SEVERE:
            return RecoveryStrategy.REDUCE
        elif event.severity == DrawdownSeverity.MODERATE:
            return RecoveryStrategy.AVERAGE_DOWN
        elif event.severity == DrawdownSeverity.MILD:
            return RecoveryStrategy.HOLD
        return RecoveryStrategy.HOLD

    def _generate_summary(self, analysis: DrawdownAnalysis) -> str:
        if analysis.active_drawdowns:
            worst = max(analysis.active_drawdowns, key=lambda e: e.depth_pct)
            return (
                f"{len(analysis.active_drawdowns)} active drawdown(s). "
                f"Worst: {worst.depth_pct:.1%} ({worst.severity.value}). "
                f"Historical avg recovery: {analysis.avg_recovery_days:.0f} days"
            )
        return "No active drawdowns. Portfolio at or near highs."

    def get_latest_analysis(self) -> Optional[DrawdownAnalysis]:
        """Get the most recent drawdown analysis."""
        return self.analyses[-1] if self.analyses else None

    def get_active_drawdowns(self) -> List[DrawdownEvent]:
        """Get all currently active drawdown events."""
        if not self.analyses:
            return []
        return self.analyses[-1].active_drawdowns

    def get_worst_drawdowns(self, top_n: int = 5) -> List[DrawdownEvent]:
        """Get the worst drawdown events by depth."""
        return sorted(self.drawdown_history, key=lambda e: e.depth_pct, reverse=True)[:top_n]
