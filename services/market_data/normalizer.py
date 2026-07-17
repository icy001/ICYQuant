"""
Payload normalization helpers.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .quote import Quote


class QuoteNormalizer:
    def from_mapping(
        self,
        payload: dict,
    ) -> Quote:
        return Quote(
            symbol=payload["symbol"],
            bid=Decimal(str(payload["bid"])),
            ask=Decimal(str(payload["ask"])),
            last=Decimal(str(payload["last"])),
            timestamp=payload.get(
                "timestamp",
                datetime.utcnow(),
            ),
        )