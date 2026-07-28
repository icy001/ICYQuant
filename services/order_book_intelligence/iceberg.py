"""Iceberg Order Detector — detect hidden iceberg/display-size orders.

Identifies iceberg orders by monitoring repeated fills at the same
price level with constant display size replenishment patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IcebergStatus(str, Enum):
    """Iceberg detection status."""

    NONE = "none"  # No iceberg detected
    SUSPECTED = "suspected"  # Pattern forming, watch closely
    CONFIRMED = "confirmed"  # Iceberg order confirmed
    DISSOLVED = "dissolved"  # Previously confirmed iceberg gone


class IcebergSide(str, Enum):
    """Iceberg order side."""

    BID = "bid"
    ASK = "ask"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class IcebergEvent:
    """Single event in an iceberg pattern.

    Attributes:
        price: Price level.
        fill_volume: Volume filled in this event.
        display_size: Visible display size after replenishment.
        timestamp: Event time.
        event_index: Sequence number in the pattern.
    """

    price: float
    fill_volume: float
    display_size: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_index: int = 0


@dataclass
class IcebergDetection:
    """Detected iceberg order.

    Attributes:
        price: Iceberg price level.
        side: BID or ASK.
        total_estimated_volume: Estimated total iceberg volume.
        visible_display_size: Consistent display size.
        fill_count: Number of fill events observed.
        avg_fill_size: Average fill per event.
        replenishment_interval_sec: Average time between replenishments.
        status: Detection status.
        confidence: Detection confidence (0–1).
        events: Recorded iceberg fill events.
        timestamp: Detection time.
    """

    price: float
    side: IcebergSide
    total_estimated_volume: float = 0.0
    visible_display_size: float = 0.0
    fill_count: int = 0
    avg_fill_size: float = 0.0
    replenishment_interval_sec: float = 0.0
    status: IcebergStatus = IcebergStatus.SUSPECTED
    confidence: float = 0.0
    events: list[IcebergEvent] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        """Whether iceberg is still active."""
        return self.status in (IcebergStatus.SUSPECTED, IcebergStatus.CONFIRMED)

    @property
    def hidden_ratio(self) -> float:
        """Estimated hidden volume ratio (hidden / total)."""
        if self.total_estimated_volume == 0:
            return 0.0
        visible = self.visible_display_size * self.fill_count
        return 1.0 - (visible / self.total_estimated_volume)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "price": self.price,
            "side": self.side.value,
            "estimated_total_volume": round(self.total_estimated_volume, 2),
            "display_size": round(self.visible_display_size, 2),
            "fill_count": self.fill_count,
            "status": self.status.value,
            "confidence": round(self.confidence, 4),
            "hidden_ratio": round(self.hidden_ratio, 4),
        }


# ---------------------------------------------------------------------------
# IcebergDetector
# ---------------------------------------------------------------------------


class IcebergDetector:
    """Iceberg order detection engine.

    Monitors order book fill events for patterns indicative of iceberg
    orders: repeated small fills at the same price level with constant
    display size after each fill, suggesting the presence of a large
    hidden order being replenished.

    Attributes:
        min_repetitions: Minimum repeated fills to suspect iceberg.
        size_tolerance: Max deviation in display size for consistency.
        price_tolerance_pct: Max price deviation for same-level grouping.
        active_trackers: Currently tracked iceberg candidates.
        confirmed: Confirmed iceberg orders.
        dissolved: Previously active icebergs that have dissolved.
    """

    MIN_FILLS = 3
    SIZE_TOLERANCE = 0.10  # 10% variation in display size
    PRICE_TOLERANCE = 0.001  # 0.1% price grouping tolerance

    def __init__(
        self,
        min_repetitions: int = 3,
        size_tolerance: float = 0.10,
    ) -> None:
        """Initialize the iceberg detector.

        Args:
            min_repetitions: Minimum fills to confirm iceberg.
            size_tolerance: Max display size variation (fraction).
        """
        self.min_repetitions = min_repetitions
        self.size_tolerance = size_tolerance
        self.active_trackers: dict[tuple[float, str], list[IcebergEvent]] = {}
        self.confirmed: list[IcebergDetection] = []
        self.dissolved: list[IcebergDetection] = []
        self.history: list[IcebergDetection] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def detect(
        self,
        events: list[dict[str, Any]],
    ) -> list[IcebergDetection]:
        """Detect iceberg orders from order book fill events.

        Args:
            events: List of fill event dicts with keys: price, volume,
                    side, display_size (volume remaining at level after fill),
                    timestamp.

        Returns:
            List of detected iceberg orders (active and confirmed).
        """
        for event_dict in events:
            self._process_event(event_dict)

        # Generate detections from active trackers
        detections = []
        for (price, side_str), event_list in self.active_trackers.items():
            if len(event_list) >= self.min_repetitions:
                detection = self._build_detection(price, side_str, event_list)
                detections.append(detection)

        self.history = detections
        return detections

    # ------------------------------------------------------------------
    # Event Processing
    # ------------------------------------------------------------------

    def _process_event(self, event_dict: dict[str, Any]) -> None:
        """Process a single fill event."""
        price = event_dict.get("price", 0.0)
        volume = event_dict.get("volume", 0.0)
        side = event_dict.get("side", "")
        display_size = event_dict.get("display_size", 0.0)
        ts = event_dict.get("timestamp", datetime.utcnow())

        if not isinstance(ts, datetime):
            ts = datetime.utcnow()

        # Find matching tracker by price proximity
        key = self._find_matching_key(price, side)
        if key is None:
            # New potential iceberg
            key = (price, side)
            self.active_trackers[key] = []

        event = IcebergEvent(
            price=price,
            fill_volume=volume,
            display_size=display_size,
            timestamp=ts,
            event_index=len(self.active_trackers[key]),
        )

        # Check display size consistency
        existing_events = self.active_trackers[key]
        if existing_events:
            avg_display = sum(e.display_size for e in existing_events) / len(existing_events)
            if avg_display > 0:
                deviation = abs(display_size - avg_display) / avg_display
                if deviation > self.size_tolerance:
                    # Display size changed significantly — reset tracker
                    self.active_trackers[key] = [event]
                    return

        self.active_trackers[key].append(event)

    def _find_matching_key(
        self,
        price: float,
        side: str,
    ) -> Optional[tuple[float, str]]:
        """Find existing tracker key within price tolerance."""
        for existing_price, existing_side in self.active_trackers:
            if existing_side != side:
                continue
            if existing_price == 0:
                continue
            deviation = abs(price - existing_price) / existing_price
            if deviation <= self.PRICE_TOLERANCE:
                return (existing_price, existing_side)
        return None

    # ------------------------------------------------------------------
    # Detection Building
    # ------------------------------------------------------------------

    def _build_detection(
        self,
        price: float,
        side: str,
        event_list: list[IcebergEvent],
    ) -> IcebergDetection:
        """Build IcebergDetection from accumulated events."""
        fill_count = len(event_list)
        total_fill = sum(e.fill_volume for e in event_list)
        avg_fill = total_fill / fill_count if fill_count > 0 else 0.0
        display_sizes = [e.display_size for e in event_list]
        avg_display = sum(display_sizes) / len(display_sizes) if display_sizes else 0.0

        # Estimate total: current displayed × (1 + hidden_multiplier)
        hidden_multiplier = fill_count  # rough: each fill replenished once
        estimated_total = avg_display * (1 + hidden_multiplier)

        # Confidence based on pattern clarity
        size_consistency = 1.0
        if avg_display > 0:
            max_dev = max(
                abs(d - avg_display) / avg_display for d in display_sizes
            )
            size_consistency = max(0.0, 1.0 - max_dev / self.size_tolerance)

        fill_consistency = min(1.0, fill_count / self.min_repetitions)
        confidence = 0.5 * size_consistency + 0.5 * fill_consistency

        # Status
        if fill_count >= self.min_repetitions and confidence > 0.7:
            status = IcebergStatus.CONFIRMED
        elif fill_count >= 2:
            status = IcebergStatus.SUSPECTED
        else:
            status = IcebergStatus.NONE

        # Replenishment interval
        interval = 0.0
        if len(event_list) >= 2:
            intervals = [
                (event_list[i].timestamp - event_list[i-1].timestamp).total_seconds()
                for i in range(1, len(event_list))
            ]
            interval = sum(intervals) / len(intervals)

        detection = IcebergDetection(
            price=price,
            side=IcebergSide(side),
            total_estimated_volume=estimated_total,
            visible_display_size=avg_display,
            fill_count=fill_count,
            avg_fill_size=avg_fill,
            replenishment_interval_sec=interval,
            status=status,
            confidence=confidence,
            events=event_list,
        )

        return detection

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def age_out(self, max_age_seconds: float = 300.0) -> int:
        """Remove stale trackers that haven't seen activity.

        Args:
            max_age_seconds: Maximum seconds since last event.

        Returns:
            Number of trackers removed.
        """
        now = datetime.utcnow()
        stale_keys = []
        for key, events in self.active_trackers.items():
            if events:
                last_event = events[-1]
                age = (now - last_event.timestamp).total_seconds()
                if age > max_age_seconds:
                    stale_keys.append(key)

        # Move to dissolved if confirmed
        for key in stale_keys:
            events = self.active_trackers[key]
            if len(events) >= self.min_repetitions:
                detection = self._build_detection(key[0], key[1], events)
                detection.status = IcebergStatus.DISSOLVED
                self.dissolved.append(detection)
            del self.active_trackers[key]

        return len(stale_keys)

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_detect(
        self,
        price: float,
        volume: float,
        side: str,
        display_size: float,
    ) -> dict[str, Any]:
        """Quick iceberg detection from single fill event.

        Args:
            price: Fill price.
            volume: Fill volume.
            side: "bid" or "ask".
            display_size: Remaining visible volume after fill.

        Returns:
            Dict with detection status and confidence.
        """
        events = [{
            "price": price,
            "volume": volume,
            "side": side,
            "display_size": display_size,
        }]
        detections = self.detect(events)
        if detections:
            d = detections[0]
            return {
                "status": d.status.value,
                "confidence": round(d.confidence, 4),
                "estimated_total": round(d.total_estimated_volume, 2),
                "price": d.price,
                "side": d.side.value,
            }
        return {"status": "none", "confidence": 0.0}

    def active_count(self) -> int:
        """Number of active iceberg trackers."""
        return len(self.active_trackers)

    def clear(self) -> None:
        """Reset all trackers and history."""
        self.active_trackers.clear()
        self.confirmed.clear()
        self.dissolved.clear()
        self.history.clear()
