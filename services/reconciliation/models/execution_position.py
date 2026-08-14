from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ExecutionPosition:
    symbol: str
    quantity: Decimal
    average_price: Decimal
    realized_pnl: Decimal
