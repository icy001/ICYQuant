"""AI Portfolio Memory — historical portfolio state & decision memory.

Records portfolio configurations, allocation decisions, performance
history, and market regime context. Enables learning from past
decisions and supports trend analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MemoryEventType(str, Enum):
    """Types of portfolio memory events."""

    ALLOCATION_CHANGE = "allocation_change"
    REBALANCE = "rebalance"
    OPTIMIZATION = "optimization"
    PERFORMANCE_SNAPSHOT = "performance_snapshot"
    RISK_BUDGET_UPDATE = "risk_budget_update"
    EXPOSURE_BREACH = "exposure_breach"
    SIZING_DECISION = "sizing_decision"
    ATTRIBUTION_REPORT = "attribution_report"
    MARKET_REGIME = "market_regime"


class DecisionOutcome(str, Enum):
    """Outcome classification for past decisions."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class MemoryEvent:
    """Single portfolio memory event.

    Attributes:
        event_type: Type of event recorded.
        data: Event data payload.
        outcome: Decision outcome assessment.
        impact_score: Normalized impact score (-1.0 to +1.0).
        timestamp: Event time.
        tags: Searchable tags.
        notes: Human-readable notes.
    """

    event_type: MemoryEventType
    data: dict[str, Any]
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    impact_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def age_days(self) -> float:
        """Age of this event in days."""
        return (datetime.utcnow() - self.timestamp).total_seconds() / 86400.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "outcome": self.outcome.value,
            "impact_score": self.impact_score,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "notes": self.notes,
        }


@dataclass
class PerformanceSnapshot:
    """Portfolio performance snapshot at a point in time.

    Attributes:
        date: Snapshot date.
        portfolio_value: Total portfolio value.
        daily_return: Daily return.
        ytd_return: Year-to-date return.
        annual_volatility: Annualized volatility.
        sharpe_ratio: Sharpe ratio.
        max_drawdown: Maximum drawdown.
        allocations: Current allocation weights.
        risk_metrics: Dict of risk metrics.
    """

    date: datetime
    portfolio_value: float
    daily_return: float = 0.0
    ytd_return: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    allocations: dict[str, float] = field(default_factory=dict)
    risk_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class PortfolioInsight:
    """Insight extracted from portfolio memory.

    Attributes:
        insight_type: Category of insight.
        description: Human-readable insight.
        confidence: Confidence level (0–1).
        supporting_events: Number of events supporting this insight.
        recommendation: Actionable recommendation.
        timestamp: Insight generation time.
    """

    insight_type: str
    description: str
    confidence: float = 0.0
    supporting_events: int = 0
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# PortfolioMemory
# ---------------------------------------------------------------------------


class PortfolioMemory:
    """Portfolio decision memory and analytics engine.

    Records portfolio events, decisions, and performance snapshots.
    Extracts insights from historical data to improve future decisions.

    Attributes:
        events: List of all memory events.
        snapshots: Performance snapshots over time.
        max_events: Maximum events to retain in memory.
    """

    def __init__(self, max_events: int = 10000) -> None:
        """Initialize portfolio memory.

        Args:
            max_events: Maximum number of events to retain.
        """
        self.events: list[MemoryEvent] = []
        self.snapshots: list[PerformanceSnapshot] = []
        self.max_events = max_events

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        event_type: MemoryEventType,
        data: dict[str, Any],
        outcome: DecisionOutcome = DecisionOutcome.PENDING,
        impact_score: float = 0.0,
        tags: Optional[list[str]] = None,
        notes: str = "",
    ) -> MemoryEvent:
        """Record a portfolio event.

        Args:
            event_type: Type of event.
            data: Event data payload.
            outcome: Decision outcome classification.
            impact_score: Impact assessment (-1 to +1).
            tags: Searchable tags.
            notes: Human-readable notes.

        Returns:
            The recorded MemoryEvent.
        """
        event = MemoryEvent(
            event_type=event_type,
            data=data,
            outcome=outcome,
            impact_score=impact_score,
            tags=tags or [],
            notes=notes,
        )
        self.events.append(event)

        # Prune old events if exceeding max
        while len(self.events) > self.max_events:
            self.events.pop(0)

        return event

    def record_snapshot(
        self,
        portfolio_value: float,
        daily_return: float = 0.0,
        ytd_return: float = 0.0,
        annual_volatility: float = 0.0,
        sharpe_ratio: float = 0.0,
        max_drawdown: float = 0.0,
        allocations: Optional[dict[str, float]] = None,
        risk_metrics: Optional[dict[str, float]] = None,
    ) -> PerformanceSnapshot:
        """Record a performance snapshot.

        Args:
            portfolio_value: Current portfolio value.
            daily_return: Today's return.
            ytd_return: Year-to-date return.
            annual_volatility: Annualized volatility.
            sharpe_ratio: Current Sharpe ratio.
            max_drawdown: Current maximum drawdown.
            allocations: Current allocation weights.
            risk_metrics: Additional risk metrics.

        Returns:
            The recorded PerformanceSnapshot.
        """
        snapshot = PerformanceSnapshot(
            date=datetime.utcnow(),
            portfolio_value=portfolio_value,
            daily_return=daily_return,
            ytd_return=ytd_return,
            annual_volatility=annual_volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            allocations=allocations or {},
            risk_metrics=risk_metrics or {},
        )
        self.snapshots.append(snapshot)

        # Also record as event
        self.record(
            event_type=MemoryEventType.PERFORMANCE_SNAPSHOT,
            data={
                "portfolio_value": portfolio_value,
                "daily_return": daily_return,
                "sharpe_ratio": sharpe_ratio,
            },
            outcome=DecisionOutcome.POSITIVE if daily_return >= 0 else DecisionOutcome.NEGATIVE,
            impact_score=daily_return,
            tags=["performance", "snapshot"],
        )

        return snapshot

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def recent_events(
        self,
        limit: int = 20,
        event_type: Optional[MemoryEventType] = None,
    ) -> list[MemoryEvent]:
        """Get recent events, optionally filtered by type.

        Args:
            limit: Maximum number of events to return.
            event_type: Filter by event type.

        Returns:
            List of matching MemoryEvents (newest first).
        """
        events = self.events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return list(reversed(events[-limit:]))

    def events_by_type(
        self,
        event_type: MemoryEventType,
    ) -> list[MemoryEvent]:
        """Get all events of a specific type.

        Args:
            event_type: Type to filter by.

        Returns:
            List of matching events.
        """
        return [e for e in self.events if e.event_type == event_type]

    def events_by_tag(self, tag: str) -> list[MemoryEvent]:
        """Get events matching a specific tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of events with matching tag.
        """
        return [e for e in self.events if tag in e.tags]

    def events_by_outcome(
        self,
        outcome: DecisionOutcome,
    ) -> list[MemoryEvent]:
        """Get events with a specific outcome.

        Args:
            outcome: Outcome to filter by.

        Returns:
            List of events with matching outcome.
        """
        return [e for e in self.events if e.outcome == outcome]

    def events_by_date_range(
        self,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> list[MemoryEvent]:
        """Get events within a date range.

        Args:
            start: Start of range.
            end: End of range (default: now).

        Returns:
            List of events in range.
        """
        end = end or datetime.utcnow()
        return [e for e in self.events if start <= e.timestamp <= end]

    def recent_snapshots(
        self,
        limit: int = 20,
    ) -> list[PerformanceSnapshot]:
        """Get recent performance snapshots.

        Args:
            limit: Maximum number of snapshots.

        Returns:
            List of snapshots (newest first).
        """
        return list(reversed(self.snapshots[-limit:]))

    # ------------------------------------------------------------------
    # Analytics & Insights
    # ------------------------------------------------------------------

    def knowledge_base(self) -> dict[str, Any]:
        """Generate knowledge base from accumulated memory.

        Returns:
            Dict with analytics, insights, and summary statistics.
        """
        total_events = len(self.events)
        total_snapshots = len(self.snapshots)

        # Decision effectiveness
        positive_count = len([e for e in self.events if e.outcome == DecisionOutcome.POSITIVE])
        negative_count = len([e for e in self.events if e.outcome == DecisionOutcome.NEGATIVE])
        total_decisions = positive_count + negative_count
        win_rate = positive_count / max(total_decisions, 1)

        # Average impact score
        avg_impact = (
            sum(e.impact_score for e in self.events) / max(total_events, 1)
            if total_events > 0
            else 0.0
        )

        # Event type distribution
        type_dist = {}
        for e in self.events:
            t = e.event_type.value
            type_dist[t] = type_dist.get(t, 0) + 1

        # Performance trends from snapshots
        perf_trend = self._compute_performance_trends()

        # Extract insights
        insights = self._extract_insights()

        return {
            "total_events": total_events,
            "total_snapshots": total_snapshots,
            "decision_count": total_decisions,
            "win_rate": round(win_rate, 4),
            "average_impact": round(avg_impact, 4),
            "event_type_distribution": type_dist,
            "performance_trends": perf_trend,
            "insights": [i.__dict__ for i in insights],
        }

    def _compute_performance_trends(self) -> dict[str, Any]:
        """Compute performance trends from snapshots."""
        if len(self.snapshots) < 2:
            return {"status": "insufficient_data"}

        snapshots = self.snapshots[-30:]  # last 30 days

        returns = [s.daily_return for s in snapshots]
        avg_daily_ret = sum(returns) / len(returns)
        positive_days = sum(1 for r in returns if r > 0)

        # Value trend
        values = [s.portfolio_value for s in snapshots]
        start_val = values[0]
        end_val = values[-1]
        total_return = (end_val / start_val - 1.0) if start_val > 0 else 0.0

        # Volatility of returns
        if len(returns) > 1:
            mean = sum(returns) / len(returns)
            return_vol = (sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
        else:
            return_vol = 0.0

        return {
            "period_days": len(snapshots),
            "start_value": start_val,
            "end_value": end_val,
            "total_return": round(total_return, 6),
            "avg_daily_return": round(avg_daily_ret, 6),
            "positive_day_ratio": round(positive_days / max(len(returns), 1), 4),
            "return_volatility": round(return_vol, 6),
            "max_drawdown": max((s.max_drawdown for s in snapshots), default=0.0),
            "latest_sharpe": snapshots[-1].sharpe_ratio if snapshots else 0.0,
        }

    def _extract_insights(self) -> list[PortfolioInsight]:
        """Extract actionable insights from memory."""
        insights: list[PortfolioInsight] = []

        # Insight 1: Rebalancing frequency effectiveness
        rebalance_events = self.events_by_type(MemoryEventType.REBALANCE)
        if rebalance_events:
            positive_reb = sum(
                1 for e in rebalance_events if e.outcome == DecisionOutcome.POSITIVE
            )
            total_reb = len(rebalance_events)
            insights.append(
                PortfolioInsight(
                    insight_type="rebalance_effectiveness",
                    description=f"Rebalancing decisions were positive in {positive_reb}/{total_reb} cases",
                    confidence=total_reb / max(total_reb + 5, 1),
                    supporting_events=total_reb,
                    recommendation="Continue rebalancing strategy" if positive_reb > total_reb / 2
                    else "Review rebalancing thresholds",
                )
            )

        # Insight 2: Allocation change impact
        alloc_events = self.events_by_type(MemoryEventType.ALLOCATION_CHANGE)
        if alloc_events:
            avg_impact = sum(e.impact_score for e in alloc_events) / len(alloc_events)
            insights.append(
                PortfolioInsight(
                    insight_type="allocation_timing",
                    description=f"Average allocation change impact: {avg_impact:+.4f}",
                    confidence=len(alloc_events) / max(len(alloc_events) + 5, 1),
                    supporting_events=len(alloc_events),
                    recommendation="Allocation changes adding value" if avg_impact > 0
                    else "Review allocation decision process",
                )
            )

        # Insight 3: Exposure breach frequency
        breach_events = self.events_by_type(MemoryEventType.EXPOSURE_BREACH)
        if breach_events:
            insights.append(
                PortfolioInsight(
                    insight_type="exposure_management",
                    description=f"{len(breach_events)} exposure breaches recorded",
                    confidence=0.9,
                    supporting_events=len(breach_events),
                    recommendation="Review exposure limits" if len(breach_events) > 5
                    else "Current exposure controls adequate",
                )
            )

        # Insight 4: Win rate trend
        pos = len(self.events_by_outcome(DecisionOutcome.POSITIVE))
        neg = len(self.events_by_outcome(DecisionOutcome.NEGATIVE))
        total_d = pos + neg
        if total_d > 0:
            wr = pos / total_d
            insights.append(
                PortfolioInsight(
                    insight_type="decision_quality",
                    description=f"Overall decision win rate: {wr:.1%}",
                    confidence=total_d / max(total_d + 10, 1),
                    supporting_events=total_d,
                    recommendation="Good decision framework" if wr >= 0.55
                    else "Improve decision quality",
                )
            )

        return insights

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_status(self) -> dict[str, Any]:
        """Quick memory status summary.

        Returns:
            Dict with event count, snapshot count, and recent activity.
        """
        recent = self.recent_events(limit=5)
        return {
            "total_events": len(self.events),
            "total_snapshots": len(self.snapshots),
            "recent_activity": [
                {
                    "type": e.event_type.value,
                    "outcome": e.outcome.value,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in recent
            ],
        }

    def clear(self) -> None:
        """Reset all memory."""
        self.events.clear()
        self.snapshots.clear()
