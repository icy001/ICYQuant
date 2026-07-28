"""Order Book Memory — historical microstructure data & knowledge base.

Records order book snapshots, large orders, liquidity events, and
alpha signal accuracy. Builds a microstructure knowledge base for
backtesting and model improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from services.order_book_intelligence.snapshot import OrderBookSnapshot


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MicrostructureEvent(str, Enum):
    """Microstructure event types for memory recording."""

    ORDER_BOOK_SNAPSHOT = "order_book_snapshot"
    IMBALANCE_EXTREME = "imbalance_extreme"
    WALL_DETECTED = "wall_detected"
    WALL_BREACHED = "wall_breached"
    ICEBERG_DETECTED = "iceberg_detected"
    ICEBERG_DISSOLVED = "iceberg_dissolved"
    LARGE_ORDER = "large_order"
    SWEEP = "sweep"
    TOXICITY_SPIKE = "toxicity_spike"
    HIDDEN_LIQUIDITY = "hidden_liquidity"
    ALPHA_SIGNAL = "alpha_signal"
    ALPHA_CONFIRMED = "alpha_confirmed"
    ALPHA_FAILED = "alpha_failed"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class MicrostructureRecord:
    """Single microstructure event record.

    Attributes:
        event_type: Type of microstructure event.
        data: Event data payload.
        symbol: Trading symbol.
        price: Reference price for the event.
        timestamp: Event time.
        metadata: Additional context.
    """

    event_type: MicrostructureEvent
    data: dict[str, Any]
    symbol: str = ""
    price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "event_type": self.event_type.value,
            "symbol": self.symbol,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class AlphaAccuracy:
    """Alpha signal accuracy tracking.

    Attributes:
        total_signals: Total alpha signals generated.
        confirmed_signals: Signals that led to correct prediction.
        failed_signals: Signals that led to incorrect prediction.
        accuracy: Win rate (confirmed / total).
        avg_magnitude_correct: Average alpha magnitude for correct signals.
        avg_magnitude_incorrect: Average alpha magnitude for incorrect.
    """

    total_signals: int = 0
    confirmed_signals: int = 0
    failed_signals: int = 0
    accuracy: float = 0.0
    avg_magnitude_correct: float = 0.0
    avg_magnitude_incorrect: float = 0.0


@dataclass
class MicrostructureKnowledgeBase:
    """Aggregated microstructure knowledge.

    Attributes:
        total_events: Total recorded events.
        event_distribution: Event type → count mapping.
        alpha_accuracy: Alpha signal accuracy stats.
        top_wall_prices: Most frequent liquidity wall prices.
        avg_toxicity: Average observed toxicity.
        avg_imbalance: Average observed imbalance.
        insights: List of extracted insights.
    """

    total_events: int = 0
    event_distribution: dict[str, int] = field(default_factory=dict)
    alpha_accuracy: Optional[AlphaAccuracy] = None
    top_wall_prices: list[float] = field(default_factory=list)
    avg_toxicity: float = 0.0
    avg_imbalance: float = 0.0
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "total_events": self.total_events,
            "event_distribution": self.event_distribution,
            "alpha_accuracy": (
                {
                    "accuracy": round(self.alpha_accuracy.accuracy, 4),
                    "total": self.alpha_accuracy.total_signals,
                }
                if self.alpha_accuracy else None
            ),
            "avg_toxicity": round(self.avg_toxicity, 4),
            "avg_imbalance": round(self.avg_imbalance, 4),
            "insights": self.insights,
        }


# ---------------------------------------------------------------------------
# OrderBookMemory
# ---------------------------------------------------------------------------


class OrderBookMemory:
    """Microstructure event memory and knowledge base.

    Records order book events, tracks alpha signal accuracy,
    and builds microstructure knowledge for backtesting and
    model improvement.

    Attributes:
        records: All recorded microstructure events.
        snapshots: Historical order book snapshots.
        alpha_signals: Alpha signals awaiting verification.
        max_records: Maximum events to retain.
    """

    def __init__(self, max_records: int = 100000) -> None:
        """Initialize order book memory.

        Args:
            max_records: Maximum events in memory.
        """
        self.records: list[MicrostructureRecord] = []
        self.snapshots: list[OrderBookSnapshot] = []
        self.alpha_signals: list[dict[str, Any]] = []  # pending verification
        self.max_records = max_records

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def save(
        self,
        snapshot: OrderBookSnapshot,
    ) -> None:
        """Save an order book snapshot.

        Args:
            snapshot: OrderBookSnapshot to persist.
        """
        self.snapshots.append(snapshot)
        # Prune
        while len(self.snapshots) > self.max_records:
            self.snapshots.pop(0)

    def record(
        self,
        event_type: MicrostructureEvent,
        data: dict[str, Any],
        symbol: str = "",
        price: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MicrostructureRecord:
        """Record a microstructure event.

        Args:
            event_type: Type of event.
            data: Event data payload.
            symbol: Trading symbol.
            price: Reference price.
            metadata: Additional context.

        Returns:
            The recorded MicrostructureRecord.
        """
        record = MicrostructureRecord(
            event_type=event_type,
            data=data,
            symbol=symbol,
            price=price,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )
        self.records.append(record)

        # Prune
        while len(self.records) > self.max_records:
            self.records.pop(0)

        return record

    def record_alpha_signal(
        self,
        alpha_score: float,
        direction: str,
        strength: str,
        confidence: float,
    ) -> None:
        """Record an alpha signal for later accuracy tracking.

        Args:
            alpha_score: Alpha score value.
            direction: LONG/SHORT/FLAT.
            strength: Weak/moderate/strong/very_strong.
            confidence: Confidence value.
        """
        self.alpha_signals.append({
            "alpha_score": alpha_score,
            "direction": direction,
            "strength": strength,
            "confidence": confidence,
            "timestamp": datetime.utcnow(),
        })

        # Also record as event
        self.record(
            event_type=MicrostructureEvent.ALPHA_SIGNAL,
            data={
                "alpha_score": alpha_score,
                "direction": direction,
                "strength": strength,
            },
        )

    def verify_alpha_signal(
        self,
        signal_index: int = -1,
        was_correct: bool = True,
    ) -> None:
        """Mark a pending alpha signal as confirmed or failed.

        Args:
            signal_index: Index in alpha_signals (default: latest).
            was_correct: Whether the signal prediction was correct.
        """
        if not self.alpha_signals:
            return

        self.alpha_signals[signal_index]["verified"] = True
        self.alpha_signals[signal_index]["was_correct"] = was_correct

        event_type = (
            MicrostructureEvent.ALPHA_CONFIRMED
            if was_correct
            else MicrostructureEvent.ALPHA_FAILED
        )
        self.record(
            event_type=event_type,
            data={
                "alpha_score": self.alpha_signals[signal_index]["alpha_score"],
                "direction": self.alpha_signals[signal_index]["direction"],
            },
        )

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def recent_events(
        self,
        limit: int = 100,
        event_type: Optional[MicrostructureEvent] = None,
    ) -> list[MicrostructureRecord]:
        """Get recent events, optionally filtered.

        Args:
            limit: Max events to return.
            event_type: Filter by type.

        Returns:
            List of MicrostructureRecords.
        """
        events = self.records
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return list(reversed(events[-limit:]))

    def events_by_type(
        self,
        event_type: MicrostructureEvent,
    ) -> list[MicrostructureRecord]:
        """Get all events of a specific type."""
        return [e for e in self.records if e.event_type == event_type]

    def events_by_price(
        self,
        min_price: float,
        max_price: float,
    ) -> list[MicrostructureRecord]:
        """Get events within a price range."""
        return [
            e for e in self.records
            if min_price <= e.price <= max_price
        ]

    def recent_snapshots(
        self,
        limit: int = 100,
    ) -> list[OrderBookSnapshot]:
        """Get recent order book snapshots."""
        return self.snapshots[-limit:]

    # ------------------------------------------------------------------
    # Knowledge Base
    # ------------------------------------------------------------------

    def knowledge_base(self) -> MicrostructureKnowledgeBase:
        """Generate microstructure knowledge base.

        Returns:
            MicrostructureKnowledgeBase with analytics and insights.
        """
        total = len(self.records)

        # Event distribution
        dist: dict[str, int] = {}
        for r in self.records:
            dist[r.event_type.value] = dist.get(r.event_type.value, 0) + 1

        # Alpha accuracy
        verified = [s for s in self.alpha_signals if s.get("verified")]
        confirmed = sum(1 for s in verified if s.get("was_correct"))
        failed = len(verified) - confirmed
        accuracy = confirmed / max(len(verified), 1) if verified else 0.0

        # Avg magnitude by outcome
        correct_alpha = [s["alpha_score"] for s in verified if s.get("was_correct")]
        incorrect_alpha = [s["alpha_score"] for s in verified if not s.get("was_correct")]
        avg_mag_correct = sum(abs(a) for a in correct_alpha) / max(len(correct_alpha), 1)
        avg_mag_incorrect = sum(abs(a) for a in incorrect_alpha) / max(len(incorrect_alpha), 1)

        alpha_acc = AlphaAccuracy(
            total_signals=len(self.alpha_signals),
            confirmed_signals=confirmed,
            failed_signals=failed,
            accuracy=accuracy,
            avg_magnitude_correct=avg_mag_correct,
            avg_magnitude_incorrect=avg_mag_incorrect,
        )

        # Top wall prices
        wall_events = self.events_by_type(MicrostructureEvent.WALL_DETECTED)
        wall_prices: dict[float, int] = {}
        for e in wall_events:
            p = round(e.price, 2)
            wall_prices[p] = wall_prices.get(p, 0) + 1
        top_walls = sorted(wall_prices, key=wall_prices.get, reverse=True)[:5]

        # Avg toxicity & imbalance
        toxicity_events = self.events_by_type(MicrostructureEvent.TOXICITY_SPIKE)
        avg_tox = (
            sum(e.data.get("toxicity_score", 0) for e in toxicity_events)
            / max(len(toxicity_events), 1)
        )

        imbalance_events = self.events_by_type(MicrostructureEvent.IMBALANCE_EXTREME)
        avg_imb = (
            sum(e.data.get("imbalance_score", 0) for e in imbalance_events)
            / max(len(imbalance_events), 1)
        )

        # Insights
        insights: list[str] = []
        if accuracy > 0:
            insights.append(
                f"Alpha signal accuracy: {accuracy:.1%} ({confirmed}/{confirmed + failed})"
            )
        if dist:
            most_common = max(dist, key=dist.get)
            insights.append(f"Most common event: {most_common} ({dist[most_common]} occurrences)")
        if avg_tox > 0.5:
            insights.append(f"High average toxicity: {avg_tox:.3f} — consider defensive execution")

        return MicrostructureKnowledgeBase(
            total_events=total,
            event_distribution=dist,
            alpha_accuracy=alpha_acc,
            top_wall_prices=top_walls,
            avg_toxicity=avg_tox,
            avg_imbalance=avg_imb,
            insights=insights,
        )

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_status(self) -> dict[str, Any]:
        """Quick memory status summary."""
        kb = self.knowledge_base()
        return {
            "total_events": self.records.__len__(),
            "total_snapshots": self.snapshots.__len__(),
            "pending_alpha_signals": len([s for s in self.alpha_signals if not s.get("verified")]),
            "alpha_accuracy": (
                round(kb.alpha_accuracy.accuracy, 4)
                if kb.alpha_accuracy else 0.0
            ),
            "top_insight": kb.insights[0] if kb.insights else "No insights yet",
        }

    def clear(self) -> None:
        """Reset all memory."""
        self.records.clear()
        self.snapshots.clear()
        self.alpha_signals.clear()
