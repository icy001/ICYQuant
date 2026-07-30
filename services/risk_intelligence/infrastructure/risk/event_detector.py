import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RiskEventLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class RiskEvent:
    event_id: str
    level: str
    event_type: str
    description: str
    timestamp: int
    metadata: Dict = field(default_factory=dict)


class RiskEventDetector:
    def __init__(self):
        self.event_history: List[RiskEvent] = []
        self.event_counter = 0

    def _generate_event_id(self) -> str:
        self.event_counter += 1
        return f"EVT{self.event_counter:04d}"

    def detect_price_collapse(
        self, index_decline: float, threshold: float = -0.05
    ) -> Optional[RiskEvent]:
        if index_decline <= threshold:
            level = (
                RiskEventLevel.EMERGENCY.value
                if index_decline <= -0.15
                else RiskEventLevel.CRITICAL.value
            )
            event = RiskEvent(
                event_id=self._generate_event_id(),
                level=level,
                event_type="PRICE_COLLAPSE",
                description=f"Index decline {index_decline:.2%} exceeds threshold {threshold:.2%}",
                timestamp=int(time.time()),
                metadata={"index_decline": index_decline, "threshold": threshold},
            )
            self.event_history.append(event)
            return event
        return None

    def detect_volatility_spike(
        self, vix_change: float, threshold: float = 0.5
    ) -> Optional[RiskEvent]:
        if vix_change >= threshold:
            level = (
                RiskEventLevel.EMERGENCY.value
                if vix_change >= 1.5
                else RiskEventLevel.CRITICAL.value
                if vix_change >= 1.0
                else RiskEventLevel.WARNING.value
            )
            event = RiskEvent(
                event_id=self._generate_event_id(),
                level=level,
                event_type="VOLATILITY_SPIKE",
                description=f"VIX change {vix_change:.1f} exceeds threshold {threshold:.1f}",
                timestamp=int(time.time()),
                metadata={"vix_change": vix_change, "threshold": threshold},
            )
            self.event_history.append(event)
            return event
        return None

    def detect_liquidity_crisis(
        self, spread: float, threshold: float = 0.005
    ) -> Optional[RiskEvent]:
        if spread >= threshold:
            level = (
                RiskEventLevel.CRITICAL.value
                if spread >= 0.01
                else RiskEventLevel.WARNING.value
            )
            event = RiskEvent(
                event_id=self._generate_event_id(),
                level=level,
                event_type="LIQUIDITY_CRISIS",
                description=f"Bid-ask spread {spread:.4f} exceeds threshold {threshold:.4f}",
                timestamp=int(time.time()),
                metadata={"spread": spread, "threshold": threshold},
            )
            self.event_history.append(event)
            return event
        return None

    def detect_abnormal_volume(
        self, volume_surge: float, threshold: float = 3.0
    ) -> Optional[RiskEvent]:
        if volume_surge >= threshold:
            level = (
                RiskEventLevel.CRITICAL.value
                if volume_surge >= 5.0
                else RiskEventLevel.WARNING.value
            )
            event = RiskEvent(
                event_id=self._generate_event_id(),
                level=level,
                event_type="ABNORMAL_VOLUME",
                description=f"Volume surge {volume_surge:.1f}x exceeds threshold {threshold:.1f}x",
                timestamp=int(time.time()),
                metadata={"volume_surge": volume_surge, "threshold": threshold},
            )
            self.event_history.append(event)
            return event
        return None

    def get_recent_events(
        self, count: int = 20, level: str = None
    ) -> List[RiskEvent]:
        events = self.event_history[-count:]
        if level:
            events = [e for e in events if e.level == level]
        return events

    def get_event_count_by_level(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for event in self.event_history:
            counts[event.level] = counts.get(event.level, 0) + 1
        return counts
