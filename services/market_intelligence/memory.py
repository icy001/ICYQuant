from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MarketMemoryEntry:
    event_type: str
    symbol: str
    description: str
    regime: str
    sentiment: str
    forecast_result: str
    actual_result: str
    lesson: str
    timestamp: str = ""


@dataclass
class PatternMemory:
    pattern_name: str
    occurrence_count: int
    accuracy: float
    description: str
    typical_duration: str
    success_conditions: List[str] = field(default_factory=list)


class MarketMemory:
    """Market Memory Engine - stores and learns from market events and patterns."""

    def __init__(self):
        self.history: list = []
        self.patterns: Dict[str, PatternMemory] = {}
        self.lessons: List[str] = []

    def save(self, event):
        """Save a market event to memory.

        Args:
            event: Event data to save.
        """
        if isinstance(event, MarketMemoryEntry):
            self.history.append(event)
            self._extract_lesson(event)
            self._update_patterns(event)
        else:
            self.history.append(event)

    def _extract_lesson(self, entry: MarketMemoryEntry):
        """Extract a lesson from a market memory entry."""
        if entry.forecast_result != entry.actual_result:
            self.lessons.append(
                f"[{entry.symbol}] {entry.event_type}: "
                f"Predicted {entry.forecast_result}, actual {entry.actual_result}. "
                f"Lesson: {entry.lesson}"
            )

    def _update_patterns(self, entry: MarketMemoryEntry):
        """Update pattern recognition from market memory."""
        pattern_key = f"{entry.regime}_{entry.event_type}"
        if pattern_key not in self.patterns:
            self.patterns[pattern_key] = PatternMemory(
                pattern_name=pattern_key,
                occurrence_count=0,
                accuracy=0.0,
                description=f"Pattern: {entry.regime} regime with {entry.event_type} event",
                typical_duration="1W",
            )
        self.patterns[pattern_key].occurrence_count += 1
        if entry.forecast_result == entry.actual_result:
            correct = self.patterns[pattern_key].accuracy * (self.patterns[pattern_key].occurrence_count - 1) + 1
            self.patterns[pattern_key].accuracy = correct / self.patterns[pattern_key].occurrence_count

    def get_history(self, symbol: Optional[str] = None) -> list:
        """Retrieve market memory history, optionally filtered by symbol."""
        if symbol:
            return [e for e in self.history if hasattr(e, 'symbol') and e.symbol == symbol]
        return list(self.history)

    def get_lessons(self) -> List[str]:
        """Get all lessons learned from market memory."""
        return list(self.lessons)

    def get_pattern(self, pattern_name: str) -> Optional[PatternMemory]:
        """Get a specific market pattern from memory."""
        return self.patterns.get(pattern_name)

    def get_best_patterns(self, min_occurrences: int = 3) -> List[PatternMemory]:
        """Get the most reliable market patterns."""
        return sorted(
            [p for p in self.patterns.values() if p.occurrence_count >= min_occurrences],
            key=lambda p: p.accuracy,
            reverse=True,
        )
