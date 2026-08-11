"""
Decision Repository
===================
Persistent storage for portfolio decisions with indexed queries,
statistics aggregation, and time-series retrieval.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DecisionSortField(str, Enum):
    """Sort fields for decision queries."""

    CREATED_AT = "created_at"
    CONFIDENCE = "confidence"
    QUANTITY = "quantity"
    ALLOCATED_CAPITAL = "allocated_capital"
    PRIORITY = "priority"


@dataclass
class DecisionQuery:
    """Query filter for retrieving decisions from the repository."""

    portfolio_id: Optional[str] = None
    strategy_id: Optional[str] = None
    instrument: Optional[str] = None
    decision_type: Optional[str] = None
    status: Optional[str] = None
    min_confidence: Optional[float] = None
    min_quantity: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sort_by: DecisionSortField = DecisionSortField.CREATED_AT
    sort_desc: bool = True
    limit: int = 100
    offset: int = 0


@dataclass
class DecisionStats:
    """Aggregated statistics for a set of decisions."""

    total_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    total_capital_allocated: float = 0.0
    total_quantity: float = 0.0
    avg_confidence: float = 0.0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_instrument: Dict[str, int] = field(default_factory=dict)
    by_strategy: Dict[str, int] = field(default_factory=dict)
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_count": self.total_count,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "total_capital_allocated": self.total_capital_allocated,
            "total_quantity": self.total_quantity,
            "avg_confidence": round(self.avg_confidence, 4),
            "by_type": self.by_type,
            "by_instrument": self.by_instrument,
            "by_strategy": self.by_strategy,
            "time_range_start": self.time_range_start.isoformat() if self.time_range_start else None,
            "time_range_end": self.time_range_end.isoformat() if self.time_range_end else None,
        }


class DecisionRepository:
    """
    Persistent storage for portfolio decisions.

    Features:
    - Multi-index querying (portfolio, strategy, instrument, status)
    - Time-series retrieval
    - Statistics aggregation
    - Pagination support
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Primary storage
        self._decisions: Dict[str, Any] = {}

        # Indexes
        self._by_portfolio: Dict[str, List[str]] = defaultdict(list)
        self._by_strategy: Dict[str, List[str]] = defaultdict(list)
        self._by_instrument: Dict[str, List[str]] = defaultdict(list)
        self._by_status: Dict[str, List[str]] = defaultdict(list)
        self._by_type: Dict[str, List[str]] = defaultdict(list)

        # Time-ordered list for efficient range queries
        self._time_ordered: List[str] = []

        self._max_decisions = config.get("max_decisions", 100000) if config else 100000

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("DecisionRepository initialized")

    async def shutdown(self) -> None:
        self._decisions.clear()
        self._by_portfolio.clear()
        self._by_strategy.clear()
        self._by_instrument.clear()
        self._by_status.clear()
        self._by_type.clear()
        self._time_ordered.clear()
        self._initialized = False
        logger.info("DecisionRepository shut down")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, decision: Any) -> str:
        """Save a decision to the repository."""
        decision_id = getattr(decision, "decision_id", "")
        if not decision_id:
            logger.error("Cannot save decision without decision_id")
            return ""

        self._decisions[decision_id] = decision

        # Update indexes
        portfolio_id = getattr(decision, "portfolio_id", "")
        strategy_id = getattr(decision, "strategy_id", "")
        instrument = getattr(decision, "instrument", "")
        status = getattr(decision, "status", "")
        if hasattr(status, "value"):
            status = status.value
        decision_type = getattr(decision, "decision_type", "")
        if hasattr(decision_type, "value"):
            decision_type = decision_type.value

        if portfolio_id:
            self._by_portfolio[portfolio_id].append(decision_id)
        if strategy_id:
            self._by_strategy[strategy_id].append(decision_id)
        if instrument:
            self._by_instrument[instrument].append(decision_id)
        if status:
            self._by_status[status].append(decision_id)
        if decision_type:
            self._by_type[decision_type].append(decision_id)

        # Time ordering
        self._time_ordered.append(decision_id)

        # Evict old if over limit
        while len(self._time_ordered) > self._max_decisions:
            old_id = self._time_ordered.pop(0)
            self._remove_from_indexes(old_id)
            self._decisions.pop(old_id, None)

        return decision_id

    def save_batch(self, decisions: List[Any]) -> List[str]:
        """Save multiple decisions in batch."""
        return [self.save(d) for d in decisions]

    def get(self, decision_id: str) -> Optional[Any]:
        """Retrieve a decision by ID."""
        return self._decisions.get(decision_id)

    def delete(self, decision_id: str) -> bool:
        """Delete a decision by ID."""
        if decision_id not in self._decisions:
            return False
        self._remove_from_indexes(decision_id)
        self._decisions.pop(decision_id, None)
        if decision_id in self._time_ordered:
            self._time_ordered.remove(decision_id)
        return True

    def _remove_from_indexes(self, decision_id: str) -> None:
        """Remove a decision ID from all indexes."""
        for idx in [self._by_portfolio, self._by_strategy, self._by_instrument,
                     self._by_status, self._by_type]:
            for key, id_list in list(idx.items()):
                if decision_id in id_list:
                    id_list.remove(decision_id)
                    if not id_list:
                        del idx[key]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, q: DecisionQuery) -> List[Any]:
        """Query decisions with filters."""
        candidate_ids: Optional[set] = None

        # Narrow by indexed fields first
        if q.portfolio_id:
            ids = set(self._by_portfolio.get(q.portfolio_id, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if q.strategy_id:
            ids = set(self._by_strategy.get(q.strategy_id, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if q.instrument:
            ids = set(self._by_instrument.get(q.instrument, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if q.status:
            ids = set(self._by_status.get(q.status, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if q.decision_type:
            ids = set(self._by_type.get(q.decision_type, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        # If no index filter, scan all
        if candidate_ids is None:
            candidate_ids = set(self._decisions.keys())

        # Apply non-indexed filters
        results = []
        for did in candidate_ids:
            d = self._decisions.get(did)
            if d is None:
                continue

            if q.min_confidence is not None:
                conf = getattr(d, "confidence", 0)
                if conf < q.min_confidence:
                    continue

            if q.min_quantity is not None:
                qty = getattr(d, "quantity", 0)
                if qty < q.min_quantity:
                    continue

            if q.start_time or q.end_time:
                created = getattr(d, "created_at", None)
                if created:
                    if q.start_time and created < q.start_time:
                        continue
                    if q.end_time and created > q.end_time:
                        continue

            results.append(d)

        # Sort
        reverse = q.sort_desc
        sort_key = q.sort_by.value

        def _sort_key(d: Any) -> Any:
            val = getattr(d, sort_key, None)
            if isinstance(val, datetime):
                return val.timestamp()
            return val if val is not None else 0

        results.sort(key=_sort_key, reverse=reverse)

        # Paginate
        return results[q.offset: q.offset + q.limit]

    def get_by_portfolio(self, portfolio_id: str, limit: int = 100) -> List[Any]:
        return self.query(DecisionQuery(portfolio_id=portfolio_id, limit=limit))

    def get_by_strategy(self, strategy_id: str, limit: int = 100) -> List[Any]:
        return self.query(DecisionQuery(strategy_id=strategy_id, limit=limit))

    def get_recent(self, limit: int = 100) -> List[Any]:
        """Get most recent decisions."""
        recent_ids = self._time_ordered[-limit:]
        return [self._decisions[did] for did in recent_ids if did in self._decisions]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def compute_stats(self, q: Optional[DecisionQuery] = None) -> DecisionStats:
        """Compute aggregate statistics for decisions matching query."""
        decisions = self.query(q) if q else list(self._decisions.values())
        stats = DecisionStats()
        stats.total_count = len(decisions)

        confidences = []
        for d in decisions:
            status = getattr(d, "status", "")
            if hasattr(status, "value"):
                status = status.value

            if status == "approved":
                stats.approved_count += 1
            elif status == "rejected":
                stats.rejected_count += 1

            stats.total_capital_allocated += getattr(d, "allocated_capital", 0.0)
            stats.total_quantity += getattr(d, "quantity", 0.0)

            conf = getattr(d, "confidence", 0.0)
            if conf > 0:
                confidences.append(conf)

            dtype = getattr(d, "decision_type", "")
            if hasattr(dtype, "value"):
                dtype = dtype.value
            stats.by_type[dtype] = stats.by_type.get(dtype, 0) + 1

            instrument = getattr(d, "instrument", "")
            if instrument:
                stats.by_instrument[instrument] = stats.by_instrument.get(instrument, 0) + 1

            sid = getattr(d, "strategy_id", "")
            if sid:
                stats.by_strategy[sid] = stats.by_strategy.get(sid, 0) + 1

            created = getattr(d, "created_at", None)
            if created:
                if stats.time_range_start is None or created < stats.time_range_start:
                    stats.time_range_start = created
                if stats.time_range_end is None or created > stats.time_range_end:
                    stats.time_range_end = created

        if confidences:
            stats.avg_confidence = sum(confidences) / len(confidences)

        return stats

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self._decisions)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
