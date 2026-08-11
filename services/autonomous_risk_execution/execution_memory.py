"""
Execution Memory — persistent storage of execution history.

Stores complete execution records for:
    - Venue performance tracking
    - Strategy performance analysis
    - Cost calibration
    - Pattern recognition
    - Audit trail
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """A complete execution record."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    execution_id: str = ""

    # Order info
    asset: str = ""
    side: str = "BUY"
    target_quantity: int = 0
    filled_quantity: int = 0
    notional: float = 0.0

    # Strategy
    execution_strategy: str = ""
    venue: str = ""
    num_slices: int = 0

    # Prices
    decision_price: float = 0.0
    arrival_price: float = 0.0
    avg_execution_price: float = 0.0

    # Costs
    slippage_bps: float = 0.0
    implementation_shortfall_bps: float = 0.0
    total_cost_bps: float = 0.0

    # Quality
    fill_rate: float = 0.0
    quality_score: float = 0.0
    quality_grade: str = ""

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionMemoryStats:
    """Aggregate statistics from execution memory."""
    total_executions: int = 0
    avg_cost_bps: float = 0.0
    avg_slippage_bps: float = 0.0
    avg_fill_rate: float = 0.0
    by_strategy: dict[str, int] = field(default_factory=dict)
    by_venue: dict[str, int] = field(default_factory=dict)


class ExecutionMemory:
    """
    Persistent execution memory.

    Stores:
        - Complete execution records
        - Event-level detail
        - Aggregate statistics
        - Audit trail for compliance

    Used by:
        - Execution Learning for pattern recognition
        - Cost Model for calibration
        - Strategy Selector for historical performance
    """

    def __init__(self, max_records: int = 10_000) -> None:
        self._max_records = max_records
        self._records: list[ExecutionRecord] = []
        self._total_stored: int = 0

    async def store(self, record: ExecutionRecord) -> None:
        """Store an execution record."""
        self._records.append(record)
        self._total_stored += 1

        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records // 2:]

    async def query(
        self,
        asset: Optional[str] = None,
        strategy: Optional[str] = None,
        venue: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[ExecutionRecord]:
        """Query execution records with filters."""
        results = self._records

        if asset:
            results = [r for r in results if r.asset == asset]
        if strategy:
            results = [r for r in results if r.execution_strategy == strategy]
        if venue:
            results = [r for r in results if r.venue == venue]
        if start_time:
            results = [r for r in results if r.timestamp >= start_time]
        if end_time:
            results = [r for r in results if r.timestamp <= end_time]

        return results[-limit:]

    async def get_stats(
        self, start_time: Optional[datetime] = None,
    ) -> ExecutionMemoryStats:
        """Get aggregate statistics."""
        records = self._records
        if start_time:
            records = [r for r in records if r.timestamp >= start_time]

        if not records:
            return ExecutionMemoryStats()

        stats = ExecutionMemoryStats(
            total_executions=len(records),
            avg_cost_bps=sum(r.total_cost_bps for r in records) / len(records),
            avg_slippage_bps=sum(r.slippage_bps for r in records) / len(records),
            avg_fill_rate=sum(r.fill_rate for r in records) / len(records),
        )

        # By strategy
        strategies: dict[str, int] = {}
        for r in records:
            s = r.execution_strategy or "UNKNOWN"
            strategies[s] = strategies.get(s, 0) + 1
        stats.by_strategy = dict(sorted(strategies.items(), key=lambda x: -x[1]))

        # By venue
        venues: dict[str, int] = {}
        for r in records:
            v = r.venue or "UNKNOWN"
            venues[v] = venues.get(v, 0) + 1
        stats.by_venue = dict(sorted(venues.items(), key=lambda x: -x[1]))

        return stats

    @property
    def total_stored(self) -> int:
        return self._total_stored

    @property
    def record_count(self) -> int:
        return len(self._records)
