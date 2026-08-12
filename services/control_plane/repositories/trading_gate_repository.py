"""
TradingGateRepository — persistent audit trail of gate decisions.

Every gate evaluation is stored as a :class:`GateDecisionRecord` (decision
snapshot + policy version + correlation id).  This makes it possible to
reproduce *why* any past order was allowed or denied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..trading_gate.gate_decision import GateDecision, GateDecisionRecord


@dataclass
class TradingGateRepository:
    """In-memory store of gate decision records."""

    _records: List[Dict[str, Any]] = field(default_factory=list)

    # -- writes ----------------------------------------------------------

    def save_record(self, record: GateDecisionRecord) -> None:
        self._records.append(record.to_dict())

    # -- queries ---------------------------------------------------------

    def list_records(self) -> List[GateDecisionRecord]:
        return [GateDecisionRecord.from_dict(r) for r in self._records]

    def record_count(self) -> int:
        return len(self._records)

    def get_latest(self) -> Optional[GateDecisionRecord]:
        if not self._records:
            return None
        return GateDecisionRecord.from_dict(self._records[-1])

    def get_latest_for_order(self, order_id: str) -> Optional[GateDecisionRecord]:
        for raw in reversed(self._records):
            if raw.get("order_id") == order_id:
                return GateDecisionRecord.from_dict(raw)
        return None

    def count_by_decision(self, decision: GateDecision) -> int:
        return sum(1 for r in self._records if r.get("decision") == decision.value)

    def allow_count(self) -> int:
        return self.count_by_decision(GateDecision.ALLOW)

    def deny_count(self) -> int:
        return self.count_by_decision(GateDecision.DENY)

    def clear(self) -> None:
        self._records.clear()
