"""
Market data validator.
"""

from __future__ import annotations

from .quote import Quote


class MarketDataValidator:
    def validate(
        self,
        quote: Quote,
    ) -> bool:
        return (
            quote.bid > 0
            and quote.ask > 0
            and quote.last > 0
            and quote.bid <= quote.ask
        )