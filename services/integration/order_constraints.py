"""OrderConstraints — unified constraints applied at the admission boundary.

Collects and normalizes all upstream constraints (Risk, Governance, Authority,
Approval) into a single effective set that governs what the Order can look like
when it enters OMS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class OrderConstraints:
    """Effective constraints derived from all upstream control domains.

    These are applied at the admission boundary to ensure the final Order
    does not violate any domain's rules.
    """

    max_quantity: Optional[float] = None
    max_notional: Optional[float] = None
    max_price_deviation: Optional[float] = None
    max_leverage: Optional[float] = None
    max_exposure: Optional[float] = None

    allowed_symbols: Optional[Set[str]] = None
    allowed_sides: Optional[Set[str]] = None
    allowed_venues: Optional[Set[str]] = None
    allowed_order_types: Optional[Set[str]] = None

    min_quantity: Optional[float] = None
    quantity_step: Optional[float] = None
    lot_size: Optional[float] = None
    tick_size: Optional[float] = None

    expiry: Optional[float] = None

    sources: Dict[str, List[str]] = field(default_factory=dict)

    def with_max_quantity(self, value: float, source: str = "") -> "OrderConstraints":
        if self.max_quantity is None or value < self.max_quantity:
            self.max_quantity = value
        if source:
            self.sources.setdefault("max_quantity", []).append(source)
        return self

    def with_max_notional(self, value: float, source: str = "") -> "OrderConstraints":
        if self.max_notional is None or value < self.max_notional:
            self.max_notional = value
        if source:
            self.sources.setdefault("max_notional", []).append(source)
        return self

    def with_max_leverage(self, value: float, source: str = "") -> "OrderConstraints":
        if self.max_leverage is None or value < self.max_leverage:
            self.max_leverage = value
        if source:
            self.sources.setdefault("max_leverage", []).append(source)
        return self

    def with_max_exposure(self, value: float, source: str = "") -> "OrderConstraints":
        if self.max_exposure is None or value < self.max_exposure:
            self.max_exposure = value
        if source:
            self.sources.setdefault("max_exposure", []).append(source)
        return self

    def with_allowed_symbols(self, symbols: Set[str], source: str = "") -> "OrderConstraints":
        if self.allowed_symbols is None:
            self.allowed_symbols = set(symbols)
        else:
            self.allowed_symbols &= set(symbols)
        if source:
            self.sources.setdefault("allowed_symbols", []).append(source)
        return self

    def with_allowed_sides(self, sides: Set[str], source: str = "") -> "OrderConstraints":
        if self.allowed_sides is None:
            self.allowed_sides = set(sides)
        else:
            self.allowed_sides &= set(sides)
        if source:
            self.sources.setdefault("allowed_sides", []).append(source)
        return self

    def with_allowed_venues(self, venues: Set[str], source: str = "") -> "OrderConstraints":
        if self.allowed_venues is None:
            self.allowed_venues = set(venues)
        else:
            self.allowed_venues &= set(venues)
        if source:
            self.sources.setdefault("allowed_venues", []).append(source)
        return self

    def with_allowed_order_types(self, types: Set[str], source: str = "") -> "OrderConstraints":
        if self.allowed_order_types is None:
            self.allowed_order_types = set(types)
        else:
            self.allowed_order_types &= set(types)
        if source:
            self.sources.setdefault("allowed_order_types", []).append(source)
        return self

    def with_min_quantity(self, value: float, source: str = "") -> "OrderConstraints":
        if self.min_quantity is None or value > self.min_quantity:
            self.min_quantity = value
        if source:
            self.sources.setdefault("min_quantity", []).append(source)
        return self

    def with_lot_size(self, value: float, source: str = "") -> "OrderConstraints":
        self.lot_size = value
        if source:
            self.sources.setdefault("lot_size", []).append(source)
        return self

    def with_tick_size(self, value: float, source: str = "") -> "OrderConstraints":
        self.tick_size = value
        if source:
            self.sources.setdefault("tick_size", []).append(source)
        return self

    def with_expiry(self, value: float, source: str = "") -> "OrderConstraints":
        if self.expiry is None or value < self.expiry:
            self.expiry = value
        if source:
            self.sources.setdefault("expiry", []).append(source)
        return self

    def check_quantity(self, quantity: float) -> bool:
        """Check if a quantity satisfies all applicable constraints."""
        if self.max_quantity is not None and quantity > self.max_quantity:
            return False
        if self.min_quantity is not None and quantity < self.min_quantity:
            return False
        return True

    def check_notional(self, notional: float) -> bool:
        """Check if a notional value satisfies max_notional."""
        if self.max_notional is not None and notional > self.max_notional:
            return False
        return True

    def check_symbol(self, symbol: str) -> bool:
        """Check if a symbol is allowed."""
        if self.allowed_symbols is not None and symbol not in self.allowed_symbols:
            return False
        return True

    def check_side(self, side: str) -> bool:
        """Check if a side is allowed."""
        if self.allowed_sides is not None and side not in self.allowed_sides:
            return False
        return True

    def check_order_type(self, order_type: str) -> bool:
        """Check if an order type is allowed."""
        if self.allowed_order_types is not None and order_type not in self.allowed_order_types:
            return False
        return True

    def check_venue(self, venue: str) -> bool:
        """Check if a venue is allowed."""
        if self.allowed_venues is not None and venue not in self.allowed_venues:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if constraints have expired."""
        if self.expiry is None:
            return False
        import time
        return time.time() > self.expiry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_quantity": self.max_quantity,
            "max_notional": self.max_notional,
            "max_price_deviation": self.max_price_deviation,
            "max_leverage": self.max_leverage,
            "max_exposure": self.max_exposure,
            "allowed_symbols": list(self.allowed_symbols) if self.allowed_symbols else None,
            "allowed_sides": list(self.allowed_sides) if self.allowed_sides else None,
            "allowed_venues": list(self.allowed_venues) if self.allowed_venues else None,
            "allowed_order_types": list(self.allowed_order_types) if self.allowed_order_types else None,
            "min_quantity": self.min_quantity,
            "quantity_step": self.quantity_step,
            "lot_size": self.lot_size,
            "tick_size": self.tick_size,
            "expiry": self.expiry,
            "sources": self.sources,
        }

    def __repr__(self) -> str:
        return (
            f"OrderConstraints(max_quantity={self.max_quantity}, "
            f"max_notional={self.max_notional}, "
            f"max_exposure={self.max_exposure})"
        )
