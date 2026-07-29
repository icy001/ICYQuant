from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionCategory(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    MISSED_OPPORTUNITY = "MISSED_OPPORTUNITY"


@dataclass
class InvestmentMemoryEntry:
    entry_id: str
    symbol: str
    thesis: str
    decision: str
    conviction_score: float
    reason: str
    outcome: str
    lesson: str
    category: DecisionCategory = DecisionCategory.BREAKEVEN
    return_pct: float = 0.0
    timestamp: str = ""


@dataclass
class DecisionPattern:
    pattern_name: str
    thesis_type: str
    decision_type: str
    success_count: int
    failure_count: int
    avg_return: float
    win_rate: float
    description: str


class InvestmentDecisionMemory:
    """Investment Decision Memory Engine - institutional memory for investment decisions."""

    def __init__(self):
        self.history: list = []
        self.patterns: Dict[str, DecisionPattern] = {}
        self.lessons: List[str] = []
        self.institutional_knowledge: Dict[str, Any] = {}

    def save(self, decision):
        """Save an investment decision to memory.

        Args:
            decision: The decision data to save.
        """
        if isinstance(decision, InvestmentMemoryEntry):
            self.history.append(decision)
            self._extract_lesson(decision)
            self._update_patterns(decision)
            self._update_knowledge(decision)
        else:
            self.history.append(decision)

    def _extract_lesson(self, entry: InvestmentMemoryEntry):
        """Extract a lesson from an investment memory entry."""
        lesson = f"[{entry.symbol}] {entry.decision} (conviction: {entry.conviction_score:.0f}) → "
        lesson += f"{entry.outcome} (return: {entry.return_pct:.1%}). "
        lesson += f"Lesson: {entry.lesson}"
        self.lessons.append(lesson)

    def _update_patterns(self, entry: InvestmentMemoryEntry):
        """Update decision patterns from memory."""
        pattern_key = f"{entry.decision}_{entry.category.value}"
        if pattern_key not in self.patterns:
            self.patterns[pattern_key] = DecisionPattern(
                pattern_name=pattern_key,
                thesis_type=entry.thesis or "GENERAL",
                decision_type=entry.decision,
                success_count=0,
                failure_count=0,
                avg_return=0.0,
                win_rate=0.0,
                description=f"Pattern: {entry.decision} → {entry.category.value}",
            )

        pattern = self.patterns[pattern_key]
        if entry.category == DecisionCategory.WIN:
            pattern.success_count += 1
        elif entry.category == DecisionCategory.LOSS:
            pattern.failure_count += 1

        total = pattern.success_count + pattern.failure_count
        if total > 0:
            pattern.win_rate = pattern.success_count / total
            # Update moving average return
            old_avg = pattern.avg_return
            n = total
            pattern.avg_return = old_avg + (entry.return_pct - old_avg) / n

    def _update_knowledge(self, entry: InvestmentMemoryEntry):
        """Update institutional knowledge base."""
        symbol = entry.symbol
        if symbol not in self.institutional_knowledge:
            self.institutional_knowledge[symbol] = {
                "decisions_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "avg_return": 0.0,
                "best_decision": None,
                "worst_decision": None,
                "lessons": [],
            }

        knowledge = self.institutional_knowledge[symbol]
        knowledge["decisions_count"] += 1
        if entry.category == DecisionCategory.WIN:
            knowledge["win_count"] += 1
        elif entry.category == DecisionCategory.LOSS:
            knowledge["loss_count"] += 1

        n = knowledge["decisions_count"]
        old_avg = knowledge["avg_return"]
        knowledge["avg_return"] = old_avg + (entry.return_pct - old_avg) / n

        if entry.lesson:
            knowledge["lessons"].append(entry.lesson)

    def get_history(self, symbol: Optional[str] = None) -> list:
        """Retrieve investment memory history, optionally filtered by symbol."""
        if symbol:
            return [e for e in self.history if hasattr(e, 'symbol') and e.symbol == symbol]
        return list(self.history)

    def get_lessons(self) -> List[str]:
        """Get all lessons learned from investment memory."""
        return list(self.lessons)

    def get_lessons_by_symbol(self, symbol: str) -> List[str]:
        """Get lessons for a specific symbol."""
        knowledge = self.institutional_knowledge.get(symbol, {})
        return knowledge.get("lessons", [])

    def get_pattern(self, pattern_name: str) -> Optional[DecisionPattern]:
        """Get a specific decision pattern."""
        return self.patterns.get(pattern_name)

    def get_best_patterns(self, min_samples: int = 3) -> List[DecisionPattern]:
        """Get the most reliable decision patterns."""
        return sorted(
            [p for p in self.patterns.values()
             if (p.success_count + p.failure_count) >= min_samples],
            key=lambda p: p.win_rate,
            reverse=True,
        )

    def get_worst_patterns(self, min_samples: int = 3) -> List[DecisionPattern]:
        """Get the least reliable decision patterns to avoid."""
        return sorted(
            [p for p in self.patterns.values()
             if (p.success_count + p.failure_count) >= min_samples],
            key=lambda p: p.win_rate,
        )

    def get_institutional_knowledge(self, symbol: Optional[str] = None) -> dict:
        """Get institutional knowledge, optionally for a specific symbol."""
        if symbol:
            return self.institutional_knowledge.get(symbol, {})
        return dict(self.institutional_knowledge)

    def get_total_decisions(self) -> int:
        """Get total number of decisions in memory."""
        return len(self.history)

    def get_win_rate(self) -> float:
        """Get overall win rate."""
        if not self.history:
            return 0.0
        wins = sum(1 for e in self.history
                   if hasattr(e, 'category') and e.category == DecisionCategory.WIN)
        losses = sum(1 for e in self.history
                     if hasattr(e, 'category') and e.category == DecisionCategory.LOSS)
        total = wins + losses
        return wins / total if total > 0 else 0.0
