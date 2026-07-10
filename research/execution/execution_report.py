from dataclasses import dataclass, field
from typing import List, Optional

from .order import Order
from .fill import Fill


@dataclass
class ExecutionReport:
    order: Order
    fills: List[Fill] = field(default_factory=list)
    message: Optional[str] = None