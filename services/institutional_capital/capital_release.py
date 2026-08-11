"""
Capital Release — Return Capital to the Available Pool

Handles the release of capital back to the available pool when:
- Strategy stops / is paused
- Order is cancelled (unfilled)
- Position is closed
- Allocation is reduced
- Reservation expires

Lifecycle: DEPLOYED → RELEASED → AVAILABLE
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReleaseType(str, Enum):
    STRATEGY_STOP = "STRATEGY_STOP"
    ORDER_CANCEL = "ORDER_CANCEL"
    POSITION_CLOSE = "POSITION_CLOSE"
    ALLOCATION_REDUCE = "ALLOCATION_REDUCE"
    RESERVATION_EXPIRE = "RESERVATION_EXPIRE"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class ReleaseRecord:
    release_id: str
    release_type: ReleaseType
    amount: float
    strategy_id: Optional[str]
    source_state: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapitalRelease:
    """
    Manages capital release operations back to the available pool.

    Ensures orderly release: deployed → allocated reduction → available.
    Handles emergency releases with priority.
    """

    def __init__(
        self,
        release_id: Optional[str] = None,
        capital_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.release_id = release_id or f"crl-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self.config = config or {}
        self._records: List[ReleaseRecord] = []
        self._pending_releases: Dict[str, ReleaseRecord] = {}
        self._total_released: float = 0.0

    def release(
        self,
        amount: float,
        strategy_id: Optional[str] = None,
        release_type: ReleaseType = ReleaseType.MANUAL,
        reason: str = "",
    ) -> ReleaseRecord:
        """Release capital back to available pool."""
        record = ReleaseRecord(
            release_id=f"rel-{uuid.uuid4().hex[:8]}",
            release_type=release_type,
            amount=amount,
            strategy_id=strategy_id,
            source_state="ALLOCATED",
            reason=reason,
        )

        if self._capital_pool:
            if strategy_id:
                self._capital_pool.deallocate(amount, strategy_id)
            self._capital_pool.release(amount, reason)

        self._total_released += amount
        self._records.append(record)
        logger.info(f"Released {amount} from {strategy_id or 'pool'} ({release_type.value})")
        return record

    def emergency_release_all(self) -> List[ReleaseRecord]:
        """Emergency release of all allocated capital."""
        records = []
        if self._capital_pool:
            for sid, amount in self._capital_pool.get_all_allocations().items():
                if amount > 0:
                    records.append(self.release(
                        amount, sid,
                        release_type=ReleaseType.EMERGENCY,
                        reason="EMERGENCY_RELEASE_ALL",
                    ))
        logger.critical(f"EMERGENCY: Released all capital ({len(records)} strategies)")
        return records

    def release_for_strategy(self, strategy_id: str, amount: Optional[float] = None) -> ReleaseRecord:
        """Release capital for a specific strategy."""
        if amount is None and self._capital_pool:
            amount = self._capital_pool.get_allocation(strategy_id)
        amount = amount or 0.0
        return self.release(amount, strategy_id, ReleaseType.STRATEGY_STOP)

    def get_total_released(self) -> float:
        return self._total_released

    def get_history(self) -> List[ReleaseRecord]:
        return list(self._records)

    def get_summary(self) -> Dict[str, Any]:
        by_type = {}
        for r in self._records:
            by_type[r.release_type.value] = by_type.get(r.release_type.value, 0.0) + r.amount
        return {
            "release_id": self.release_id,
            "total_released": self._total_released,
            "record_count": len(self._records),
            "by_type": by_type,
        }
