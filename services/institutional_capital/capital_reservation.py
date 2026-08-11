"""
Capital Reservation — Prevent Double-Allocation

Before a strategy can deploy capital, it must reserve it.
This prevents multiple strategies from simultaneously consuming
the same capital:

    Request → Reserve → Allocate → Deploy → Release
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReservationState(str, Enum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    CONVERTED = "CONVERTED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class Reservation:
    reservation_id: str
    strategy_id: str
    amount: float
    state: ReservationState = ReservationState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


class CapitalReservation:
    """
    Manages capital reservations to prevent double-allocation.

    Lifecycle:
      PENDING → RESERVED → CONVERTED (to allocation)
                        → RELEASED (back to available)
                        → EXPIRED (timeout)
    """

    def __init__(
        self,
        reservation_id: Optional[str] = None,
        capital_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.reservation_id = reservation_id or f"crv-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self.config = config or {}
        self._default_ttl_seconds = self.config.get("reservation_ttl_seconds", 300)
        self._reservations: Dict[str, Reservation] = {}
        self._by_strategy: Dict[str, List[str]] = {}

    def request(
        self,
        strategy_id: str,
        amount: float,
        reason: str = "",
        ttl_seconds: Optional[int] = None,
    ) -> Reservation:
        """Request a capital reservation."""
        ttl = ttl_seconds or self._default_ttl_seconds
        res = Reservation(
            reservation_id=f"res-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            amount=amount,
            state=ReservationState.PENDING,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            reason=reason,
        )

        # Check availability
        if self._capital_pool:
            available = self._capital_pool.available_capital
            if amount > available:
                res.state = ReservationState.CANCELLED
                res.metadata["reject_reason"] = f"Insufficient: {amount} > {available}"
                self._reservations[res.reservation_id] = res
                return res

            self._capital_pool.reserve(amount, reason)

        res.state = ReservationState.RESERVED
        self._reservations[res.reservation_id] = res
        self._by_strategy.setdefault(strategy_id, []).append(res.reservation_id)

        logger.info(f"Reservation {res.reservation_id}: {strategy_id} reserved {amount}")
        return res

    def convert(self, reservation_id: str) -> Optional[Reservation]:
        """Convert reservation to actual allocation."""
        res = self._reservations.get(reservation_id)
        if not res or res.state != ReservationState.RESERVED:
            return None

        if self._capital_pool:
            self._capital_pool.allocate(res.amount, res.strategy_id)

        res.state = ReservationState.CONVERTED
        res.converted_at = datetime.utcnow()
        return res

    def release(self, reservation_id: str) -> Optional[Reservation]:
        """Release reservation back to available."""
        res = self._reservations.get(reservation_id)
        if not res or res.state not in (ReservationState.RESERVED, ReservationState.PENDING):
            return None

        if self._capital_pool:
            self._capital_pool.release(res.amount, res.reason)

        res.state = ReservationState.RELEASED
        res.released_at = datetime.utcnow()
        return res

    def expire_stale(self) -> List[Reservation]:
        """Expire all stale reservations."""
        expired = []
        for res in self._reservations.values():
            if res.state == ReservationState.RESERVED and res.is_expired:
                self.release(res.reservation_id)
                res.state = ReservationState.EXPIRED
                expired.append(res)
        if expired:
            logger.info(f"Expired {len(expired)} stale reservations")
        return expired

    def get_strategy_reserved(self, strategy_id: str) -> float:
        ids = self._by_strategy.get(strategy_id, [])
        return sum(
            self._reservations[rid].amount
            for rid in ids
            if self._reservations[rid].state == ReservationState.RESERVED
        )

    def get_total_reserved(self) -> float:
        return sum(
            r.amount for r in self._reservations.values()
            if r.state == ReservationState.RESERVED
        )

    def get_summary(self) -> Dict[str, Any]:
        by_state = {}
        for r in self._reservations.values():
            by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
        return {
            "reservation_id": self.reservation_id,
            "total_reserved": self.get_total_reserved(),
            "count": len(self._reservations),
            "by_state": by_state,
        }
