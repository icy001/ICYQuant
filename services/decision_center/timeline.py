"""Decision Timeline – records the full history of decisions for audit trail."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DecisionTimeline:
    """Records every decision event for full audit trail.

    Maintains:
      - Decision history
      - Reason history
      - Confidence history
      - Model version tracking
    """

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def append(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Append a decision event with timestamp.

        Args:
            event: decision event dict.

        Returns:
            The recorded event with timestamp.
        """
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.events.append(event)
        return event

    def record(
        self,
        signal: str,
        confidence: float,
        reason: str = "",
        model_version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a decision with standard fields."""
        event = {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "model_version": model_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.events.append(event)
        return event

    def query_by_signal(self, signal: str) -> List[Dict[str, Any]]:
        """Retrieve all events for a given signal."""
        return [e for e in self.events if e.get("signal") == signal]

    def query_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return most recent N events."""
        sorted_events = sorted(
            self.events,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        return sorted_events[:n]

    def confidence_history(self) -> List[float]:
        """Return time-series of confidence scores."""
        return [e["confidence"] for e in self.events if "confidence" in e]

    @property
    def event_count(self) -> int:
        return len(self.events)

    def clear(self) -> None:
        self.events.clear()
