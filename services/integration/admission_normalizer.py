"""AdmissionNormalizer — normalizes order fields to canonical representations.

Ensures consistent formatting of sides, quantities, prices (tick size),
and other fields before the order enters OMS. Different modules should
not each implement their own normalization logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from .order_intent import OrderIntent, Side, OrderType
from .order_constraints import OrderConstraints


class PriceRoundingPolicy(Enum):
    """Policy for rounding prices to tick size."""
    NEAREST = auto()
    UP = auto()
    DOWN = auto()

    @property
    def label(self) -> str:
        _labels = {
            PriceRoundingPolicy.NEAREST: "NEAREST",
            PriceRoundingPolicy.UP: "UP",
            PriceRoundingPolicy.DOWN: "DOWN",
        }
        return _labels.get(self, "UNKNOWN")


class QuantityNormalizationPolicy(Enum):
    """Policy for handling non-standard quantities."""
    REJECT = auto()
    ROUND_DOWN = auto()
    ROUND_NEAREST = auto()

    @property
    def label(self) -> str:
        _labels = {
            QuantityNormalizationPolicy.REJECT: "REJECT",
            QuantityNormalizationPolicy.ROUND_DOWN: "ROUND_DOWN",
            QuantityNormalizationPolicy.ROUND_NEAREST: "ROUND_NEAREST",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class NormalizationResult:
    """Result of normalization."""
    normalized: bool = True
    intent: Optional[OrderIntent] = None
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.normalized = False


@dataclass
class AdmissionNormalizer:
    """Normalizes order fields to canonical representations.

    Applies constraint-driven normalization for price (tick size),
    quantity (lot size, steps), and field formatting (side, venue).
    """

    price_rounding: PriceRoundingPolicy = PriceRoundingPolicy.NEAREST
    quantity_policy: QuantityNormalizationPolicy = QuantityNormalizationPolicy.ROUND_DOWN
    default_tick_size: float = 0.01
    default_lot_size: float = 1.0

    def normalize(
        self, intent: OrderIntent, constraints: Optional[OrderConstraints] = None
    ) -> NormalizationResult:
        """Normalize an OrderIntent according to constraints."""
        result = NormalizationResult(intent=intent)

        # 1. Normalize side
        self._normalize_side(intent)

        # 2. Normalize symbol
        self._normalize_symbol(intent)

        # 3. Normalize venue
        self._normalize_venue(intent)

        # 4. Normalize price (tick size)
        if intent.limit_price is not None:
            self._normalize_price(intent, constraints, result)

        # 5. Normalize quantity (lot size / step)
        self._normalize_quantity(intent, constraints, result)

        return result

    def _normalize_side(self, intent: OrderIntent) -> None:
        """Canonicalize side: BUY, buy, Buy → BUY."""
        # Side is already an enum, so normalization is inherent
        pass

    def _normalize_symbol(self, intent: OrderIntent) -> None:
        """Uppercase symbol."""
        if intent.symbol:
            intent.symbol = intent.symbol.strip().upper()

    def _normalize_venue(self, intent: OrderIntent) -> None:
        """Uppercase venue."""
        if intent.venue:
            intent.venue = intent.venue.strip().upper()

    def _normalize_price(
        self,
        intent: OrderIntent,
        constraints: Optional[OrderConstraints],
        result: NormalizationResult,
    ) -> None:
        """Round price to tick size."""
        tick_size = self.default_tick_size
        if constraints and constraints.tick_size is not None:
            tick_size = constraints.tick_size

        if tick_size <= 0:
            return

        price = intent.limit_price or 0.0
        ticks = price / tick_size

        if self.price_rounding == PriceRoundingPolicy.NEAREST:
            rounded = round(ticks) * tick_size
        elif self.price_rounding == PriceRoundingPolicy.UP:
            rounded = math.ceil(ticks) * tick_size
        else:  # DOWN
            rounded = math.floor(ticks) * tick_size

        if abs(rounded - price) > 1e-9:
            result.add_warning(
                f"Price normalized: {price} → {rounded} (tick_size={tick_size})"
            )

        intent.limit_price = round(rounded, 10)  # Avoid floating point artifacts

    def _normalize_quantity(
        self,
        intent: OrderIntent,
        constraints: Optional[OrderConstraints],
        result: NormalizationResult,
    ) -> None:
        """Normalize quantity to lot size / step."""
        step = self.default_lot_size
        if constraints:
            if constraints.lot_size is not None:
                step = constraints.lot_size
            elif constraints.quantity_step is not None:
                step = constraints.quantity_step

        if step <= 0:
            return

        qty = intent.quantity
        remainder = qty % step

        if remainder == 0:
            return

        if self.quantity_policy == QuantityNormalizationPolicy.REJECT:
            result.add_error(
                f"Quantity {qty} is not a multiple of step {step}"
            )
            return

        if self.quantity_policy == QuantityNormalizationPolicy.ROUND_DOWN:
            normalized = math.floor(qty / step) * step
        else:  # ROUND_NEAREST
            normalized = round(qty / step) * step

        if normalized <= 0:
            result.add_error(
                f"Quantity {qty} normalized to {normalized} (step={step}), "
                f"result is non-positive"
            )
            return

        if abs(normalized - qty) > 1e-9:
            result.add_warning(
                f"Quantity normalized: {qty} → {normalized} (step={step})"
            )

        intent.quantity = normalized

    def __repr__(self) -> str:
        return (
            f"AdmissionNormalizer(price={self.price_rounding.label}, "
            f"qty={self.quantity_policy.label})"
        )
