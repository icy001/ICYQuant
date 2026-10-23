"""P0-01 Strategy Contract — the ICYQuant → LEAN boundary type.

This is the single most important interface of the LEAN track.  Every
strategy layer (Alpha021, Alpha101, Chan, trend, ML, Strategy
Discovery) speaks *this*, and only this: it produces
:class:`StrategyIntent` objects.  It never produces a broker order.

The split of responsibility is deliberate:

  ICYQuant owns            LEAN owns
  ----------------------   ------------------------------------
  Alpha / Strategy         Security / Market data
  Risk / Sizing            Order / Fill
  StrategyContract         Portfolio / Paper Brokerage

Because the contract is a plain frozen dataclass with a hand-written
``validate()`` (rather than a pydantic model), it stays importable with
zero third-party dependencies — the adapter boundary must never be the
reason an ICYQuant process cannot start.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

#: Bumped only when the payload is no longer backward compatible.
CONTRACT_VERSION = "1.0"

SUPPORTED_MODES = frozenset({"paper", "live"})
SUPPORTED_SIDES = frozenset({"BUY", "SELL"})

__all__ = [
    "CONTRACT_VERSION",
    "SUPPORTED_MODES",
    "SUPPORTED_SIDES",
    "StrategyContract",
    "StrategyIntent",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StrategyIntent:
    """One strategy decision, expressed as an intent — not an order.

    Quantities are whole shares (integers): ICYQuant sizes positions
    *before* the contract, so the adapter never has to round, and a
    fractional lot can never be silently truncated at the broker.
    """

    strategy_id: str
    signal_id: str
    symbol: str
    side: str
    quantity: int
    target_weight: Optional[float] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    timestamp: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Raise ``ValueError`` on the first violated invariant."""
        if not self.strategy_id:
            raise ValueError("strategy_id is required")

        if not self.signal_id:
            raise ValueError("signal_id is required")

        if not self.symbol:
            raise ValueError("symbol is required")

        side = str(self.side).upper()
        if side not in SUPPORTED_SIDES:
            raise ValueError(f"unsupported side: {self.side}")

        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise ValueError("quantity must be an integer number of shares")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

        if self.target_weight is not None and not (
            -1.0 <= self.target_weight <= 1.0
        ):
            raise ValueError("target_weight must be between -1 and 1")

        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError("limit_price must be positive")

        if self.stop_price is not None and self.stop_price <= 0:
            raise ValueError("stop_price must be positive")

    @property
    def signed_quantity(self) -> int:
        """Shares as LEAN expects them: negative for a sell."""
        self.validate()
        return self.quantity if str(self.side).upper() == "BUY" else -self.quantity

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class StrategyContract:
    """A validated batch of intents plus the account context around them."""

    contract_version: str
    strategy_id: str
    mode: str
    initial_cash: float
    symbols: list[str]
    intents: list[StrategyIntent]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"unsupported contract version: {self.contract_version}"
            )

        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"unsupported mode: {self.mode}")

        if not self.strategy_id:
            raise ValueError("strategy_id is required")

        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")

        if not self.symbols:
            raise ValueError("symbols must not be empty")

        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")

        symbol_set = set(self.symbols)

        for intent in self.intents:
            intent.validate()

            if intent.symbol not in symbol_set:
                raise ValueError(
                    f"intent symbol {intent.symbol} not in contract symbols"
                )

            if intent.strategy_id != self.strategy_id:
                raise ValueError(
                    f"intent strategy_id {intent.strategy_id} does not match "
                    f"contract strategy_id {self.strategy_id}"
                )

    def to_dict(self) -> dict[str, Any]:
        self.validate()

        return {
            "contract_version": self.contract_version,
            "strategy_id": self.strategy_id,
            "mode": self.mode,
            "initial_cash": self.initial_cash,
            "symbols": self.symbols,
            "intents": [intent.to_dict() for intent in self.intents],
            "metadata": self.metadata,
        }
