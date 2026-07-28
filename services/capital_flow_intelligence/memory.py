"""Capital Flow Memory.

Stores and retrieves historical capital flow data, market reactions,
institutional behavior patterns, and signal accuracy to build a
Smart Money Knowledge Base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import FlowSource, FlowDirection, InstitutionalBehavior, SmartMoneyAction


@dataclass
class CapitalMemoryEntry:
    """A single entry in the capital flow memory.

    Attributes:
        entry_id: Unique entry identifier.
        timestamp: When the entry was recorded.
        flow_data: Capital flow data recorded.
        behavior: Detected institutional behavior.
        smart_money: Smart money action observed.
        market_reaction: Market outcome after the flow event.
        signal_accuracy: Whether the flow signal proved correct.
        notes: Additional context.
        metadata: Arbitrary metadata.
    """

    entry_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    flow_data: dict[str, Any] = field(default_factory=dict)
    behavior: InstitutionalBehavior | None = None
    smart_money: SmartMoneyAction | None = None
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


class CapitalMemory:
    """Persistent memory for capital flow intelligence patterns.

    Tracks flow history, market outcomes, institutional behavior accuracy,
    and smart money performance to build a knowledge base for improving
    future capital flow predictions.

    Attributes:
        history: List of all memory entries.
        accuracy_stats: Rolling accuracy statistics.
    """

    def __init__(self) -> None:
        self.history: list[CapitalMemoryEntry] = []
        self.accuracy_stats: dict[str, dict[str, float]] = {}

    # --- Storage ---

    def save(self, item: dict[str, Any] | CapitalMemoryEntry) -> None:
        """Save a capital flow memory entry.

        Args:
            item: Either a dict of data or a CapitalMemoryEntry.
        """
        if isinstance(item, CapitalMemoryEntry):
            entry = item
        else:
            entry = CapitalMemoryEntry(
                entry_id=item.get("entry_id", f"cap_{len(self.history):06d}"),
                flow_data=item.get("flow_data", {}),
                behavior=item.get("behavior"),
                smart_money=item.get("smart_money"),
                market_reaction=item.get("market_reaction", ""),
                signal_accuracy=item.get("signal_accuracy"),
                notes=item.get("notes", ""),
                metadata=item.get("metadata", {}),
            )
        self.history.append(entry)
        self._update_accuracy_stats(entry)

    def save_flow(
        self,
        asset: str,
        net_flow: float,
        behavior: InstitutionalBehavior,
        smart_money: SmartMoneyAction | None = None,
        notes: str = "",
    ) -> str:
        """Save a capital flow observation with metadata.

        Args:
            asset: Asset identifier.
            net_flow: Net flow amount.
            behavior: Institutional behavior.
            smart_money: Smart money action.
            notes: Optional notes.

        Returns:
            Entry ID of the saved memory.
        """
        entry_id = f"flow_{len(self.history):08d}"
        entry = CapitalMemoryEntry(
            entry_id=entry_id,
            flow_data={"asset": asset, "net_flow": net_flow},
            behavior=behavior,
            smart_money=smart_money,
            notes=notes,
        )
        self.history.append(entry)
        return entry_id

    def record_outcome(
        self, entry_id: str, market_reaction: str, was_accurate: bool
    ) -> bool:
        """Record market outcome for a previous flow observation.

        Args:
            entry_id: The entry to update.
            market_reaction: Description of market reaction.
            was_accurate: Whether the flow signal was correct.

        Returns:
            True if found and updated.
        """
        for entry in self.history:
            if entry.entry_id == entry_id:
                entry.market_reaction = market_reaction
                entry.signal_accuracy = was_accurate
                self._update_accuracy_stats(entry)
                return True
        return False

    # --- Query ---

    def find(self, query: dict[str, Any]) -> list[CapitalMemoryEntry]:
        """Find entries matching criteria.

        Args:
            query: Dict of field-value pairs.

        Returns:
            Matching entries.
        """
        results = self.history
        for key, value in query.items():
            filtered: list[CapitalMemoryEntry] = []
            for entry in results:
                entry_val = getattr(entry, key, None)
                if entry_val == value:
                    filtered.append(entry)
            results = filtered
        return results

    def get_recent(self, limit: int = 10) -> list[CapitalMemoryEntry]:
        """Get most recent entries."""
        return self.history[-limit:]

    def get_by_behavior(
        self, behavior: InstitutionalBehavior
    ) -> list[CapitalMemoryEntry]:
        """Get entries by institutional behavior."""
        return [e for e in self.history if e.behavior == behavior]

    def get_by_smart_money(
        self, action: SmartMoneyAction
    ) -> list[CapitalMemoryEntry]:
        """Get entries by smart money action."""
        return [e for e in self.history if e.smart_money == action]

    def get_with_outcomes(self) -> list[CapitalMemoryEntry]:
        """Get entries with recorded outcomes."""
        return [e for e in self.history if e.has_outcome]

    # --- Analysis ---

    def get_accuracy(
        self, behavior: InstitutionalBehavior | None = None
    ) -> float:
        """Compute flow signal accuracy.

        Args:
            behavior: Optional behavior filter.

        Returns:
            Accuracy rate [0.0, 1.0].
        """
        entries = self.get_with_outcomes()
        if behavior:
            entries = [e for e in entries if e.behavior == behavior]
        if not entries:
            return 0.0
        accurate = sum(1 for e in entries if e.was_accurate)
        return accurate / len(entries)

    def get_accuracy_report(self) -> dict[str, Any]:
        """Generate comprehensive accuracy report.

        Returns:
            Dict with accuracy stats by behavior, smart money, and overall.
        """
        report: dict[str, Any] = {
            "total_entries": len(self.history),
            "entries_with_outcomes": len(self.get_with_outcomes()),
            "overall_accuracy": self.get_accuracy(),
            "by_behavior": {},
            "by_smart_money": {},
        }

        for behavior in InstitutionalBehavior:
            acc = self.get_accuracy(behavior)
            count = len([e for e in self.get_with_outcomes() if e.behavior == behavior])
            if count > 0:
                report["by_behavior"][behavior.value] = {"accuracy": acc, "count": count}

        for action in SmartMoneyAction:
            entries = [e for e in self.get_with_outcomes() if e.smart_money == action]
            if entries:
                acc = sum(1 for e in entries if e.was_accurate) / len(entries)
                report["by_smart_money"][action.value] = {"accuracy": acc, "count": len(entries)}

        return report

    def get_most_reliable_behavior(self) -> InstitutionalBehavior | None:
        """Find institutional behavior with highest prediction accuracy.

        Returns:
            Most reliable behavior or None.
        """
        best = None
        best_acc = 0.0
        for behavior in InstitutionalBehavior:
            entries = [e for e in self.get_with_outcomes() if e.behavior == behavior]
            if len(entries) >= 3:
                acc = sum(1 for e in entries if e.was_accurate) / len(entries)
                if acc > best_acc:
                    best_acc = acc
                    best = behavior
        return best

    def get_smart_money_win_rate(self) -> dict[str, float]:
        """Get win rates for each smart money action.

        Returns:
            Dict mapping action to win rate.
        """
        rates: dict[str, float] = {}
        for action in SmartMoneyAction:
            entries = [e for e in self.get_with_outcomes() if e.smart_money == action]
            if entries:
                rates[action.value] = sum(1 for e in entries if e.was_accurate) / len(entries)
        return rates

    # --- Internal ---

    def _update_accuracy_stats(self, entry: CapitalMemoryEntry) -> None:
        """Update rolling accuracy statistics."""
        if entry.behavior is None or entry.signal_accuracy is None:
            return
        key = entry.behavior.value
        if key not in self.accuracy_stats:
            self.accuracy_stats[key] = {"total": 0, "correct": 0, "accuracy": 0.0}
        stats = self.accuracy_stats[key]
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
