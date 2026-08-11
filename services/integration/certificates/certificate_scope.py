"""CertificateScope — defines what a Pre-Trade Control Certificate authorizes.

Scope binds:
- subject (account, portfolio, strategy)
- instrument (symbol, venue)
- action (side, order_type)
- limits (max_quantity, max_notional, max_leverage)
- lifespan (issued_at, expires_at)

A certificate scope violation occurs when the actual order exceeds
any dimension of the scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ScopeGranularity(Enum):
    """Granularity level of certificate scope."""
    ORDER = auto()      # single order
    SYMBOL = auto()     # single symbol, multiple orders
    ACCOUNT = auto()    # account-wide


class ConsumptionMode(Enum):
    """How certificate limits are consumed across uses."""
    ONE_TIME = auto()       # single use only
    QUANTITY_CAPPED = auto()  # total quantity across uses
    NOTIONAL_CAPPED = auto()  # total notional across uses
    UNLIMITED = auto()       # reusable without cap (rare)


@dataclass
class CertificateScope:
    """Defines the exact boundaries within which a certificate is valid.

    Every dimension must be satisfied for the certificate to pass verification.
    """

    scope_id: str = field(
        default_factory=lambda: f"SCOPE-{__import__('uuid').uuid4().hex[:12].upper()}"
    )

    # ── Subject binding ───────────────────────────────────────
    account_id: str = ""
    portfolio_id: str = ""
    strategy_id: str = ""

    # ── Instrument binding ────────────────────────────────────
    symbol: str = ""
    venue: str = ""

    # ── Action binding ────────────────────────────────────────
    side: str = ""
    order_type: str = ""

    # ── Limit binding ─────────────────────────────────────────
    max_quantity: Optional[float] = None
    max_notional: Optional[float] = None
    max_leverage: Optional[float] = None
    allowed_order_types: List[str] = field(default_factory=list)

    # ── Consumption tracking ───────────────────────────────────
    granularity: ScopeGranularity = ScopeGranularity.ORDER
    consumption_mode: ConsumptionMode = ConsumptionMode.ONE_TIME

    quantity_consumed: float = 0.0
    notional_consumed: float = 0.0

    # ── Lifespan ──────────────────────────────────────────────
    issued_at: float = field(default_factory=lambda: __import__("time").time())
    expires_at: Optional[float] = None

    def is_active(self, now: Optional[float] = None) -> bool:
        """Check whether the scope is still within its validity window."""
        if now is None:
            now = __import__("time").time()
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    @property
    def quantity_remaining(self) -> Optional[float]:
        """Remaining quantity, or None if no max_quantity is set."""
        if self.max_quantity is None:
            return None
        return max(0.0, self.max_quantity - self.quantity_consumed)

    @property
    def notional_remaining(self) -> Optional[float]:
        """Remaining notional, or None if no max_notional is set."""
        if self.max_notional is None:
            return None
        return max(0.0, self.max_notional - self.notional_consumed)

    def check_symbol(self, symbol: str) -> bool:
        """Verify symbol matches scope."""
        if not self.symbol:
            return True
        return symbol.upper() == self.symbol.upper()

    def check_side(self, side: str) -> bool:
        """Verify side matches scope."""
        if not self.side:
            return True
        return side.upper() == self.side.upper()

    def check_venue(self, venue: str) -> bool:
        """Verify venue matches scope."""
        if not self.venue:
            return True
        return venue.upper() == self.venue.upper()

    def check_quantity(self, quantity: float) -> bool:
        """Check whether *quantity* is within scope."""
        if self.max_quantity is None:
            return True
        remaining = self.quantity_remaining
        if remaining is None:
            return True
        return quantity <= remaining

    def check_notional(self, notional: float) -> bool:
        """Check whether *notional* is within scope."""
        if self.max_notional is None:
            return True
        remaining = self.notional_remaining
        if remaining is None:
            return True
        return notional <= remaining

    def consume_quantity(self, quantity: float) -> None:
        """Record quantity consumption. Raises ValueError if exceeded."""
        remaining = self.quantity_remaining
        if remaining is not None and quantity > remaining:
            raise ValueError(
                f"Quantity {quantity} exceeds remaining {remaining}"
            )
        self.quantity_consumed += quantity

    def consume_notional(self, notional: float) -> None:
        """Record notional consumption. Raises ValueError if exceeded."""
        remaining = self.notional_remaining
        if remaining is not None and notional > remaining:
            raise ValueError(
                f"Notional {notional} exceeds remaining {remaining}"
            )
        self.notional_consumed += notional

    @classmethod
    def for_order(cls, account_id: str, symbol: str, side: str,
                  max_quantity: float, max_notional: Optional[float] = None,
                  venue: str = "", strategy_id: str = "",
                  portfolio_id: str = "") -> "CertificateScope":
        """Create a single-order scope."""
        return cls(
            account_id=account_id,
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            venue=venue,
            max_quantity=max_quantity,
            max_notional=max_notional,
            granularity=ScopeGranularity.ORDER,
            consumption_mode=ConsumptionMode.ONE_TIME,
        )

    @classmethod
    def for_symbol(cls, account_id: str, symbol: str, side: str,
                   max_quantity: float, venue: str = "",
                   strategy_id: str = "") -> "CertificateScope":
        """Create a symbol-level reusable scope."""
        return cls(
            account_id=account_id,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            venue=venue,
            max_quantity=max_quantity,
            granularity=ScopeGranularity.SYMBOL,
            consumption_mode=ConsumptionMode.QUANTITY_CAPPED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "account_id": self.account_id,
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "venue": self.venue,
            "side": self.side,
            "order_type": self.order_type,
            "max_quantity": self.max_quantity,
            "max_notional": self.max_notional,
            "max_leverage": self.max_leverage,
            "allowed_order_types": self.allowed_order_types,
            "granularity": self.granularity.name,
            "consumption_mode": self.consumption_mode.name,
            "quantity_consumed": self.quantity_consumed,
            "notional_consumed": self.notional_consumed,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateScope(id={self.scope_id[:12]}..., "
            f"symbol={self.symbol}, side={self.side}, "
            f"max_qty={self.max_quantity}, "
            f"consumed={self.quantity_consumed}/{self.max_quantity})"
        )
