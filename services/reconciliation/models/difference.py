from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class DifferenceType(str, Enum):
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    AVERAGE_PRICE_MISMATCH = "AVERAGE_PRICE_MISMATCH"
    REALIZED_PNL_MISMATCH = "REALIZED_PNL_MISMATCH"
    MULTIPLE_MISMATCH = "MULTIPLE_MISMATCH"
    UNKNOWN_MISMATCH = "UNKNOWN_MISMATCH"


@dataclass(frozen=True)
class Difference:
    type: DifferenceType
    expected: Decimal
    actual: Decimal
    delta: Decimal
