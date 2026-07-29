"""Trade Confirmation.

Receives broker fill events and generates confirmed trade records.
These records are sent to:
- Ledger (accounting)
- Position Manager (portfolio updates)
- Risk Engine (risk updates)

Guarantees that trade results enter the system's core ledger
with full audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================


class ConfirmationStatus(str, Enum):
    """Status of a trade confirmation."""

    PENDING = "PENDING"          # Waiting for processing
    CONFIRMED = "CONFIRMED"      # Confirmed and recorded
    RECONCILED = "RECONCILED"    # Matched with broker report
    DISCREPANCY = "DISCREPANCY"  # Mismatch with broker
    ERROR = "ERROR"              # Processing error


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class TradeConfirmation:
    """A confirmed trade record.

    Generated when a broker fill event is received and validated.
    This is the authoritative record of a trade execution.
    """

    confirmation_id: str
    order_id: str
    broker_order_id: str
    symbol: str
    side: str                    # BUY or SELL
    quantity: float
    price: float
    commission: float = 0.0
    currency: str = "USD"
    trade_date: str = ""         # YYYY-MM-DD
    settlement_date: str = ""    # T+2 for US stocks
    exchange: str = ""
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    broker_ref: str = ""         # Broker reference number
    notes: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def notional(self) -> float:
        """Total notional value of the trade."""
        return self.quantity * self.price

    @property
    def total_cost(self) -> float:
        """Total cost including commission."""
        return self.notional + self.commission

    def to_dict(self) -> Dict[str, Any]:
        """Serialize confirmation to dictionary."""
        return {
            "confirmation_id": self.confirmation_id,
            "order_id": self.order_id,
            "broker_order_id": self.broker_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "commission": self.commission,
            "currency": self.currency,
            "trade_date": self.trade_date,
            "settlement_date": self.settlement_date,
            "exchange": self.exchange,
            "status": self.status.value,
            "notional": self.notional,
            "total_cost": self.total_cost,
            "notes": self.notes,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Callback Types
# =============================================================================

# Callback signature for downstream systems
ConfirmationCallback = Callable[[TradeConfirmation], None]


# =============================================================================
# Trade Confirmation Engine
# =============================================================================


class TradeConfirmationEngine:
    """Processes broker fill events into confirmed trade records.

    Receives raw fill events from the broker gateway, generates
    confirmed TradeConfirmation records, and dispatches them
    to registered downstream systems.

    Downstream recipients:
        - Ledger: Records the trade for accounting
        - Position Manager: Updates portfolio positions
        - Risk Engine: Updates risk exposure

    Usage:
        engine = TradeConfirmationEngine()
        engine.register_handler("ledger", ledger_callback)
        engine.register_handler("position", position_callback)
        engine.register_handler("risk", risk_callback)

        confirmation = engine.confirm(
            order_id="ORD_001",
            broker_order_id="BRK_0001",
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            price=150.0,
            commission=2.50,
        )
    """

    def __init__(self) -> None:
        self._confirmations: Dict[str, TradeConfirmation] = {}
        self._handlers: Dict[str, ConfirmationCallback] = {}
        self._counter: int = 0

    def register_handler(self, name: str, callback: ConfirmationCallback) -> None:
        """Register a downstream handler for confirmed trades.

        Args:
            name: Handler name (e.g., "ledger", "position", "risk")
            callback: Function called with each confirmed trade
        """
        self._handlers[name] = callback

    def unregister_handler(self, name: str) -> None:
        """Remove a registered handler.

        Args:
            name: Handler name to remove
        """
        self._handlers.pop(name, None)

    @property
    def handlers(self) -> Dict[str, str]:
        """Get list of registered handler names."""
        return {name: handler.__name__ for name, handler in self._handlers.items()}

    def confirm(
        self,
        order_id: str,
        broker_order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        currency: str = "USD",
        exchange: str = "",
        broker_ref: str = "",
        notes: str = "",
    ) -> TradeConfirmation:
        """Confirm a trade execution.

        Generates a TradeConfirmation record and dispatches it
        to all registered downstream handlers.

        Args:
            order_id: OMS order ID
            broker_order_id: Broker's order ID
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Executed quantity
            price: Execution price
            commission: Broker commission
            currency: Trade currency
            exchange: Execution venue
            broker_ref: Broker reference number
            notes: Additional notes

        Returns:
            The created TradeConfirmation record
        """
        self._counter += 1
        now = datetime.utcnow()

        # Settlement: T+2 for US equities (simplified)
        from datetime import timedelta
        settlement = now + timedelta(days=2)

        confirmation = TradeConfirmation(
            confirmation_id=f"TC_{now.strftime('%Y%m%d')}_{self._counter:06d}",
            order_id=order_id,
            broker_order_id=broker_order_id,
            symbol=symbol.upper(),
            side=side.upper(),
            quantity=quantity,
            price=price,
            commission=commission,
            currency=currency,
            trade_date=now.strftime("%Y-%m-%d"),
            settlement_date=settlement.strftime("%Y-%m-%d"),
            exchange=exchange,
            broker_ref=broker_ref,
            notes=notes,
        )

        self._confirmations[confirmation.confirmation_id] = confirmation

        # Dispatch to downstream handlers
        self._dispatch(confirmation)

        return confirmation

    def _dispatch(self, confirmation: TradeConfirmation) -> None:
        """Dispatch a confirmed trade to all registered handlers.

        Args:
            confirmation: The confirmed trade to dispatch
        """
        for name, handler in self._handlers.items():
            try:
                handler(confirmation)
                confirmation.status = ConfirmationStatus.CONFIRMED
            except Exception:
                confirmation.status = ConfirmationStatus.ERROR
                confirmation.notes += f"; Handler '{name}' failed"

    def get_confirmation(self, confirmation_id: str) -> Optional[TradeConfirmation]:
        """Get a specific trade confirmation.

        Args:
            confirmation_id: Confirmation ID

        Returns:
            TradeConfirmation if found, None otherwise
        """
        return self._confirmations.get(confirmation_id)

    def get_confirmations_by_order(self, order_id: str) -> List[TradeConfirmation]:
        """Get all confirmations for a given order.

        Args:
            order_id: OMS order ID

        Returns:
            List of trade confirmations
        """
        return [
            c for c in self._confirmations.values()
            if c.order_id == order_id
        ]

    def get_all_confirmations(self) -> List[TradeConfirmation]:
        """Get all trade confirmations.

        Returns:
            List of all confirmations
        """
        return list(self._confirmations.values())

    def reconcile(
        self,
        confirmation_id: str,
        broker_record: Dict[str, Any],
    ) -> bool:
        """Reconcile a trade confirmation against broker records.

        Args:
            confirmation_id: Confirmation to reconcile
            broker_record: Broker's record of the trade

        Returns:
            True if records match, False if discrepancy found
        """
        confirmation = self._confirmations.get(confirmation_id)
        if confirmation is None:
            return False

        match = (
            abs(confirmation.quantity - broker_record.get("quantity", 0)) < 0.0001
            and abs(confirmation.price - broker_record.get("price", 0)) < 0.0001
        )

        if match:
            confirmation.status = ConfirmationStatus.RECONCILED
        else:
            confirmation.status = ConfirmationStatus.DISCREPANCY
            confirmation.notes += f"; Discrepancy with broker: {broker_record}"

        return match

    def get_pending_confirmations(self) -> List[TradeConfirmation]:
        """Get all pending (unprocessed) confirmations.

        Returns:
            List of pending confirmations
        """
        return [
            c for c in self._confirmations.values()
            if c.status == ConfirmationStatus.PENDING
        ]

    def get_discrepancies(self) -> List[TradeConfirmation]:
        """Get all confirmations with discrepancies.

        Returns:
            List of discrepancy confirmations
        """
        return [
            c for c in self._confirmations.values()
            if c.status == ConfirmationStatus.DISCREPANCY
        ]
