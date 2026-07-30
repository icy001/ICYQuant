"""
Event-driven Alpha Signal Engine.

Converts knowledge events into trading signals:
- Event → Signal mapping
- Confidence-weighted signals
- Multi-event signal aggregation
- Knowledge graph propagation for signal discovery
- Signal pipeline integration
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from services.knowledge.event_engine import MarketEvent, EventType, EventImpact
from services.knowledge.knowledge_graph import KnowledgeGraph, NodeType, EdgeType
from services.knowledge.sentiment import SentimentEngine, SentimentDirection

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    OVERWEIGHT = "OVERWEIGHT"
    UNDERWEIGHT = "UNDERWEIGHT"


class SignalConfidence(str, Enum):
    VERY_HIGH = "very_high"  # > 0.8
    HIGH = "high"            # 0.6 - 0.8
    MEDIUM = "medium"        # 0.4 - 0.6
    LOW = "low"              # 0.2 - 0.4
    VERY_LOW = "very_low"    # < 0.2


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AlphaSignal:
    """A trading signal derived from knowledge events."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    signal_type: SignalType = SignalType.HOLD
    confidence: float = 0.0
    confidence_level: SignalConfidence = SignalConfidence.LOW

    # Source events
    source_events: List[str] = field(default_factory=list)  # event IDs
    event_count: int = 0

    # Scores
    alpha_score: float = 0.0  # -1.0 to 1.0
    sentiment_score: float = 0.5
    impact_score: float = 0.0

    # Time horizon
    horizon: str = "short_term"  # intraday, short_term, medium_term, long_term

    # Propagation
    propagated: bool = False
    propagation_path: List[str] = field(default_factory=list)

    # Expiry
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    # Reason
    reason: str = ""
    description: str = ""

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "alpha_score": self.alpha_score,
            "sentiment_score": self.sentiment_score,
            "impact_score": self.impact_score,
            "horizon": self.horizon,
            "propagated": self.propagated,
            "reason": self.reason,
            "generated_at": self.generated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class EventToSignalMapping:
    """Maps event types to signal characteristics."""

    event_type: EventType
    base_signal: SignalType
    base_impact: float  # -1.0 to 1.0
    default_horizon: str = "short_term"
    confidence_modifier: float = 1.0


@dataclass
class SignalPipeline:
    """A pipeline of signals for a strategy."""

    pipeline_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signals: List[AlphaSignal] = field(default_factory=list)
    aggregated_signal: Optional[AlphaSignal] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AlphaConfig:
    """Configuration for the alpha signal engine."""

    # Signal generation
    min_confidence: float = 0.3
    min_events_for_signal: int = 1

    # Confidence thresholds
    very_high_conf: float = 0.8
    high_conf: float = 0.6
    medium_conf: float = 0.4
    low_conf: float = 0.2

    # Signal expiry
    intraday_expiry_hours: int = 8
    short_term_expiry_hours: int = 48
    medium_term_expiry_hours: int = 168  # 1 week
    long_term_expiry_hours: int = 720  # 30 days

    # Propagation
    enable_graph_propagation: bool = True
    max_propagation_depth: int = 2
    propagation_decay: float = 0.5  # confidence decay per hop

    # Aggregation
    aggregate_window_hours: int = 24
    max_signals_per_symbol: int = 50


# ── Event → Signal Mapping Table ─────────────────────────────────────────────

DEFAULT_EVENT_SIGNAL_MAP: Dict[EventType, EventToSignalMapping] = {
    EventType.EARNINGS_SURPRISE: EventToSignalMapping(
        EventType.EARNINGS_SURPRISE, SignalType.BUY, 0.7, "medium_term", 1.2
    ),
    EventType.EARNINGS_MISS: EventToSignalMapping(
        EventType.EARNINGS_MISS, SignalType.SELL, -0.7, "medium_term", 1.2
    ),
    EventType.GUIDANCE_RAISED: EventToSignalMapping(
        EventType.GUIDANCE_RAISED, SignalType.BUY, 0.6, "medium_term", 1.0
    ),
    EventType.GUIDANCE_LOWERED: EventToSignalMapping(
        EventType.GUIDANCE_LOWERED, SignalType.SELL, -0.6, "medium_term", 1.0
    ),
    EventType.PRODUCT_LAUNCH: EventToSignalMapping(
        EventType.PRODUCT_LAUNCH, SignalType.BUY, 0.5, "short_term", 0.8
    ),
    EventType.PRODUCT_RECALL: EventToSignalMapping(
        EventType.PRODUCT_RECALL, SignalType.SELL, -0.6, "short_term", 0.9
    ),
    EventType.M_AND_A_ANNOUNCED: EventToSignalMapping(
        EventType.M_AND_A_ANNOUNCED, SignalType.BUY, 0.5, "medium_term", 0.8
    ),
    EventType.M_AND_A_COMPLETED: EventToSignalMapping(
        EventType.M_AND_A_COMPLETED, SignalType.BUY, 0.3, "medium_term", 0.5
    ),
    EventType.M_AND_A_TERMINATED: EventToSignalMapping(
        EventType.M_AND_A_TERMINATED, SignalType.SELL, -0.3, "short_term", 0.5
    ),
    EventType.REGULATION_FINE: EventToSignalMapping(
        EventType.REGULATION_FINE, SignalType.SELL, -0.7, "short_term", 1.0
    ),
    EventType.REGULATION_NEW: EventToSignalMapping(
        EventType.REGULATION_NEW, SignalType.BUY, 0.4, "medium_term", 0.6
    ),
    EventType.SUPPLY_CHAIN_DISRUPTION: EventToSignalMapping(
        EventType.SUPPLY_CHAIN_DISRUPTION, SignalType.SELL, -0.5, "short_term", 0.7
    ),
    EventType.SUPPLY_CHAIN_EXPANSION: EventToSignalMapping(
        EventType.SUPPLY_CHAIN_EXPANSION, SignalType.BUY, 0.4, "medium_term", 0.6
    ),
    EventType.CAPEX_INCREASE: EventToSignalMapping(
        EventType.CAPEX_INCREASE, SignalType.BUY, 0.4, "long_term", 0.8
    ),
    EventType.CAPEX_DECREASE: EventToSignalMapping(
        EventType.CAPEX_DECREASE, SignalType.SELL, -0.3, "medium_term", 0.6
    ),
    EventType.MANAGEMENT_APPOINTMENT: EventToSignalMapping(
        EventType.MANAGEMENT_APPOINTMENT, SignalType.BUY, 0.1, "medium_term", 0.4
    ),
    EventType.MANAGEMENT_RESIGNATION: EventToSignalMapping(
        EventType.MANAGEMENT_RESIGNATION, SignalType.SELL, -0.3, "short_term", 0.6
    ),
    EventType.DIVIDEND_INCREASE: EventToSignalMapping(
        EventType.DIVIDEND_INCREASE, SignalType.BUY, 0.4, "medium_term", 0.6
    ),
    EventType.DIVIDEND_DECREASE: EventToSignalMapping(
        EventType.DIVIDEND_DECREASE, SignalType.SELL, -0.4, "short_term", 0.6
    ),
    EventType.BUYBACK_ANNOUNCED: EventToSignalMapping(
        EventType.BUYBACK_ANNOUNCED, SignalType.BUY, 0.3, "medium_term", 0.6
    ),
    EventType.BANKRUPTCY: EventToSignalMapping(
        EventType.BANKRUPTCY, SignalType.SELL, -0.9, "long_term", 1.5
    ),
    EventType.FDA_APPROVAL: EventToSignalMapping(
        EventType.FDA_APPROVAL, SignalType.BUY, 0.7, "medium_term", 1.2
    ),
    EventType.ANALYST_UPGRADE: EventToSignalMapping(
        EventType.ANALYST_UPGRADE, SignalType.BUY, 0.5, "short_term", 0.7
    ),
    EventType.ANALYST_DOWNGRADE: EventToSignalMapping(
        EventType.ANALYST_DOWNGRADE, SignalType.SELL, -0.5, "short_term", 0.7
    ),
    EventType.PARTNERSHIP: EventToSignalMapping(
        EventType.PARTNERSHIP, SignalType.BUY, 0.3, "medium_term", 0.5
    ),
    EventType.MACRO_RATE_HIKE: EventToSignalMapping(
        EventType.MACRO_RATE_HIKE, SignalType.SELL, -0.4, "medium_term", 0.6
    ),
    EventType.MACRO_RATE_CUT: EventToSignalMapping(
        EventType.MACRO_RATE_CUT, SignalType.BUY, 0.4, "medium_term", 0.6
    ),
}


# ── Event Alpha Engine ───────────────────────────────────────────────────────

class EventAlphaEngine:
    """
    Event-driven alpha signal engine.

    Converts market events into actionable trading signals
    with confidence scoring, knowledge graph propagation,
    and multi-signal aggregation.
    """

    def __init__(
        self,
        config: Optional[AlphaConfig] = None,
        knowledge_graph: Optional[KnowledgeGraph] = None,
    ):
        self.config = config or AlphaConfig()
        self.graph = knowledge_graph or KnowledgeGraph()
        self._signals: List[AlphaSignal] = []
        self._event_signal_map: Dict[EventType, EventToSignalMapping] = dict(
            DEFAULT_EVENT_SIGNAL_MAP
        )
        self._pipelines: Dict[str, SignalPipeline] = {}

    # ── Signal Generation ────────────────────────────────────────────────────

    def generate_signals(
        self, events: List[MarketEvent]
    ) -> List[AlphaSignal]:
        """
        Generate alpha signals from market events.

        Each event is mapped to a signal based on its event type,
        impact, and confidence.
        """
        signals: List[AlphaSignal] = []

        for event in events:
            mapping = self._event_signal_map.get(event.event_type)
            if not mapping:
                logger.debug(f"No signal mapping for event type: {event.event_type}")
                continue

            # Compute alpha score from event impact and confidence
            alpha_score = (
                event.impact_score * event.confidence * mapping.confidence_modifier
            )
            # Clamp to [-1, 1]
            alpha_score = max(-1.0, min(1.0, alpha_score))

            # Determine signal type based on alpha_score sign
            # The alpha_score already encodes the direction (positive=good, negative=bad)
            if abs(alpha_score) < 0.05:
                signal_type = SignalType.HOLD
            elif alpha_score > 0:
                signal_type = SignalType.BUY
            else:
                signal_type = SignalType.SELL

            # Compute confidence
            confidence = event.confidence * mapping.confidence_modifier
            confidence = min(confidence, 1.0)

            if confidence < self.config.min_confidence:
                continue

            # Determine horizon
            horizon = mapping.default_horizon

            # Set expiry
            expires_at = self._compute_expiry(horizon)

            # For primary entity
            if event.primary_entity:
                signal = AlphaSignal(
                    symbol=event.primary_entity,
                    signal_type=signal_type,
                    confidence=confidence,
                    confidence_level=self._confidence_to_level(confidence),
                    source_events=[event.event_id],
                    event_count=1,
                    alpha_score=alpha_score,
                    impact_score=event.impact_score,
                    horizon=horizon,
                    expires_at=expires_at,
                    reason=f"{event.event_type.value}: {event.description[:100]}",
                    description=f"Generated from {event.event_type.value} event",
                )
                signals.append(signal)

            # For affected symbols
            for symbol in event.affected_symbols:
                if symbol != event.primary_entity:
                    # Slightly lower confidence for affected entities
                    affected_confidence = confidence * 0.8
                    signal = AlphaSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence=affected_confidence,
                        confidence_level=self._confidence_to_level(affected_confidence),
                        source_events=[event.event_id],
                        event_count=1,
                        alpha_score=alpha_score * 0.8,
                        impact_score=event.impact_score * 0.8,
                        horizon=horizon,
                        expires_at=expires_at,
                        reason=f"Affected by {event.primary_entity} {event.event_type.value}",
                    )
                    signals.append(signal)

        self._signals.extend(signals)
        return signals

    # ── Knowledge Graph Propagation ──────────────────────────────────────────

    def propagate_signals(
        self, signals: List[AlphaSignal]
    ) -> List[AlphaSignal]:
        """
        Propagate signals through the knowledge graph.

        Discovers supply chain / value chain entities that may
        be affected by the original signal.
        """
        if not self.config.enable_graph_propagation:
            return []

        propagated: List[AlphaSignal] = []
        supply_types = {
            EdgeType.SUPPLIER_OF, EdgeType.SUPPLY_CHAIN,
            EdgeType.DEPENDS_ON, EdgeType.CUSTOMER_OF,
            EdgeType.PRODUCES, EdgeType.USES,
        }

        for signal in signals:
            node = self.graph.find_node(signal.symbol)
            if not node:
                continue

            # BFS from the signal's entity
            bfs_result = self.graph.bfs(
                node.node_id,
                self.config.max_propagation_depth,
                list(supply_types),
            )

            for depth, node_ids in bfs_result.items():
                if depth == 0:
                    continue

                decay = self.config.propagation_decay ** depth
                for nid in node_ids:
                    target_node = self.graph.get_node(nid)
                    if not target_node or not target_node.ticker:
                        continue

                    prop_confidence = signal.confidence * decay
                    if prop_confidence < self.config.min_confidence:
                        continue

                    prop_signal = AlphaSignal(
                        symbol=target_node.ticker,
                        signal_type=signal.signal_type,
                        confidence=prop_confidence,
                        confidence_level=self._confidence_to_level(prop_confidence),
                        source_events=signal.source_events,
                        event_count=signal.event_count,
                        alpha_score=signal.alpha_score * decay,
                        impact_score=signal.impact_score * decay,
                        horizon=signal.horizon,
                        propagated=True,
                        propagation_path=signal.propagation_path + [target_node.name],
                        expires_at=signal.expires_at,
                        reason=f"Propagated from {signal.symbol} at depth {depth}",
                    )
                    propagated.append(prop_signal)

                    # Also track in the original signal
                    if target_node.name not in signal.propagation_path:
                        signal.propagation_path.append(target_node.name)

        self._signals.extend(propagated)
        return propagated

    # ── Signal Aggregation ───────────────────────────────────────────────────

    def aggregate_signals(
        self, symbol: str, window_hours: Optional[int] = None
    ) -> Optional[AlphaSignal]:
        """
        Aggregate all recent signals for a symbol into a single signal.

        Multiple positive events → stronger BUY, conflicting → HOLD.
        """
        window = window_hours or self.config.aggregate_window_hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window)

        relevant = [
            s for s in self._signals
            if s.symbol.upper() == symbol.upper()
            and s.generated_at >= cutoff
        ]

        if not relevant:
            return None

        if len(relevant) < self.config.min_events_for_signal:
            return None

        # Weighted aggregation
        total_alpha = 0.0
        total_weight = 0.0
        all_event_ids = []
        horizons = defaultdict(int)
        reasons = []

        for signal in relevant:
            weight = signal.confidence
            total_alpha += signal.alpha_score * weight
            total_weight += weight
            all_event_ids.extend(signal.source_events)
            horizons[signal.horizon] += 1
            if signal.reason:
                reasons.append(signal.reason)

        if total_weight == 0:
            return None

        aggregated_alpha = total_alpha / total_weight
        aggregated_confidence = total_weight / len(relevant)

        # Signal type
        if abs(aggregated_alpha) < 0.03:
            signal_type = SignalType.HOLD
        elif aggregated_alpha > 0:
            signal_type = SignalType.BUY
        else:
            signal_type = SignalType.SELL

        # Dominant horizon
        dominant_horizon = max(horizons, key=horizons.get) if horizons else "short_term"

        unique_reasons = list(set(reasons))
        reason_text = f"Aggregated from {len(relevant)} signals: " + "; ".join(
            unique_reasons[:3]
        )

        return AlphaSignal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=aggregated_confidence,
            confidence_level=self._confidence_to_level(aggregated_confidence),
            source_events=list(set(all_event_ids)),
            event_count=len(relevant),
            alpha_score=aggregated_alpha,
            impact_score=0.0,
            horizon=dominant_horizon,
            reason=reason_text,
            description=f"Aggregated signal from {len(relevant)} events",
        )

    def aggregate_all(
        self, window_hours: Optional[int] = None
    ) -> List[AlphaSignal]:
        """Aggregate signals for all symbols with recent activity."""
        symbols = set(s.symbol for s in self._signals)
        aggregated = []
        for symbol in symbols:
            agg = self.aggregate_signals(symbol, window_hours)
            if agg:
                aggregated.append(agg)
        return aggregated

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def create_pipeline(self, name: str) -> SignalPipeline:
        """Create a named signal pipeline."""
        pipeline = SignalPipeline(name=name)
        self._pipelines[pipeline.pipeline_id] = pipeline
        return pipeline

    def add_to_pipeline(
        self, pipeline_id: str, signals: List[AlphaSignal]
    ) -> None:
        """Add signals to a pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if pipeline:
            pipeline.signals.extend(signals)

    def aggregate_pipeline(self, pipeline_id: str) -> Optional[AlphaSignal]:
        """Aggregate all signals in a pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or not pipeline.signals:
            return None

        symbols = set(s.symbol for s in pipeline.signals)
        pipeline_signals = []

        for symbol in symbols:
            # Temporarily use pipeline signals as source
            saved = self._signals
            self._signals = pipeline.signals
            agg = self.aggregate_signals(symbol)
            self._signals = saved
            if agg:
                pipeline_signals.append(agg)

        if pipeline_signals:
            pipeline.aggregated_signal = pipeline_signals[0]
            return pipeline_signals[0]

        return None

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_signals(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        min_confidence: float = 0.0,
        exclude_expired: bool = True,
        limit: int = 100,
    ) -> List[AlphaSignal]:
        """Query generated signals."""
        results = self._signals

        if symbol:
            results = [s for s in results if s.symbol.upper() == symbol.upper()]
        if signal_type:
            results = [s for s in results if s.signal_type == signal_type]
        if min_confidence > 0:
            results = [s for s in results if s.confidence >= min_confidence]
        if exclude_expired:
            now = datetime.now(timezone.utc)
            results = [
                s for s in results
                if s.expires_at is None or s.expires_at > now
            ]

        return results[-limit:]

    def get_latest_signal(self, symbol: str) -> Optional[AlphaSignal]:
        """Get the latest signal for a symbol."""
        signals = self.get_signals(symbol=symbol, exclude_expired=True)
        if not signals:
            return None
        return max(signals, key=lambda s: s.generated_at)

    def get_active_buy_signals(
        self, min_confidence: float = 0.4
    ) -> List[AlphaSignal]:
        """Get all active BUY signals."""
        return self.get_signals(
            signal_type=SignalType.BUY,
            min_confidence=min_confidence,
        )

    def get_active_sell_signals(
        self, min_confidence: float = 0.4
    ) -> List[AlphaSignal]:
        """Get all active SELL signals."""
        return self.get_signals(
            signal_type=SignalType.SELL,
            min_confidence=min_confidence,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _confidence_to_level(self, confidence: float) -> SignalConfidence:
        if confidence >= self.config.very_high_conf:
            return SignalConfidence.VERY_HIGH
        elif confidence >= self.config.high_conf:
            return SignalConfidence.HIGH
        elif confidence >= self.config.medium_conf:
            return SignalConfidence.MEDIUM
        elif confidence >= self.config.low_conf:
            return SignalConfidence.LOW
        else:
            return SignalConfidence.VERY_LOW

    def _compute_expiry(self, horizon: str) -> datetime:
        """Compute signal expiry based on horizon."""
        now = datetime.now(timezone.utc)
        hours = {
            "intraday": self.config.intraday_expiry_hours,
            "short_term": self.config.short_term_expiry_hours,
            "medium_term": self.config.medium_term_expiry_hours,
            "long_term": self.config.long_term_expiry_hours,
        }.get(horizon, self.config.short_term_expiry_hours)
        return now + timedelta(hours=hours)

    def add_event_mapping(self, mapping: EventToSignalMapping) -> None:
        """Add or override an event-to-signal mapping."""
        self._event_signal_map[mapping.event_type] = mapping

    def clear(self) -> None:
        """Clear all signals."""
        self._signals.clear()
        self._pipelines.clear()
