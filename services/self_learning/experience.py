"""Experience Collector - collects and structures trading experience data."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class ExperienceType(Enum):
    """Type of experience collected."""
    TRADE = "TRADE"
    DECISION = "DECISION"
    MARKET = "MARKET"
    STRATEGY = "STRATEGY"
    OUTCOME = "OUTCOME"


class ExperienceOutcome(Enum):
    """Outcome classification for experience."""
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class ExperienceCategory(Enum):
    """Category of trading experience."""
    WINNING_TRADE = "WINNING_TRADE"
    LOSING_TRADE = "LOSING_TRADE"
    MISSED_OPPORTUNITY = "MISSED_OPPORTUNITY"
    CORRECT_DECISION = "CORRECT_DECISION"
    INCORRECT_DECISION = "INCORRECT_DECISION"
    MARKET_SURPRISE = "MARKET_SURPRISE"
    REGIME_CHANGE = "REGIME_CHANGE"
    STRATEGY_BREAKDOWN = "STRATEGY_BREAKDOWN"


@dataclass
class ExperienceRecord:
    """A single trading experience record."""
    record_id: str
    timestamp: float
    experience_type: ExperienceType
    category: ExperienceCategory
    context: Dict[str, Any]
    action: Dict[str, Any]
    outcome: ExperienceOutcome
    pnl: float
    strategy: str
    tags: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def is_significant(self) -> bool:
        """Check if this experience is significant enough to learn from."""
        return (self.outcome != ExperienceOutcome.NEUTRAL
                and abs(self.pnl) > 0.001
                and self.confidence > 0.5)


@dataclass
class ExperienceBatch:
    """A batch of experiences collected over a period."""
    batch_id: str
    period_start: float
    period_end: float
    records: List[ExperienceRecord] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_pnl(self) -> float:
        return sum(r.pnl for r in self.records)

    @property
    def win_rate(self) -> float:
        if not self.records:
            return 0.0
        positive = sum(1 for r in self.records if r.outcome == ExperienceOutcome.POSITIVE)
        return positive / len(self.records)

    @property
    def significant_count(self) -> int:
        return sum(1 for r in self.records if r.is_significant())


class ExperienceCollector:
    """Experience Collector.

    Collects and structures trading experience including:
    - Trade events
    - Decision events
    - Market context
    - Strategy states
    - Outcome results

    Forms the foundation of the self-learning loop.
    """

    def __init__(self):
        self.records: List[ExperienceRecord] = []
        self.batches: List[ExperienceBatch] = []
        self._record_counter = 0

    def collect(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """Collect a single experience.

        Args:
            experience: Raw experience data dict.

        Returns:
            Dict with collected experience info.
        """
        record = ExperienceRecord(
            record_id=f"EXP_{self._record_counter:06d}",
            timestamp=experience.get("timestamp", time.time()),
            experience_type=ExperienceType(experience.get("type", "TRADE")),
            category=ExperienceCategory(experience.get("category", "WINNING_TRADE")),
            context=experience.get("context", {}),
            action=experience.get("action", {}),
            outcome=ExperienceOutcome(experience.get("outcome", "NEUTRAL")),
            pnl=experience.get("pnl", 0.0),
            strategy=experience.get("strategy", "unknown"),
            tags=experience.get("tags", []),
            lessons=experience.get("lessons", []),
            confidence=experience.get("confidence", 1.0),
        )
        self.records.append(record)
        self._record_counter += 1

        return {
            "record_id": record.record_id,
            "type": record.experience_type.value,
            "category": record.category.value,
            "outcome": record.outcome.value,
            "significant": record.is_significant(),
        }

    def collect_batch(self, experiences: List[Dict[str, Any]],
                      period_start: float = None,
                      period_end: float = None) -> Dict[str, Any]:
        """Collect a batch of experiences.

        Args:
            experiences: List of raw experience data dicts.
            period_start: Start timestamp.
            period_end: End timestamp.

        Returns:
            Dict with batch collection info.
        """
        if period_start is None:
            period_start = time.time() - 86400
        if period_end is None:
            period_end = time.time()

        batch = ExperienceBatch(
            batch_id=f"BATCH_{len(self.batches):04d}",
            period_start=period_start,
            period_end=period_end,
        )

        for exp in experiences:
            record = ExperienceRecord(
                record_id=f"EXP_{self._record_counter:06d}",
                timestamp=exp.get("timestamp", time.time()),
                experience_type=ExperienceType(exp.get("type", "TRADE")),
                category=ExperienceCategory(exp.get("category", "WINNING_TRADE")),
                context=exp.get("context", {}),
                action=exp.get("action", {}),
                outcome=ExperienceOutcome(exp.get("outcome", "NEUTRAL")),
                pnl=exp.get("pnl", 0.0),
                strategy=exp.get("strategy", "unknown"),
                tags=exp.get("tags", []),
                lessons=exp.get("lessons", []),
                confidence=exp.get("confidence", 1.0),
            )
            self.records.append(record)
            batch.records.append(record)
            self._record_counter += 1

        batch.summary = {
            "count": len(batch.records),
            "total_pnl": batch.total_pnl,
            "win_rate": batch.win_rate,
            "significant_count": batch.significant_count,
        }
        self.batches.append(batch)

        return {
            "batch_id": batch.batch_id,
            "count": len(batch.records),
            "total_pnl": batch.total_pnl,
            "win_rate": batch.win_rate,
            "significant_experiences": batch.significant_count,
        }

    def query(self, filters: Dict[str, Any] = None) -> List[ExperienceRecord]:
        """Query collected experiences with filters.

        Args:
            filters: Optional dict of filter criteria.

        Returns:
            Filtered list of experience records.
        """
        results = self.records
        if filters is None:
            return results

        if "type" in filters:
            results = [r for r in results
                       if r.experience_type.value == filters["type"]]
        if "outcome" in filters:
            results = [r for r in results
                       if r.outcome.value == filters["outcome"]]
        if "strategy" in filters:
            results = [r for r in results
                       if r.strategy == filters["strategy"]]
        if "category" in filters:
            results = [r for r in results
                       if r.category.value == filters["category"]]
        if "significant_only" in filters and filters["significant_only"]:
            results = [r for r in results if r.is_significant()]
        if "min_pnl" in filters:
            results = [r for r in results if r.pnl >= filters["min_pnl"]]
        if "max_pnl" in filters:
            results = [r for r in results if r.pnl <= filters["max_pnl"]]
        if "tags" in filters:
            tag_set = set(filters["tags"])
            results = [r for r in results if tag_set.intersection(set(r.tags))]

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics over all collected experiences.

        Returns:
            Dict with experience statistics.
        """
        if not self.records:
            return {"total": 0}

        positive = sum(1 for r in self.records
                       if r.outcome == ExperienceOutcome.POSITIVE)
        negative = sum(1 for r in self.records
                       if r.outcome == ExperienceOutcome.NEGATIVE)
        neutral = sum(1 for r in self.records
                       if r.outcome == ExperienceOutcome.NEUTRAL)

        strategies = {}
        for r in self.records:
            if r.strategy not in strategies:
                strategies[r.strategy] = {"count": 0, "total_pnl": 0.0, "wins": 0}
            strategies[r.strategy]["count"] += 1
            strategies[r.strategy]["total_pnl"] += r.pnl
            if r.outcome == ExperienceOutcome.POSITIVE:
                strategies[r.strategy]["wins"] += 1

        return {
            "total": len(self.records),
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "win_rate": positive / max(positive + negative, 1),
            "total_pnl": sum(r.pnl for r in self.records),
            "batches": len(self.batches),
            "by_strategy": {
                s: {
                    **stats,
                    "avg_pnl": stats["total_pnl"] / max(stats["count"], 1),
                    "win_rate": stats["wins"] / max(stats["count"], 1),
                }
                for s, stats in strategies.items()
            },
        }

    def extract_lessons(self) -> List[Dict[str, Any]]:
        """Extract lessons from collected experiences.

        Returns:
            List of lesson dicts.
        """
        lessons = []
        for r in self.records:
            if r.lessons:
                for lesson in r.lessons:
                    lessons.append({
                        "record_id": r.record_id,
                        "strategy": r.strategy,
                        "category": r.category.value,
                        "outcome": r.outcome.value,
                        "lesson": lesson,
                        "pnl": r.pnl,
                    })
        return lessons
