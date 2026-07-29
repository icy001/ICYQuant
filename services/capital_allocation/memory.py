from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapitalEvent(str, Enum):
    DEPLOYMENT = "DEPLOYMENT"
    ROTATION = "ROTATION"
    DEALLOCATION = "DEALLOCATION"
    REBALANCE = "REBALANCE"
    LIQUIDATION = "LIQUIDATION"


class CapitalOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    NEUTRAL = "NEUTRAL"
    FAILURE = "FAILURE"


@dataclass
class CapitalMemoryEntry:
    entry_id: str
    symbol: str
    event: CapitalEvent
    amount: float
    allocation_before: float
    allocation_after: float
    outcome: CapitalOutcome
    result: str
    lesson: str
    return_impact: float = 0.0


@dataclass
class CapitalPattern:
    pattern_name: str
    event_type: str
    success_count: int
    failure_count: int
    avg_return_impact: float
    success_rate: float
    description: str


class CapitalMemory:
    """Capital Memory Engine - institutional memory for capital allocation decisions."""

    def __init__(self):
        self.history: list = []
        self.patterns: Dict[str, CapitalPattern] = {}
        self.lessons: List[str] = []
        self.knowledge: Dict[str, Dict[str, Any]] = {}

    def save(self, decision):
        """Save a capital allocation decision to memory.

        Args:
            decision: The decision data to save.
        """
        if isinstance(decision, CapitalMemoryEntry):
            self.history.append(decision)
            self._extract_lesson(decision)
            self._update_patterns(decision)
            self._update_knowledge(decision)
        else:
            self.history.append(decision)

    def _extract_lesson(self, entry: CapitalMemoryEntry):
        """Extract a lesson from a capital memory entry."""
        lesson = (
            f"[{entry.symbol}] {entry.event.value}: {entry.amount:.0f} "
            f"({entry.allocation_before:.1%} → {entry.allocation_after:.1%}) "
            f"→ {entry.outcome.value}. Lesson: {entry.lesson}"
        )
        self.lessons.append(lesson)

    def _update_patterns(self, entry: CapitalMemoryEntry):
        """Update capital patterns from memory."""
        key = f"{entry.event.value}_{entry.outcome.value}"
        if key not in self.patterns:
            self.patterns[key] = CapitalPattern(
                pattern_name=key,
                event_type=entry.event.value,
                success_count=0,
                failure_count=0,
                avg_return_impact=0.0,
                success_rate=0.0,
                description=f"Pattern: {entry.event.value} → {entry.outcome.value}",
            )

        p = self.patterns[key]
        if entry.outcome == CapitalOutcome.SUCCESS:
            p.success_count += 1
        elif entry.outcome == CapitalOutcome.FAILURE:
            p.failure_count += 1

        total = p.success_count + p.failure_count
        if total > 0:
            p.success_rate = p.success_count / total
            old_avg = p.avg_return_impact
            p.avg_return_impact = old_avg + (entry.return_impact - old_avg) / total

    def _update_knowledge(self, entry: CapitalMemoryEntry):
        """Update capital knowledge base."""
        symbol = entry.symbol
        if symbol not in self.knowledge:
            self.knowledge[symbol] = {
                "total_events": 0,
                "total_deployed": 0.0,
                "success_count": 0,
                "failure_count": 0,
                "avg_return_impact": 0.0,
                "lessons": [],
            }

        k = self.knowledge[symbol]
        k["total_events"] += 1
        k["total_deployed"] += entry.amount
        if entry.outcome == CapitalOutcome.SUCCESS:
            k["success_count"] += 1
        elif entry.outcome == CapitalOutcome.FAILURE:
            k["failure_count"] += 1

        n = k["total_events"]
        old_avg = k["avg_return_impact"]
        k["avg_return_impact"] = old_avg + (entry.return_impact - old_avg) / n

        if entry.lesson:
            k["lessons"].append(entry.lesson)

    def get_history(self, symbol: Optional[str] = None) -> list:
        """Get capital memory history, optionally filtered by symbol."""
        if symbol:
            return [e for e in self.history
                    if hasattr(e, 'symbol') and e.symbol == symbol]
        return list(self.history)

    def get_lessons(self) -> List[str]:
        """Get all lessons learned from capital memory."""
        return list(self.lessons)

    def get_pattern(self, name: str) -> Optional[CapitalPattern]:
        """Get a specific capital pattern."""
        return self.patterns.get(name)

    def get_best_patterns(self, min_samples: int = 3) -> List[CapitalPattern]:
        """Get most successful capital allocation patterns."""
        return sorted(
            [p for p in self.patterns.values()
             if (p.success_count + p.failure_count) >= min_samples],
            key=lambda p: p.success_rate,
            reverse=True,
        )

    def get_knowledge(self, symbol: Optional[str] = None) -> dict:
        """Get capital knowledge, optionally for a specific symbol."""
        if symbol:
            return self.knowledge.get(symbol, {})
        return dict(self.knowledge)

    def get_total_capital_deployed(self) -> float:
        """Get total capital deployed across all history."""
        return sum(
            e.amount for e in self.history
            if hasattr(e, 'amount')
        )

    def get_success_rate(self) -> float:
        """Get overall capital allocation success rate."""
        if not self.history:
            return 0.0
        successes = sum(1 for e in self.history
                        if hasattr(e, 'outcome') and e.outcome == CapitalOutcome.SUCCESS)
        failures = sum(1 for e in self.history
                       if hasattr(e, 'outcome') and e.outcome == CapitalOutcome.FAILURE)
        total = successes + failures
        return successes / total if total > 0 else 0.0
