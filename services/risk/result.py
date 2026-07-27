from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from research.execution.order import Order


class RiskDecision(Enum):
    PASS = "PASS"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


@dataclass
class RiskResult:
    decision: RiskDecision
    message: Optional[str] = None
    modified_order: Optional[Order] = None


@dataclass
class SimpleRiskResult:
    passed: bool
    reason: str = ""