from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionRecord:
    order_id: str
    symbol: str
    side: str
    quantity: int
    decision: Dict[str, Any]
    execution_result: Dict[str, Any]
    quality_grade: str
    lesson: str
    timestamp: str = ""


@dataclass
class VenuePerformance:
    venue_name: str
    total_orders: int
    avg_fill_rate: float
    avg_slippage_bps: float
    avg_cost_bps: float
    reliability_score: float  # 0-100


class ExecutionMemory:
    """Execution Memory Engine - records and learns from execution history."""

    def __init__(self):
        self.history: List[ExecutionRecord] = []
        self.venue_stats: Dict[str, VenuePerformance] = {}
        self.lessons_learned: List[str] = []

    def save(self, execution):
        """Save an execution record to memory.

        Args:
            execution: Execution data to save.
        """
        if isinstance(execution, ExecutionRecord):
            self.history.append(execution)
            self._extract_lesson(execution)
            self._update_venue_stats(execution)
        else:
            self.history.append(execution)

    def _extract_lesson(self, record: ExecutionRecord):
        """Extract learnings from an execution record."""
        if record.quality_grade in ("POOR", "UNACCEPTABLE"):
            self.lessons_learned.append(
                f"[{record.symbol}] {record.side} {record.quantity} shares: {record.lesson}"
            )

    def _update_venue_stats(self, record: ExecutionRecord):
        """Update venue performance statistics."""
        result = record.execution_result
        if isinstance(result, dict):
            routes = result.get("route", {}).get("venues", [])
            if not routes:
                routes = result.get("venues", [])
            for v in routes:
                venue_name = v.get("venue", v.get("name", "unknown"))
                if venue_name not in self.venue_stats:
                    self.venue_stats[venue_name] = VenuePerformance(
                        venue_name=venue_name,
                        total_orders=0,
                        avg_fill_rate=0.0,
                        avg_slippage_bps=0.0,
                        avg_cost_bps=0.0,
                        reliability_score=50.0,
                    )
                self.venue_stats[venue_name].total_orders += 1

    def get_history(self, symbol: Optional[str] = None) -> List[ExecutionRecord]:
        """Retrieve execution history, optionally filtered by symbol."""
        if symbol:
            return [r for r in self.history if hasattr(r, 'symbol') and r.symbol == symbol]
        return list(self.history)

    def get_lessons(self) -> List[str]:
        """Get all lessons learned from execution history."""
        return list(self.lessons_learned)

    def get_best_venue(self) -> Optional[VenuePerformance]:
        """Get the best performing venue based on reliability score."""
        if not self.venue_stats:
            return None
        return max(self.venue_stats.values(), key=lambda v: v.reliability_score)
