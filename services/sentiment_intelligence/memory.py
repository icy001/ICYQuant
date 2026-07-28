"""Sentiment Memory.

Stores and retrieves historical sentiment data, market reactions,
and signal accuracy metrics to build a Market Psychology Knowledge Base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import SentimentRecord, SentimentLabel, EmotionState


@dataclass
class SentimentMemoryEntry:
    """A single entry in the sentiment memory store.

    Attributes:
        entry_id: Unique entry identifier.
        timestamp: When the entry was recorded.
        sentiment: Sentiment data recorded.
        emotion: Detected emotion state.
        market_reaction: Market outcome after the sentiment.
        signal_accuracy: Whether the sentiment signal proved correct.
        notes: Additional context or annotations.
        metadata: Arbitrary metadata.
    """

    entry_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    sentiment: dict[str, Any] = field(default_factory=dict)
    emotion: EmotionState | None = None
    market_reaction: str = ""
    signal_accuracy: bool | None = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_outcome(self) -> bool:
        return self.signal_accuracy is not None

    @property
    def was_accurate(self) -> bool:
        return self.signal_accuracy is True


class SentimentMemory:
    """Persistent memory for market sentiment psychology patterns.

    Tracks sentiment history, market outcomes, and signal accuracy
    to build a knowledge base for improving future predictions.

    Attributes:
        history: List of all memory entries.
        accuracy_stats: Rolling accuracy statistics.
    """

    def __init__(self) -> None:
        self.history: list[SentimentMemoryEntry] = []
        self.accuracy_stats: dict[str, dict[str, float]] = {}

    # --- Storage ---

    def save(self, item: dict[str, Any] | SentimentMemoryEntry) -> None:
        """Save a sentiment memory entry.

        Args:
            item: Either a dict of data or a SentimentMemoryEntry.
        """
        if isinstance(item, SentimentMemoryEntry):
            entry = item
        else:
            entry = SentimentMemoryEntry(
                entry_id=item.get("entry_id", f"mem_{len(self.history):06d}"),
                sentiment=item.get("sentiment", {}),
                emotion=item.get("emotion"),
                market_reaction=item.get("market_reaction", ""),
                signal_accuracy=item.get("signal_accuracy"),
                notes=item.get("notes", ""),
                metadata=item.get("metadata", {}),
            )
        self.history.append(entry)
        self._update_accuracy_stats(entry)

    def save_sentiment(
        self,
        sentiment_score: float,
        label: SentimentLabel,
        emotion: EmotionState,
        symbol: str | None = None,
        notes: str = "",
    ) -> str:
        """Save a sentiment data point with metadata.

        Args:
            sentiment_score: Sentiment score.
            label: Sentiment label.
            emotion: Emotion state.
            symbol: Optional symbol.
            notes: Optional notes.

        Returns:
            Entry ID of the saved memory.
        """
        entry_id = f"sent_{len(self.history):08d}"
        entry = SentimentMemoryEntry(
            entry_id=entry_id,
            sentiment={"score": sentiment_score, "label": label.value, "symbol": symbol},
            emotion=emotion,
            notes=notes,
        )
        self.history.append(entry)
        return entry_id

    def record_outcome(
        self, entry_id: str, market_reaction: str, was_accurate: bool
    ) -> bool:
        """Record the market outcome for a previously saved sentiment.

        Args:
            entry_id: The entry to update.
            market_reaction: Description of market reaction.
            was_accurate: Whether the sentiment signal was correct.

        Returns:
            True if entry was found and updated, False otherwise.
        """
        for entry in self.history:
            if entry.entry_id == entry_id:
                entry.market_reaction = market_reaction
                entry.signal_accuracy = was_accurate
                self._update_accuracy_stats(entry)
                return True
        return False

    # --- Query ---

    def find(self, query: dict[str, Any]) -> list[SentimentMemoryEntry]:
        """Find entries matching query criteria.

        Args:
            query: Dict of field-value pairs to match.

        Returns:
            Matching entries.
        """
        results = self.history
        for key, value in query.items():
            filtered: list[SentimentMemoryEntry] = []
            for entry in results:
                entry_val = getattr(entry, key, None)
                if entry_val == value:
                    filtered.append(entry)
            results = filtered
        return results

    def get_recent(self, limit: int = 10) -> list[SentimentMemoryEntry]:
        """Get most recent memory entries.

        Args:
            limit: Max number of entries.

        Returns:
            Recent entries.
        """
        return self.history[-limit:]

    def get_by_emotion(self, emotion: EmotionState) -> list[SentimentMemoryEntry]:
        """Get entries filtered by emotion state.

        Args:
            emotion: Emotion state.

        Returns:
            Matching entries.
        """
        return [e for e in self.history if e.emotion == emotion]

    def get_with_outcomes(self) -> list[SentimentMemoryEntry]:
        """Get entries that have recorded outcomes.

        Returns:
            Entries with outcomes.
        """
        return [e for e in self.history if e.has_outcome]

    # --- Analysis ---

    def get_accuracy(self, emotion: EmotionState | None = None) -> float:
        """Compute signal accuracy, optionally filtered by emotion.

        Args:
            emotion: Optional emotion filter.

        Returns:
            Accuracy rate [0.0, 1.0].
        """
        entries = self.get_with_outcomes()
        if emotion:
            entries = [e for e in entries if e.emotion == emotion]
        if not entries:
            return 0.0
        accurate = sum(1 for e in entries if e.was_accurate)
        return accurate / len(entries)

    def get_accuracy_report(self) -> dict[str, Any]:
        """Generate a comprehensive accuracy report.

        Returns:
            Dict with accuracy stats by emotion, overall, and counts.
        """
        report: dict[str, Any] = {
            "total_entries": len(self.history),
            "entries_with_outcomes": len(self.get_with_outcomes()),
            "overall_accuracy": self.get_accuracy(),
            "by_emotion": {},
            "by_label": {},
        }

        for emotion in EmotionState:
            acc = self.get_accuracy(emotion)
            count = len([e for e in self.get_with_outcomes() if e.emotion == emotion])
            if count > 0:
                report["by_emotion"][emotion.value] = {"accuracy": acc, "count": count}

        return report

    def get_emotion_distribution(self) -> dict[str, int]:
        """Get distribution of emotion states in memory.

        Returns:
            Dict mapping emotion to count.
        """
        dist: dict[str, int] = {}
        for entry in self.history:
            if entry.emotion:
                dist[entry.emotion.value] = dist.get(entry.emotion.value, 0) + 1
        return dist

    def get_most_reliable_emotion(self) -> EmotionState | None:
        """Find the emotion state with the highest prediction accuracy.

        Returns:
            Most reliable EmotionState or None if no data.
        """
        best_emotion = None
        best_accuracy = 0.0
        for emotion in EmotionState:
            entries = [e for e in self.get_with_outcomes() if e.emotion == emotion]
            if len(entries) >= 3:
                acc = sum(1 for e in entries if e.was_accurate) / len(entries)
                if acc > best_accuracy:
                    best_accuracy = acc
                    best_emotion = emotion
        return best_emotion

    # --- Internal ---

    def _update_accuracy_stats(self, entry: SentimentMemoryEntry) -> None:
        """Update rolling accuracy statistics."""
        if entry.emotion is None or entry.signal_accuracy is None:
            return
        emotion_key = entry.emotion.value
        if emotion_key not in self.accuracy_stats:
            self.accuracy_stats[emotion_key] = {"total": 0, "correct": 0, "accuracy": 0.0}
        stats = self.accuracy_stats[emotion_key]
        stats["total"] += 1
        if entry.signal_accuracy:
            stats["correct"] += 1
        stats["accuracy"] = stats["correct"] / stats["total"]

    def clear(self) -> None:
        """Clear all memory."""
        self.history.clear()
        self.accuracy_stats.clear()

    @property
    def size(self) -> int:
        return len(self.history)
