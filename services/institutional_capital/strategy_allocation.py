"""
Strategy Allocation — Strategy-Level Capital Assignment Records

Tracks the full lifecycle of a strategy's capital allocation:
- How much capital the strategy has
- When it was allocated/deallocated
- Performance attribution for the allocated capital
- Allocation history for trend analysis
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class StrategyAllocState(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    RESERVED = "RESERVED"
    ACTIVE = "ACTIVE"
    REDUCING = "REDUCING"
    RELEASED = "RELEASED"


@dataclass
class StrategyAllocRecord:
    record_id: str
    strategy_id: str
    state: StrategyAllocState = StrategyAllocState.PROPOSED
    amount: float = 0.0
    cumulative: float = 0.0
    risk_budget: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    performance_since: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyAllocation:
    """
    Tracks and manages individual strategy capital allocation records.

    Maintains the allocation history and cumulative totals for each
    strategy, enabling trend analysis and performance attribution.
    """

    def __init__(
        self,
        alloc_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.alloc_id = alloc_id or f"salloc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._records: Dict[str, StrategyAllocRecord] = {}
        self._strategy_history: Dict[str, List[str]] = {}

    def propose(
        self,
        strategy_id: str,
        amount: float,
        risk_budget: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StrategyAllocRecord:
        record = StrategyAllocRecord(
            record_id=f"sar-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            amount=amount,
            risk_budget=risk_budget,
            metadata=metadata or {},
        )
        self._records[record.record_id] = record
        self._strategy_history.setdefault(strategy_id, []).append(record.record_id)
        return record

    def approve(self, record_id: str) -> Optional[StrategyAllocRecord]:
        rec = self._records.get(record_id)
        if rec:
            rec.state = StrategyAllocState.APPROVED
        return rec

    def activate(self, record_id: str, current_cumulative: float) -> Optional[StrategyAllocRecord]:
        rec = self._records.get(record_id)
        if rec:
            rec.state = StrategyAllocState.ACTIVE
            rec.cumulative = current_cumulative
            rec.activated_at = datetime.utcnow()
        return rec

    def release(self, record_id: str) -> Optional[StrategyAllocRecord]:
        rec = self._records.get(record_id)
        if rec:
            rec.state = StrategyAllocState.RELEASED
            rec.released_at = datetime.utcnow()
        return rec

    def get_strategy_total(self, strategy_id: str) -> float:
        ids = self._strategy_history.get(strategy_id, [])
        return sum(
            self._records[rid].amount
            for rid in ids
            if self._records[rid].state == StrategyAllocState.ACTIVE
        )

    def get_strategy_history(self, strategy_id: str) -> List[StrategyAllocRecord]:
        ids = self._strategy_history.get(strategy_id, [])
        return [self._records[rid] for rid in ids]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "alloc_id": self.alloc_id,
            "record_count": len(self._records),
            "strategies": list(self._strategy_history.keys()),
        }
