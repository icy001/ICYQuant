"""Numeric coercion helpers for the Account domain.

Broker payloads are untrusted text: ``"1.25"``, ``10000``, ``None``,
``""`` all appear in the wild.  The domain never lets a *parse failure*
silently become ``0`` — callers must say which they want:

* :func:`to_decimal`          — parse or return the given default (None).
* :func:`to_decimal_or_zero`  — parse or ``0`` (for genuinely optional
  counters, never for a price).
* :func:`money` / :func:`quantity` — parse **and** quantise.

Money keeps 4 dp (A-share tick is 3 dp; 4 dp leaves room for FX /
fees), quantity keeps 6 dp.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Optional

MONEY_QUANT = Decimal("0.0001")
QUANTITY_QUANT = Decimal("0.000001")


def to_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Parse ``value`` to :class:`Decimal`, or return ``default``.

    ``bool`` is intentionally *not* accepted as a number — a payload
    carrying ``True`` for a price is malformed, not ``1``.
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace(",", "")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return default


def to_decimal_or_zero(value: Any) -> Decimal:
    """Parse ``value`` or fall back to ``0`` (optional counters only)."""
    parsed = to_decimal(value)
    return parsed if parsed is not None else Decimal("0")


def money(value: Any) -> Decimal:
    """Parse + quantise a monetary amount to 4 dp."""
    return to_decimal_or_zero(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantity(value: Any) -> Decimal:
    """Parse + quantise a share quantity to 6 dp."""
    return to_decimal_or_zero(value).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def money_or_none(value: Any) -> Optional[Decimal]:
    """Parse + quantise, preserving "absent" as ``None``."""
    parsed = to_decimal(value)
    if parsed is None:
        return None
    return parsed.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def as_float(value: Optional[Decimal]) -> Optional[float]:
    """Wire helper — ``Decimal`` → JSON number, ``None`` stays ``None``."""
    return None if value is None else float(value)


__all__ = [
    "MONEY_QUANT",
    "QUANTITY_QUANT",
    "to_decimal",
    "to_decimal_or_zero",
    "money",
    "money_or_none",
    "quantity",
    "as_float",
]
