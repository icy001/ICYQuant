from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    EARNINGS = "EARNINGS"
    FED_MEETING = "FED_MEETING"
    ECONOMIC_DATA = "ECONOMIC_DATA"
    POLICY_CHANGE = "POLICY_CHANGE"
    GEOPOLITICAL = "GEOPOLITICAL"
    INDUSTRY = "INDUSTRY"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    IPO = "IPO"
    REGULATORY = "REGULATORY"


class EventSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class MarketEvent:
    event_id: str
    event_type: EventType
    title: str
    description: str
    severity: EventSeverity
    expected_date: str
    affected_symbols: List[str] = field(default_factory=list)
    expected_impact: str = "UNKNOWN"


@dataclass
class EventAnalysis:
    event: MarketEvent
    market_reaction: str  # EXPECTED / ABOVE_EXPECTATIONS / BELOW_EXPECTATIONS
    immediate_impact_score: float  # 0-100
    lasting_impact_score: float  # 0-100
    confidence: float
    trading_implication: str
    related_events: List[str] = field(default_factory=list)


class EventIntelligenceEngine:
    """Event Intelligence Engine - analyzes market events and their implications."""

    def __init__(self):
        self.event_history: List[EventAnalysis] = []

    def analyze(self, event):
        """Analyze a market event.

        Args:
            event: Event data - can be MarketEvent dataclass or dict/symbol.

        Returns:
            Dict containing event analysis result.
        """
        if isinstance(event, MarketEvent):
            return self._analyze_event(event)
        return {"event": event}

    def _analyze_event(self, event: MarketEvent) -> dict:
        immediate_impact = self._calculate_immediate_impact(event)
        lasting_impact = self._calculate_lasting_impact(event)
        reaction = self._assess_market_reaction(event)
        trading_implication = self._derive_trading_implication(event, immediate_impact)

        return {
            "event": {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "title": event.title,
                "severity": event.severity.value,
                "expected_date": event.expected_date,
                "affected_symbols": event.affected_symbols,
                "immediate_impact_score": immediate_impact,
                "lasting_impact_score": lasting_impact,
                "market_reaction": reaction,
                "trading_implication": trading_implication,
            }
        }

    def _calculate_immediate_impact(self, event: MarketEvent) -> int:
        base = {
            EventSeverity.LOW: 10,
            EventSeverity.MEDIUM: 30,
            EventSeverity.HIGH: 60,
            EventSeverity.CRITICAL: 90,
        }.get(event.severity, 20)

        # Event type modifiers
        type_modifier = {
            EventType.FED_MEETING: 1.3,
            EventType.GEOPOLITICAL: 1.2,
            EventType.POLICY_CHANGE: 1.1,
            EventType.EARNINGS: 0.8,
            EventType.INDUSTRY: 0.7,
        }.get(event.event_type, 1.0)

        return min(100, int(base * type_modifier))

    def _calculate_lasting_impact(self, event: MarketEvent) -> int:
        base = {
            EventSeverity.LOW: 5,
            EventSeverity.MEDIUM: 20,
            EventSeverity.HIGH: 50,
            EventSeverity.CRITICAL: 80,
        }.get(event.severity, 15)

        type_modifier = {
            EventType.POLICY_CHANGE: 1.5,
            EventType.REGULATORY: 1.3,
            EventType.GEOPOLITICAL: 1.2,
            EventType.FED_MEETING: 1.1,
            EventType.EARNINGS: 0.6,
        }.get(event.event_type, 1.0)

        return min(100, int(base * type_modifier))

    def _assess_market_reaction(self, event: MarketEvent) -> str:
        if event.severity in (EventSeverity.HIGH, EventSeverity.CRITICAL):
            return "EXPECTED"
        return "EXPECTED"

    def _derive_trading_implication(self, event: MarketEvent, impact_score: int) -> str:
        if impact_score >= 70:
            return "Significant event - consider position adjustment before event"
        elif impact_score >= 40:
            return "Moderate event - monitor positions for volatility"
        else:
            return "Minor event - maintain current positions"
