"""Quote Normalizer — converts heterogeneous source formats into
the canonical (symbol, exchange) pair.

Different market data sources use different conventions:

    Source A:  "159852.SZ"   (suffixed)
    Source B:  "159852"      (bare)
    Source C:  "SZ159852"    (prefixed)
    Exchange:  "SH" / "SSE" / "Shanghai" / "上交所" ...

Downstream business code must never handle these differences.
Every raw tick passes through QuoteNormalizer first, producing a
plain 6-digit symbol + Exchange enum.
"""
from __future__ import annotations

from typing import Optional

from .domain.instrument import Exchange, Instrument
from .exceptions.market_data_error import InvalidSymbolError

# Accepted spellings for each exchange — normalized to SSE / SZSE.
_EXCHANGE_ALIASES: dict[str, Exchange] = {
    # SSE
    "SSE": Exchange.SSE,
    "SH": Exchange.SSE,
    "SHA": Exchange.SSE,
    "SHANGHAI": Exchange.SSE,
    "上交所": Exchange.SSE,
    "上海": Exchange.SSE,
    # SZSE
    "SZSE": Exchange.SZSE,
    "SZ": Exchange.SZSE,
    "SHE": Exchange.SZSE,
    "SZN": Exchange.SZSE,
    "SHENZHEN": Exchange.SZSE,
    "深交所": Exchange.SZSE,
    "深圳": Exchange.SZSE,
}

# Code-prefix → exchange (mirrors Instrument.infer_exchange logic
# but also used to strip explicit suffix/prefix markers).
_SUFFIX_TO_EXCHANGE: dict[str, Exchange] = {
    "SZ": Exchange.SZSE,
    "SH": Exchange.SSE,
}


def normalize_exchange(raw: object) -> Exchange:
    """Normalize any accepted exchange spelling to the SSE/SZSE enum."""
    if isinstance(raw, Exchange):
        return raw
    if raw is None:
        raise InvalidSymbolError("exchange is None")
    key = str(raw).strip().upper()
    # Chinese aliases are not uppercase-affected
    if key in _EXCHANGE_ALIASES:
        return _EXCHANGE_ALIASES[key]
    zh = str(raw).strip()
    if zh in _EXCHANGE_ALIASES:
        return _EXCHANGE_ALIASES[zh]
    raise InvalidSymbolError(f"unknown exchange: {raw!r}")


def normalize_symbol(raw: object) -> tuple[str, Exchange]:
    """Normalize a raw ticker string to (symbol, exchange).

    Accepted formats::

        "159852"       → ("159852", SZSE)   # inferred from prefix
        "159852.SZ"    → ("159852", SZSE)
        "159852.SZSE"  → ("159852", SZSE)
        "SZ159852"     → ("159852", SZSE)
        "SH513050"     → ("513050", SSE)

    Raises InvalidSymbolError for anything unparseable.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidSymbolError("symbol is empty or not a string")
    s = raw.strip().upper()

    exchange: Optional[Exchange] = None

    # Form 1: "159852.SZ" / "159852.SZSE" / "513050.SH"
    if "." in s:
        code_part, _, suffix = s.partition(".")
        symbol = code_part.strip()
        try:
            exchange = normalize_exchange(suffix)
        except InvalidSymbolError:
            raise InvalidSymbolError(
                f"cannot parse symbol {raw!r}: bad suffix {suffix!r}"
            )
    # Form 2: "SZ159852" / "SH513050" (2-letter prefix)
    elif len(s) == 8 and not s.isdigit() and s[:2].isalpha() and s[2:].isdigit():
        marker = s[:2]
        if marker in _SUFFIX_TO_EXCHANGE:
            exchange = _SUFFIX_TO_EXCHANGE[marker]
            symbol = s[2:]
        else:
            raise InvalidSymbolError(
                f"cannot parse symbol {raw!r}: unknown prefix {marker!r}"
            )
    # Form 3: bare 6-digit code
    else:
        symbol = s

    # Validate the code itself
    if not symbol.isdigit() or len(symbol) != 6:
        raise InvalidSymbolError(
            f"invalid A-share fund code: {raw!r} (expected 6 digits)"
        )

    # Infer exchange when not explicitly provided
    if exchange is None:
        try:
            exchange = Instrument.infer_exchange(symbol)
        except ValueError as exc:
            raise InvalidSymbolError(str(exc))

    return symbol, exchange


class QuoteNormalizer:
    """Stateless normalizer reused by every adapter.

    Usage inside an adapter::

        symbol, exchange = QuoteNormalizer().normalize(raw["code"])
    """

    def normalize(self, raw_symbol: object, raw_exchange: object = None) -> tuple[str, Exchange]:
        """Normalize (symbol, exchange) — explicit exchange wins,
        otherwise inferred from the symbol format."""
        symbol, inferred = normalize_symbol(raw_symbol)
        if raw_exchange is None:
            return symbol, inferred
        explicit = normalize_exchange(raw_exchange)
        return symbol, explicit

    def normalize_all(
        self, raw_symbols: list[object]
    ) -> list[tuple[str, Exchange]]:
        return [self.normalize(s) for s in raw_symbols]


__all__ = [
    "QuoteNormalizer",
    "normalize_symbol",
    "normalize_exchange",
]
