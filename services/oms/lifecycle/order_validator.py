"""Order Validator — Pre-submission order validation.

Validates orders before they enter the lifecycle engine. Checks
symbol validity, quantity constraints, price limits, and business
rules compliance.

Validation pipeline:
    Symbol Check → Quantity Check → Price Check → Business Rules → Result
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.order.models import Order, OrderSide, OrderStatus, OrderType, TimeInForce

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """Validation outcome."""
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class ValidationResult:
    """Result of order validation."""
    order_id: str
    status: ValidationStatus = ValidationStatus.PENDING
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks_performed: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Whether validation passed."""
        return self.status == ValidationStatus.PASSED

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "status": self.status.value,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks_performed": self.checks_performed,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class OrderValidator:
    """Validates orders before lifecycle processing.

    Performs comprehensive validation including:
    - Symbol format and existence checks
    - Quantity minimum/maximum constraints
    - Price sanity checks
    - Order type specific rules
    - Time-in-force validation
    - Business rule compliance

    Usage::

        validator = OrderValidator()
        result = await validator.validate(order)
        if result.is_valid:
            await engine.process(order)
    """

    # Configurable limits
    MIN_QUANTITY: float = 1.0
    MAX_QUANTITY: float = 100_000_000.0
    MIN_PRICE: float = 0.01
    MAX_PRICE: float = 10_000_000.0
    MAX_SYMBOL_LENGTH: int = 20
    MIN_SYMBOL_LENGTH: int = 1

    def __init__(self) -> None:
        self._symbol_cache: set[str] = set()

    async def validate(self, order: Order) -> ValidationResult:
        """Validate an order before lifecycle processing.

        Args:
            order: Order to validate

        Returns:
            ValidationResult with pass/fail status and details
        """
        result = ValidationResult(order_id=order.order_id)

        await self._validate_symbol(order, result)
        await self._validate_side(order, result)
        await self._validate_quantity(order, result)
        await self._validate_price(order, result)
        await self._validate_order_type(order, result)
        await self._validate_time_in_force(order, result)
        await self._validate_status(order, result)
        await self._validate_business_rules(order, result)

        if result.errors:
            result.status = ValidationStatus.FAILED
            logger.warning(f"Order validation failed: {order.order_id}, errors={result.errors}")
        else:
            result.status = ValidationStatus.PASSED
            logger.debug(f"Order validation passed: {order.order_id}")

        return result

    async def _validate_symbol(self, order: Order, result: ValidationResult) -> None:
        """Validate trading symbol."""
        result.checks_performed.append("symbol_check")
        if not order.symbol or not order.symbol.strip():
            result.errors.append("Symbol is required")
            return
        symbol = order.symbol.strip().upper()
        if len(symbol) < self.MIN_SYMBOL_LENGTH or len(symbol) > self.MAX_SYMBOL_LENGTH:
            result.errors.append(
                f"Symbol length must be between {self.MIN_SYMBOL_LENGTH} "
                f"and {self.MAX_SYMBOL_LENGTH}, got {len(symbol)}"
            )
        if not symbol.isalnum() and not all(c.isalnum() or c in ".-_" for c in symbol):
            result.warnings.append(f"Symbol '{symbol}' contains unusual characters")

    async def _validate_side(self, order: Order, result: ValidationResult) -> None:
        """Validate order side."""
        result.checks_performed.append("side_check")
        if order.side not in (OrderSide.BUY, OrderSide.SELL):
            result.errors.append(f"Invalid order side: {order.side}")

    async def _validate_quantity(self, order: Order, result: ValidationResult) -> None:
        """Validate order quantity."""
        result.checks_performed.append("quantity_check")
        if order.quantity <= 0:
            result.errors.append(f"Quantity must be positive, got {order.quantity}")
            return
        if order.quantity < self.MIN_QUANTITY:
            result.errors.append(f"Quantity below minimum {self.MIN_QUANTITY}: {order.quantity}")
        if order.quantity > self.MAX_QUANTITY:
            result.errors.append(f"Quantity exceeds maximum {self.MAX_QUANTITY}: {order.quantity}")

    async def _validate_price(self, order: Order, result: ValidationResult) -> None:
        """Validate order price."""
        result.checks_performed.append("price_check")
        if order.order_type == OrderType.MARKET:
            return  # Market orders don't need price validation
        if order.price <= 0:
            result.errors.append(f"Price must be positive for {order.order_type.value} orders")
            return
        if order.price < self.MIN_PRICE:
            result.errors.append(f"Price below minimum {self.MIN_PRICE}: {order.price}")
        if order.price > self.MAX_PRICE:
            result.errors.append(f"Price exceeds maximum {self.MAX_PRICE}: {order.price}")

    async def _validate_order_type(self, order: Order, result: ValidationResult) -> None:
        """Validate order type."""
        result.checks_performed.append("order_type_check")
        valid_types = {OrderType.MARKET, OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT}
        if order.order_type not in valid_types:
            result.errors.append(f"Invalid order type: {order.order_type}")

    async def _validate_time_in_force(self, order: Order, result: ValidationResult) -> None:
        """Validate time-in-force."""
        result.checks_performed.append("tif_check")
        valid_tif = {TimeInForce.DAY, TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK, TimeInForce.GTD}
        if order.time_in_force not in valid_tif:
            result.errors.append(f"Invalid time-in-force: {order.time_in_force}")
        if order.time_in_force == TimeInForce.FOK and order.order_type != OrderType.LIMIT:
            result.warnings.append("FOK is typically used with LIMIT orders")
        if order.time_in_force == TimeInForce.IOC and order.order_type == OrderType.MARKET:
            result.warnings.append("IOC with MARKET order may behave like a market order")

    async def _validate_status(self, order: Order, result: ValidationResult) -> None:
        """Validate order is in correct state for lifecycle processing."""
        result.checks_performed.append("status_check")
        if order.status != OrderStatus.CREATED:
            result.errors.append(
                f"Order must be in CREATED state for lifecycle processing, "
                f"current status: {order.status.value}"
            )
        if order.is_terminal:
            result.errors.append(f"Cannot process terminal order: {order.status.value}")

    async def _validate_business_rules(self, order: Order, result: ValidationResult) -> None:
        """Validate business rules."""
        result.checks_performed.append("business_rules")
        # Strategy ID validation
        if not order.strategy_id:
            result.warnings.append("No strategy_id assigned to order")
        # Notional value sanity check
        notional = order.notional_value
        if notional > 0 and notional > 1_000_000_000:
            result.warnings.append(f"Large notional value: ${notional:,.2f}")
        # Source validation
        if order.source:
            result.details["source"] = order.source.value

    def register_symbol(self, symbol: str) -> None:
        """Register a known valid symbol.

        Args:
            symbol: Trading symbol to register
        """
        self._symbol_cache.add(symbol.upper())

    def register_symbols(self, symbols: list[str]) -> None:
        """Register multiple known valid symbols.

        Args:
            symbols: List of trading symbols to register
        """
        for s in symbols:
            self._symbol_cache.add(s.upper())

    def is_known_symbol(self, symbol: str) -> bool:
        """Check if a symbol is registered.

        Args:
            symbol: Trading symbol to check

        Returns:
            True if the symbol is known
        """
        return symbol.upper() in self._symbol_cache
