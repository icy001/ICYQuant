"""Decision Collector – collects AI decisions from all modules into Decision Events."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DecisionEvent:
    """Unified decision event from any AI/strategy/risk module."""

    strategy: str
    signal: str
    confidence: float

    # Optional rich fields
    symbol: Optional[str] = None
    source: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionCollector:
    """Collects and normalizes decisions from all upstream intelligence engines."""

    def __init__(self) -> None:
        self._events: List[DecisionEvent] = []

    def collect(
        self,
        strategy: str,
        signal: str,
        confidence: float,
        symbol: Optional[str] = None,
        source: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionEvent:
        event = DecisionEvent(
            strategy=strategy,
            signal=signal,
            confidence=confidence,
            symbol=symbol,
            source=source,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def flush(self) -> List[DecisionEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    @property
    def event_count(self) -> int:
        return len(self._events)
