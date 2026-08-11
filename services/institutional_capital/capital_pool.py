"""
Capital Pool — Aggregate Capital Management

The CapitalPool is the single source of truth for institutional capital.
It enforces the fundamental conservation law:

    Total Capital = Allocated + Reserved + Available

All capital movements go through this pool. It tracks:
- Total capital base (AUM)
- Allocated capital (committed to strategies)
- Reserved capital (ring-fenced for specific purposes)
- Available capital (ready for deployment)
- Deployed capital (actively at risk in markets)
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PoolState(str, Enum):
    INITIALIZING = "INITIALIZING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    FROZEN = "FROZEN"
    DRAINING = "DRAINING"


@dataclass
class PoolTransaction:
    tx_id: str
    tx_type: str
    amount: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapitalPool:
    """
    Central institutional capital pool enforcing the conservation law:

        Total = Allocated + Reserved + Available
    """

    def __init__(
        self,
        pool_id: Optional[str] = None,
        initial_capital: float = 0.0,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.pool_id = pool_id or f"cp-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self.state = PoolState.INITIALIZING
        self.created_at = datetime.utcnow()

        self._total: float = initial_capital
        self._allocated: float = 0.0
        self._reserved: float = 0.0
        self._deployed: float = 0.0

        self._allocations: Dict[str, float] = {}
        self._reservations: Dict[str, float] = {}
        self._accounts: Dict[str, Any] = {}

        self._transactions: List[PoolTransaction] = []
        self._snapshots: List[Dict[str, Any]] = []

        self.state = PoolState.OPEN
        logger.info(f"CapitalPool {self.pool_id} opened with {initial_capital}")

    # ─── Properties (conservation enforcement) ────────────────

    @property
    def total_capital(self) -> float:
        return self._total

    @total_capital.setter
    def total_capital(self, value: float):
        self._total = max(0.0, value)

    @property
    def allocated_capital(self) -> float:
        return self._allocated

    @property
    def reserved_capital(self) -> float:
        return self._reserved

    @property
    def available_capital(self) -> float:
        return max(0.0, self._total - self._allocated - self._reserved)

    @property
    def deployed_capital(self) -> float:
        return self._deployed

    @property
    def unallocated_capital(self) -> float:
        return self.available_capital

    def validate_conservation(self) -> bool:
        delta = abs(self._total - (self._allocated + self._reserved + self.available_capital))
        return delta < 0.02

    # ─── Capital Allocation ───────────────────────────────────

    def allocate(self, amount: float, strategy_id: str) -> float:
        """Allocate capital from available to a strategy. Returns amount actually allocated."""
        amount = min(amount, self.available_capital)
        if amount <= 0:
            return 0.0

        self._allocated += amount
        self._allocations[strategy_id] = self._allocations.get(strategy_id, 0.0) + amount

        self._record_tx("ALLOCATE", amount, {"strategy_id": strategy_id})
        return amount

    def deallocate(self, amount: float, strategy_id: str) -> float:
        """Deallocate capital from a strategy back to available."""
        current = self._allocations.get(strategy_id, 0.0)
        amount = min(amount, current)
        if amount <= 0:
            return 0.0

        self._allocated = max(0.0, self._allocated - amount)
        self._allocations[strategy_id] = current - amount

        self._record_tx("DEALLOCATE", amount, {"strategy_id": strategy_id})
        return amount

    def reserve(self, amount: float, reason: str = "") -> bool:
        """Reserve capital (ring-fence from available)."""
        if amount > self.available_capital:
            return False
        self._reserved += amount
        self._reservations[reason or f"res_{len(self._reservations)}"] = amount
        self._record_tx("RESERVE", amount, {"reason": reason})
        return True

    def release(self, amount: float, reason: str = "") -> bool:
        """Release reserved capital back to available."""
        amount = min(amount, self._reserved)
        if amount <= 0:
            return False
        self._reserved = max(0.0, self._reserved - amount)
        self._record_tx("RELEASE", amount, {"reason": reason})
        return True

    def deploy(self, amount: float) -> None:
        """Mark capital as deployed (at risk in markets)."""
        amount = min(amount, self._allocated - self._deployed)
        self._deployed += amount
        self._record_tx("DEPLOY", amount, {})

    def undeploy(self, amount: float) -> None:
        """Mark capital as no longer deployed."""
        amount = min(amount, self._deployed)
        self._deployed = max(0.0, self._deployed - amount)
        self._record_tx("UNDEPLOY", amount, {})

    # ─── Lifecycle ────────────────────────────────────────────

    def add_capital(self, amount: float) -> None:
        """Add capital to the pool (capital injection)."""
        self._total += amount
        self._record_tx("INJECT", amount, {})

    def withdraw_capital(self, amount: float) -> float:
        """Withdraw capital (redemption). Returns actual amount withdrawn."""
        amount = min(amount, self.available_capital)
        if amount <= 0:
            return 0.0
        self._total = max(0.0, self._total - amount)
        self._record_tx("WITHDRAW", amount, {})
        return amount

    def freeze(self) -> None:
        self.state = PoolState.FROZEN
        logger.warning(f"CapitalPool {self.pool_id} FROZEN")

    def unfreeze(self) -> None:
        self.state = PoolState.OPEN
        logger.info(f"CapitalPool {self.pool_id} UNFROZEN")

    # ─── Queries ──────────────────────────────────────────────

    def get_allocation(self, strategy_id: str) -> float:
        return self._allocations.get(strategy_id, 0.0)

    def get_all_allocations(self) -> Dict[str, float]:
        return dict(self._allocations)

    def get_utilization(self) -> float:
        if self._total <= 0:
            return 0.0
        return self._allocated / self._total

    def get_deployment_ratio(self) -> float:
        if self._allocated <= 0:
            return 0.0
        return self._deployed / self._allocated

    def take_snapshot(self) -> Dict[str, Any]:
        snap = {
            "snapshot_id": f"snp-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "total": self._total,
            "allocated": self._allocated,
            "reserved": self._reserved,
            "available": self.available_capital,
            "deployed": self._deployed,
            "utilization": self.get_utilization(),
            "allocations": dict(self._allocations),
            "conservation_ok": self.validate_conservation(),
        }
        self._snapshots.append(snap)
        return snap

    def get_summary(self) -> Dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "state": self.state.value,
            "total_capital": self._total,
            "allocated": self._allocated,
            "reserved": self._reserved,
            "available": self.available_capital,
            "deployed": self._deployed,
            "utilization": self.get_utilization(),
            "strategy_count": len(self._allocations),
            "conservation_ok": self.validate_conservation(),
        }

    # ─── Internal ─────────────────────────────────────────────

    def _record_tx(self, tx_type: str, amount: float, metadata: Dict[str, Any]) -> None:
        self._transactions.append(PoolTransaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            tx_type=tx_type,
            amount=amount,
            metadata=metadata,
        ))
