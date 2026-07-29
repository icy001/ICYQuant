"""Performance Memory Engine - institutional performance memory and learning."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PerformanceEvent(str, Enum):
    TRADE = "TRADE"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    WEEKLY_REVIEW = "WEEKLY_REVIEW"
    MONTHLY_REVIEW = "MONTHLY_REVIEW"
    DRAWDOWN = "DRAWDOWN"
    RECOVERY = "RECOVERY"
    STRATEGY_CHANGE = "STRATEGY_CHANGE"
    MILESTONE = "MILESTONE"


class PerformanceOutcome(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


@dataclass
class PerformanceMemoryEntry:
    entry_id: str
    event: PerformanceEvent
    outcome: PerformanceOutcome
    strategy: str
    metrics: Dict[str, float]
    result: str
    lesson: str
    timestamp: str = ""


@dataclass
class PerformancePattern:
    pattern_name: str
    event_type: str
    occurrence_count: int
    positive_count: int
    negative_count: int
    avg_return: float
    success_rate: float
    description: str
    related_lessons: List[str] = field(default_factory=list)


@dataclass
class KnowledgeSummary:
    total_events: int
    total_strategies: int
    best_strategy: str
    best_return: float
    overall_success_rate: float
    top_lessons: List[str]
    recent_trend: str


class PerformanceMemory:
    """Performance Memory Engine.

    Saves: Trade, Result, Reason, Lesson.
    Forms: Institutional Performance Memory with pattern recognition and knowledge extraction.
    """

    def __init__(self):
        self.history: list = []
        self.patterns: Dict[str, PerformancePattern] = {}
        self.lessons: List[str] = []
        self.knowledge: Dict[str, Dict[str, Any]] = {}
        self.milestones: List[Dict[str, Any]] = []

    def save(self, event):
        """Save a performance event to memory.

        Args:
            event: Performance event data to save.
        """
        if isinstance(event, PerformanceMemoryEntry):
            self.history.append(event)
            self._extract_lesson(event)
            self._update_patterns(event)
            self._update_knowledge(event)
        else:
            self.history.append(event)

    def _extract_lesson(self, entry: PerformanceMemoryEntry):
        """Extract a lesson from a performance memory entry."""
        lesson = (
            f"[{entry.strategy}] {entry.event.value}: {entry.outcome.value} - "
            f"{entry.result}. Lesson: {entry.lesson}"
        )
        self.lessons.append(lesson)

    def _update_patterns(self, entry: PerformanceMemoryEntry):
        """Update performance patterns from memory."""
        key = f"{entry.strategy}_{entry.event.value}"
        if key not in self.patterns:
            self.patterns[key] = PerformancePattern(
                pattern_name=key,
                event_type=entry.event.value,
                occurrence_count=0,
                positive_count=0,
                negative_count=0,
                avg_return=0.0,
                success_rate=0.0,
                description=f"Pattern: {entry.strategy} - {entry.event.value}",
            )

        p = self.patterns[key]
        p.occurrence_count += 1

        if entry.outcome == PerformanceOutcome.POSITIVE:
            p.positive_count += 1
        elif entry.outcome == PerformanceOutcome.NEGATIVE:
            p.negative_count += 1

        total = p.positive_count + p.negative_count
        if total > 0:
            p.success_rate = p.positive_count / total

        ret = entry.metrics.get("return", 0.0)
        n = p.occurrence_count
        p.avg_return = p.avg_return + (ret - p.avg_return) / n

        if entry.lesson:
            p.related_lessons.append(entry.lesson)

    def _update_knowledge(self, entry: PerformanceMemoryEntry):
        """Update performance knowledge base."""
        strategy = entry.strategy
        if strategy not in self.knowledge:
            self.knowledge[strategy] = {
                "total_events": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "avg_return": 0.0,
                "max_return": float("-inf"),
                "min_return": float("inf"),
                "lessons": [],
                "last_updated": "",
            }

        k = self.knowledge[strategy]
        k["total_events"] += 1
        k["last_updated"] = entry.timestamp

        if entry.outcome == PerformanceOutcome.POSITIVE:
            k["positive"] += 1
        elif entry.outcome == PerformanceOutcome.NEGATIVE:
            k["negative"] += 1
        else:
            k["neutral"] += 1

        ret = entry.metrics.get("return", 0.0)
        n = k["total_events"]
        k["avg_return"] = k["avg_return"] + (ret - k["avg_return"]) / n
        k["max_return"] = max(k["max_return"], ret)
        k["min_return"] = min(k["min_return"], ret)

        if entry.lesson:
            k["lessons"].append(entry.lesson)

    def get_history(self, strategy: Optional[str] = None) -> list:
        """Get performance memory history, optionally filtered by strategy."""
        if strategy:
            return [e for e in self.history
                    if hasattr(e, 'strategy') and e.strategy == strategy]
        return list(self.history)

    def get_lessons(self) -> List[str]:
        """Get all lessons learned from performance memory."""
        return list(self.lessons)

    def get_pattern(self, name: str) -> Optional[PerformancePattern]:
        """Get a specific performance pattern."""
        return self.patterns.get(name)

    def get_best_patterns(self, min_samples: int = 5) -> List[PerformancePattern]:
        """Get most successful performance patterns."""
        return sorted(
            [p for p in self.patterns.values()
             if p.occurrence_count >= min_samples],
            key=lambda p: p.success_rate,
            reverse=True,
        )

    def get_knowledge(self, strategy: Optional[str] = None) -> dict:
        """Get performance knowledge, optionally for a specific strategy."""
        if strategy:
            return self.knowledge.get(strategy, {})
        return dict(self.knowledge)

    def get_summary(self) -> KnowledgeSummary:
        """Get a summary of all performance knowledge."""
        total_events = len(self.history)
        strategies = list(self.knowledge.keys())

        best_strategy = ""
        best_return = float("-inf")
        for name, k in self.knowledge.items():
            if k["avg_return"] > best_return:
                best_return = k["avg_return"]
                best_strategy = name

        total_positive = sum(k.get("positive", 0) for k in self.knowledge.values())
        total_outcomes = sum(k.get("total_events", 0) for k in self.knowledge.values())
        success_rate = total_positive / total_outcomes if total_outcomes > 0 else 0.0

        top_lessons = self.lessons[-5:] if self.lessons else []

        recent_returns = [
            e.metrics.get("return", 0.0) for e in self.history[-10:]
            if hasattr(e, 'metrics')
        ]
        if recent_returns:
            avg_recent = sum(recent_returns) / len(recent_returns)
            trend = "IMPROVING" if avg_recent > 0 else "DECLINING"
        else:
            trend = "INSUFFICIENT_DATA"

        return KnowledgeSummary(
            total_events=total_events,
            total_strategies=len(strategies),
            best_strategy=best_strategy,
            best_return=best_return,
            overall_success_rate=success_rate,
            top_lessons=top_lessons,
            recent_trend=trend,
        )

    def add_milestone(self, milestone: Dict[str, Any]):
        """Record a performance milestone."""
        self.milestones.append(milestone)

    def get_milestones(self) -> List[Dict[str, Any]]:
        """Get all recorded milestones."""
        return list(self.milestones)
