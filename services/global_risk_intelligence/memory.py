"""Risk Memory.

Records risk events, portfolio reactions, defense results, and
recovery times to build an institutional risk knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class RiskEvent:
    """A recorded risk event with outcomes.

    Attributes:
        event_id: Unique event identifier.
        event_type: Type of risk event.
        date: Event date.
        risk_level: Risk level at event time.
        systemic_score: Systemic risk score.
        volatility_regime: Volatility regime at event time.
        portfolio_reaction: Portfolio adjustment taken.
        defense_result: Outcome of defensive actions.
        recovery_time_days: Days to portfolio recovery.
        peak_drawdown: Peak drawdown during event.
        description: Event description.
        lessons: Key lessons learned.
        metadata: Additional context.
    """

    event_id: int = 0
    event_type: str = ""
    date: datetime = field(default_factory=datetime.now)
    risk_level: str = "normal"
    systemic_score: float = 0.0
    volatility_regime: str = "normal_vol"
    portfolio_reaction: str = ""
    defense_result: str = ""
    recovery_time_days: int = 0
    peak_drawdown: float = 0.0
    description: str = ""
    lessons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskKnowledgeBase:
    """Aggregated risk knowledge from historical events.

    Attributes:
        total_events: Total recorded events.
        avg_recovery_days: Average recovery time.
        max_drawdown: Historical maximum drawdown.
        most_common_regime: Most frequent crisis regime.
        event_type_frequency: Distribution of event types.
        defense_effectiveness: Effectiveness score by defense action.
    """

    total_events: int = 0
    avg_recovery_days: float = 0.0
    max_drawdown: float = 0.0
    most_common_regime: str = ""
    event_type_frequency: dict[str, int] = field(default_factory=dict)
    defense_effectiveness: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RiskMemory:
    """Records and analyzes risk events for institutional learning.

    Maintains a historical record of risk events, portfolio reactions,
    defense outcomes, and recovery metrics to improve future risk
    response.

    Attributes:
        events: Recorded risk events.
        _counter: Auto-increment event ID.
    """

    def __init__(self) -> None:
        self.events: list[RiskEvent] = []
        self._counter: int = 0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self,
               event_type: str = "",
               risk_level: str = "normal",
               systemic_score: float = 0.0,
               volatility_regime: str = "normal_vol",
               portfolio_reaction: str = "",
               defense_result: str = "",
               recovery_time_days: int = 0,
               peak_drawdown: float = 0.0,
               description: str = "",
               lessons: Optional[list[str]] = None,
               metadata: Optional[dict[str, Any]] = None,
               ) -> RiskEvent:
        """Record a risk event.

        Returns:
            The recorded RiskEvent.
        """
        self._counter += 1
        event = RiskEvent(
            event_id=self._counter,
            event_type=event_type,
            risk_level=risk_level,
            systemic_score=systemic_score,
            volatility_regime=volatility_regime,
            portfolio_reaction=portfolio_reaction,
            defense_result=defense_result,
            recovery_time_days=recovery_time_days,
            peak_drawdown=peak_drawdown,
            description=description,
            lessons=lessons or [],
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def recent_events(self, n: int = 10) -> list[RiskEvent]:
        """Return the most recent n events."""
        return self.events[-n:] if self.events else []

    def events_by_type(self, event_type: str) -> list[RiskEvent]:
        """Return all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def events_by_level(self, risk_level: str) -> list[RiskEvent]:
        """Return all events at a specific risk level."""
        return [e for e in self.events if e.risk_level == risk_level]

    def events_by_regime(self, regime: str) -> list[RiskEvent]:
        """Return all events during a specific volatility regime."""
        return [e for e in self.events if e.volatility_regime == regime]

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def knowledge_base(self) -> RiskKnowledgeBase:
        """Build an aggregated risk knowledge base from history."""
        if not self.events:
            return RiskKnowledgeBase()

        total = len(self.events)
        avg_recovery = (
            sum(e.recovery_time_days for e in self.events) / total
        )
        max_dd = max(e.peak_drawdown for e in self.events)

        # Regime frequency
        regime_freq: dict[str, int] = {}
        for e in self.events:
            regime_freq[e.volatility_regime] = (
                regime_freq.get(e.volatility_regime, 0) + 1
            )
        most_common = max(regime_freq, key=regime_freq.get) if regime_freq else ""

        # Event type frequency
        type_freq: dict[str, int] = {}
        for e in self.events:
            type_freq[e.event_type] = type_freq.get(e.event_type, 0) + 1

        # Defense effectiveness
        defense_eff: dict[str, float] = {}
        action_counts: dict[str, int] = {}
        for e in self.events:
            action = e.portfolio_reaction
            if not action:
                continue
            action_counts[action] = action_counts.get(action, 0) + 1
            # Simple heuristic: shorter recovery = better defense
            effectiveness = max(0.0, 1.0 - e.recovery_time_days / 90)
            defense_eff[action] = (
                defense_eff.get(action, 0.0) * (action_counts[action] - 1)
                + effectiveness
            ) / action_counts[action]

        return RiskKnowledgeBase(
            total_events=total,
            avg_recovery_days=round(avg_recovery, 1),
            max_drawdown=max_dd,
            most_common_regime=most_common,
            event_type_frequency=type_freq,
            defense_effectiveness=defense_eff,
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Quick summary of risk memory."""
        kb = self.knowledge_base()
        return {
            "total_events": kb.total_events,
            "avg_recovery_days": kb.avg_recovery_days,
            "max_drawdown": kb.max_drawdown,
            "most_common_regime": kb.most_common_regime,
            "recent": [
                {"id": e.event_id, "type": e.event_type,
                 "risk": e.risk_level, "dd": e.peak_drawdown}
                for e in self.recent_events(5)
            ],
        }

    def clear(self) -> None:
        self.events.clear()
        self._counter = 0
