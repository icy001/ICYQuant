"""Allocation History — historical analysis of allocation performance.

Tracks:
- Per-strategy allocation history
- Weight drift over time
- Decision pattern analysis
- Performance attribution by allocation change
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AllocationRecord:
    """Historical record of a single allocation change."""
    strategy_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    previous_weight: float = 0.0
    new_weight: float = 0.0
    previous_capital: float = 0.0
    new_capital: float = 0.0
    capital_delta: float = 0.0
    decision_type: str = ""
    alpha_at_time: float = 0.0
    risk_at_time: float = 0.0
    realized_alpha: Optional[float] = None
    realized_risk: Optional[float] = None

    @property
    def weight_delta(self) -> float:
        return self.new_weight - self.previous_weight


@dataclass
class HistorySummary:
    """Summary of allocation history."""
    strategy_id: str
    total_changes: int = 0
    increase_count: int = 0
    decrease_count: int = 0
    total_capital_in: float = 0.0
    total_capital_out: float = 0.0
    net_flow: float = 0.0
    avg_weight: float = 0.0
    min_weight: float = 1.0
    max_weight: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class AllocationHistory:
    """Maintains historical record of all allocation changes.

    Used for: performance attribution, pattern detection,
    and compliance audit.
    """

    def __init__(self, max_records: int = 100000):
        self._records: Dict[str, List[AllocationRecord]] = {}
        self._max_records = max_records

    def record_change(self, strategy_id: str,
                      previous_weight: float, new_weight: float,
                      previous_capital: float, new_capital: float,
                      decision_type: str = "",
                      alpha_at_time: float = 0.0,
                      risk_at_time: float = 0.0) -> AllocationRecord:
        """Record an allocation change in history."""
        if strategy_id not in self._records:
            self._records[strategy_id] = []

        record = AllocationRecord(
            strategy_id=strategy_id,
            previous_weight=previous_weight,
            new_weight=new_weight,
            previous_capital=previous_capital,
            new_capital=new_capital,
            capital_delta=new_capital - previous_capital,
            decision_type=decision_type,
            alpha_at_time=alpha_at_time,
            risk_at_time=risk_at_time,
        )
        self._records[strategy_id].append(record)

        # Enforce max records
        if len(self._records[strategy_id]) > self._max_records:
            self._records[strategy_id] = self._records[strategy_id][-self._max_records:]

        return record

    def get_history(self, strategy_id: str,
                    limit: int = 100) -> List[AllocationRecord]:
        """Get allocation history for a strategy."""
        return self._records.get(strategy_id, [])[-limit:]

    def summarize(self, strategy_id: str) -> HistorySummary:
        """Summarize allocation history for a strategy."""
        records = self._records.get(strategy_id, [])
        if not records:
            return HistorySummary(strategy_id=strategy_id)

        summary = HistorySummary(strategy_id=strategy_id)
        summary.total_changes = len(records)
        summary.first_seen = records[0].timestamp
        summary.last_seen = records[-1].timestamp

        total_cap_in = 0.0
        total_cap_out = 0.0
        all_weights = []

        for r in records:
            if r.capital_delta > 0:
                summary.increase_count += 1
                total_cap_in += r.capital_delta
            elif r.capital_delta < 0:
                summary.decrease_count += 1
                total_cap_out += abs(r.capital_delta)
            all_weights.append(r.new_weight)

        summary.total_capital_in = total_cap_in
        summary.total_capital_out = total_cap_out
        summary.net_flow = total_cap_in - total_cap_out

        if all_weights:
            summary.avg_weight = sum(all_weights) / len(all_weights)
            summary.min_weight = min(all_weights)
            summary.max_weight = max(all_weights)

        return summary

    def get_all_summaries(self) -> Dict[str, HistorySummary]:
        """Summarize all strategies."""
        return {sid: self.summarize(sid) for sid in self._records}

    def update_realized(self, strategy_id: str,
                        record_index: int,
                        realized_alpha: float = None,
                        realized_risk: float = None) -> bool:
        """Update realized values for a historical record."""
        records = self._records.get(strategy_id, [])
        if record_index < 0 or record_index >= len(records):
            return False
        record = records[record_index]
        if realized_alpha is not None:
            record.realized_alpha = realized_alpha
        if realized_risk is not None:
            record.realized_risk = realized_risk
        return True

    def clear(self, strategy_id: str = None) -> None:
        """Clear history."""
        if strategy_id:
            self._records.pop(strategy_id, None)
        else:
            self._records.clear()
