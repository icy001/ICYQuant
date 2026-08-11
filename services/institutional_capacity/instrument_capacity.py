"""
Instrument Capacity — Capacity modeling for specific instrument types.

Adapts capacity estimates for equities, futures, options, FX, etc.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class InstrumentType(str, Enum):
    EQUITY = "equity"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"
    BOND = "bond"
    ETF = "etf"
    CRYPTO = "crypto"


@dataclass
class InstrumentCapacity:
    """Capacity model specialized by instrument type."""

    instrument_id: str = field(default_factory=lambda: f"IC-{uuid.uuid4().hex[:8]}")
    symbol: str = ""
    instrument_type: InstrumentType = InstrumentType.EQUITY

    # Contract/notional scaling
    contract_size: float = 1.0            # shares per contract, lot size
    tick_value: float = 0.01              # dollar per tick

    # Capacity
    max_contracts: float = float("inf")
    max_notional: float = float("inf")
    daily_volume_contracts: float = 0.0

    # Margin/leverage
    margin_rate: float = 0.0              # e.g. 0.10 for futures
    leverage: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "type": self.instrument_type.value,
            "max_notional": self.max_notional,
            "max_contracts": self.max_contracts,
            "leverage": self.leverage,
        }

    def notional_to_contracts(self, notional: float) -> float:
        return notional / max(self.contract_size, 1e-9)

    def contracts_to_notional(self, contracts: float) -> float:
        return contracts * self.contract_size

    def capacity_check(self, requested_notional: float) -> bool:
        if self.max_notional < float("inf") and requested_notional > self.max_notional:
            return False
        contracts = self.notional_to_contracts(requested_notional)
        if self.max_contracts < float("inf") and contracts > self.max_contracts:
            return False
        return True
