"""
Currency Normalizer — normalizes currency codes and handles FX
conversion for multi-currency market data.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CurrencyMapping:
    """Mapping from raw currency string to ISO 4217."""

    iso_code: str = ""             # ISO 4217 (e.g., "USD")
    numeric_code: str = ""         # ISO 4217 numeric
    name: str = ""                 # Full name (e.g., "United States Dollar")
    symbol: str = ""               # Symbol (e.g., "$")
    precision: int = 2             # Decimal precision
    is_crypto: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CurrencyPair:
    """A currency pair definition."""
    base_currency: str = ""
    quote_currency: str = ""
    symbol: str = ""
    pip_size: float = 0.0001
    lot_size: float = 100000.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def pair(self) -> str:
        return f"{self.base_currency}{self.quote_currency}"


@dataclass
class FxRate:
    """An FX conversion rate."""

    base_currency: str = ""
    quote_currency: str = ""
    rate: Decimal = Decimal("1.0")
    timestamp_ns: int = 0
    source: str = ""
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")


class CurrencyNormalizer:
    """
    Normalizes currency codes and handles multi-currency conversions.

    Maps common aliases to ISO 4217:
        "US Dollar" → USD
        "RMB" / "CNH" → CNY
        "Sterling" → GBP
        "BTC" → BTC (crypto)
    """

    # Common currency aliases → ISO 4217
    CURRENCY_ALIASES: dict[str, str] = {
        "US DOLLAR": "USD",
        "USD": "USD",
        "US DOLLARS": "USD",
        "DOLLAR": "USD",
        "EURO": "EUR",
        "EUR": "EUR",
        "STERLING": "GBP",
        "POUND": "GBP",
        "GBP": "GBP",
        "YEN": "JPY",
        "JAPANESE YEN": "JPY",
        "JPY": "JPY",
        "RMB": "CNY",
        "CNY": "CNY",
        "CNH": "CNY",
        "RENMINBI": "CNY",
        "YUAN": "CNY",
        "HKD": "HKD",
        "HONG KONG DOLLAR": "HKD",
        "SGD": "SGD",
        "SINGAPORE DOLLAR": "SGD",
        "AUD": "AUD",
        "AUSTRALIAN DOLLAR": "AUD",
        "CAD": "CAD",
        "CANADIAN DOLLAR": "CAD",
        "CHF": "CHF",
        "SWISS FRANC": "CHF",
        "BTC": "BTC",
        "BITCOIN": "BTC",
        "ETH": "ETH",
        "ETHEREUM": "ETH",
        "USDT": "USDT",
        "TETHER": "USDT",
        "USDC": "USDC",
    }

    # ISO 4217 currency definitions
    CURRENCY_DEFS: dict[str, CurrencyMapping] = {
        "USD": CurrencyMapping(iso_code="USD", numeric_code="840", name="United States Dollar", symbol="$", precision=2),
        "EUR": CurrencyMapping(iso_code="EUR", numeric_code="978", name="Euro", symbol="€", precision=2),
        "GBP": CurrencyMapping(iso_code="GBP", numeric_code="826", name="Pound Sterling", symbol="£", precision=2),
        "JPY": CurrencyMapping(iso_code="JPY", numeric_code="392", name="Japanese Yen", symbol="¥", precision=0),
        "CNY": CurrencyMapping(iso_code="CNY", numeric_code="156", name="Chinese Yuan", symbol="¥", precision=2),
        "HKD": CurrencyMapping(iso_code="HKD", numeric_code="344", name="Hong Kong Dollar", symbol="HK$", precision=2),
        "SGD": CurrencyMapping(iso_code="SGD", numeric_code="702", name="Singapore Dollar", symbol="S$", precision=2),
        "AUD": CurrencyMapping(iso_code="AUD", numeric_code="036", name="Australian Dollar", symbol="A$", precision=2),
        "CAD": CurrencyMapping(iso_code="CAD", numeric_code="124", name="Canadian Dollar", symbol="C$", precision=2),
        "CHF": CurrencyMapping(iso_code="CHF", numeric_code="756", name="Swiss Franc", symbol="Fr", precision=2),
        "BTC": CurrencyMapping(iso_code="BTC", numeric_code="", name="Bitcoin", symbol="₿", precision=8, is_crypto=True),
        "ETH": CurrencyMapping(iso_code="ETH", numeric_code="", name="Ethereum", symbol="Ξ", precision=18, is_crypto=True),
        "USDT": CurrencyMapping(iso_code="USDT", numeric_code="", name="Tether", symbol="₮", precision=6, is_crypto=True),
        "USDC": CurrencyMapping(iso_code="USDC", numeric_code="", name="USD Coin", symbol="", precision=6, is_crypto=True),
    }

    def __init__(self) -> None:
        self._fx_rates: dict[str, FxRate] = {}

    async def normalize(self, raw_currency: str) -> str:
        """Normalize any currency string to ISO 4217 code."""
        if not raw_currency:
            return "USD"

        key = raw_currency.strip().upper()

        # Direct ISO match
        if key in self.CURRENCY_DEFS:
            return key

        # Alias match
        if key in self.CURRENCY_ALIASES:
            return self.CURRENCY_ALIASES[key]

        logger.warning("Unknown currency: %s, defaulting to USD", raw_currency)
        return "USD"

    async def get_definition(self, iso_code: str) -> Optional[CurrencyMapping]:
        """Get the full currency definition."""
        return self.CURRENCY_DEFS.get(iso_code.upper())

    async def convert(
        self, amount: Decimal, from_currency: str, to_currency: str
    ) -> Optional[Decimal]:
        """Convert an amount between currencies using cached FX rates."""
        from_ccy = await self.normalize(from_currency)
        to_ccy = await self.normalize(to_currency)

        if from_ccy == to_ccy:
            return amount

        # Direct rate
        pair = f"{from_ccy}{to_ccy}"
        rate = self._fx_rates.get(pair)
        if rate:
            return amount * rate.rate

        # Inverse rate
        inv_pair = f"{to_ccy}{from_ccy}"
        rate = self._fx_rates.get(inv_pair)
        if rate and rate.rate != Decimal("0"):
            return amount / rate.rate

        logger.warning("No FX rate for %s/%s", from_ccy, to_ccy)
        return None

    async def update_rate(self, base: str, quote: str, rate: Decimal, **kwargs: Any) -> None:
        """Update an FX conversion rate."""
        pair = f"{base}{quote}"
        self._fx_rates[pair] = FxRate(
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            timestamp_ns=int(datetime.now(timezone.utc).timestamp() * 1e9),
            **kwargs,
        )

    async def update_rates_batch(self, rates: list[tuple[str, str, Decimal]]) -> None:
        """Batch-update multiple FX rates."""
        for base, quote, rate in rates:
            await self.update_rate(base, quote, rate)

    @property
    def rate_count(self) -> int:
        return len(self._fx_rates)
