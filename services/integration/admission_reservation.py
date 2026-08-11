"""AdmissionReservation — reserves resources (buying power, position limits) for admitted orders.

Reservation prevents oversubscription: if available buying power is insufficient,
the admission fails with RESERVATION_FAILED. Reservations are released/ converted
when the order executes or is cancelled.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from .order_intent import OrderIntent


class ReservationStatus(Enum):
    """Reservation lifecycle status."""
    RESERVED = auto()
    RELEASED = auto()
    CONVERTED = auto()
    FAILED = auto()

    @property
    def label(self) -> str:
        _labels = {
            ReservationStatus.RESERVED: "RESERVED",
            ReservationStatus.RELEASED: "RELEASED",
            ReservationStatus.CONVERTED: "CONVERTED",
            ReservationStatus.FAILED: "FAILED",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class Reservation:
    """A single resource reservation."""
    reservation_id: str = field(
        default_factory=lambda: f"RESV-{uuid.uuid4().hex[:12].upper()}"
    )
    account_id: str = ""
    order_id: str = ""
    flow_id: str = ""

    amount_reserved: float = 0.0
    currency: str = "USD"

    status: ReservationStatus = ReservationStatus.RESERVED
    created_at: float = field(default_factory=lambda: time.time())
    released_at: Optional[float] = None

    def release(self) -> "Reservation":
        """Release the reservation (order cancelled or expired)."""
        self.status = ReservationStatus.RELEASED
        self.released_at = time.time()
        return self

    def convert(self) -> "Reservation":
        """Convert reservation to actual position (order executed)."""
        self.status = ReservationStatus.CONVERTED
        self.released_at = time.time()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "account_id": self.account_id,
            "order_id": self.order_id,
            "flow_id": self.flow_id,
            "amount_reserved": self.amount_reserved,
            "currency": self.currency,
            "status": self.status.name,
            "created_at": self.created_at,
            "released_at": self.released_at,
        }

    def __repr__(self) -> str:
        return (
            f"Reservation(id={self.reservation_id}, account={self.account_id}, "
            f"amount={self.amount_reserved}, status={self.status.label})"
        )


@dataclass
class ReservationResult:
    """Result of a reservation attempt."""
    success: bool = True
    reservation: Optional[Reservation] = None
    code: str = ""
    message: str = ""
    available: Optional[float] = None
    requested: Optional[float] = None


@dataclass
class AdmissionReservation:
    """Manages resource reservations for admitted orders.

    Tracks available buying power and reserves amounts for orders
    that pass admission. Prevents oversubscription.
    """

    # In-memory account balances. In production, this would query ledger/risk.
    _balances: Dict[str, float] = field(default_factory=dict, repr=False)
    _reservations: Dict[str, Reservation] = field(default_factory=dict, repr=False)

    def set_balance(self, account_id: str, amount: float) -> "AdmissionReservation":
        """Set the available balance for an account."""
        self._balances[account_id] = amount
        return self

    def get_available(self, account_id: str) -> float:
        """Get available balance for an account."""
        return self._balances.get(account_id, 0.0)

    def reserve(
        self, intent: OrderIntent, order_id: str
    ) -> ReservationResult:
        """Attempt to reserve resources for an order.

        Checks available balance and, if sufficient, creates a reservation.
        """
        account_id = intent.account_id
        notional = intent.notional

        if notional <= 0:
            return ReservationResult(
                success=False,
                code="INVALID_NOTIONAL",
                message=f"Notional must be positive, got {notional}",
                requested=notional,
            )

        available = self.get_available(account_id)

        if notional > available:
            return ReservationResult(
                success=False,
                code="INSUFFICIENT_BALANCE",
                message=f"Notional {notional} exceeds available balance {available}",
                available=available,
                requested=notional,
            )

        # Deduct from available balance
        self._balances[account_id] = available - notional

        reservation = Reservation(
            account_id=account_id,
            order_id=order_id,
            flow_id=intent.flow_id,
            amount_reserved=notional,
            currency=intent.currency,
        )

        self._reservations[reservation.reservation_id] = reservation

        return ReservationResult(
            success=True,
            reservation=reservation,
            code="RESERVATION_SUCCESS",
            message=f"Reserved {notional} for order {order_id}",
            available=available,
            requested=notional,
        )

    def release(self, reservation_id: str) -> Optional[Reservation]:
        """Release a reservation and return funds to available balance."""
        reservation = self._reservations.get(reservation_id)
        if not reservation:
            return None
        if reservation.status != ReservationStatus.RESERVED:
            return reservation

        reservation.release()
        self._balances[reservation.account_id] = (
            self._balances.get(reservation.account_id, 0.0)
            + reservation.amount_reserved
        )
        return reservation

    def convert(self, reservation_id: str) -> Optional[Reservation]:
        """Convert reservation to actual position (on execution)."""
        reservation = self._reservations.get(reservation_id)
        if not reservation:
            return None
        reservation.convert()
        return reservation

    def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        """Get a reservation by ID."""
        return self._reservations.get(reservation_id)

    def reset(self) -> None:
        """Clear all state (for testing)."""
        self._balances.clear()
        self._reservations.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "balances": dict(self._balances),
            "active_reservations": len([
                r for r in self._reservations.values()
                if r.status == ReservationStatus.RESERVED
            ]),
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionReservation(accounts={len(self._balances)}, "
            f"active_reservations={len(self._reservations)})"
        )
