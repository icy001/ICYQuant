from dataclasses import dataclass
from enum import Enum


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"


@dataclass
class PositionSnapshot:
    symbol: str
    quantity: float


@dataclass
class LedgerSnapshot:
    symbol: str
    quantity: float


@dataclass
class ReconciliationResult:
    symbol: str
    ledger_quantity: float
    position_quantity: float
    difference: float
    status: ReconciliationStatus
