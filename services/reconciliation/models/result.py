from __future__ import annotations

from dataclasses import dataclass

from ..repair_executor import RepairResult
from .difference import Difference
from .repair import (
    RepairPlan,
    RepairStatus,
)
from .repair_verification import RepairVerification
from .status import ReconciliationStatus


@dataclass(frozen=True)
class ReconciliationResult:
    symbol: str
    status: ReconciliationStatus
    id: str = ""
    differences: tuple[Difference, ...] = ()
    repair_plan: RepairPlan | None = None
    repair_result: RepairResult | None = None
    repair_status: RepairStatus | None = None
    repair_verification: RepairVerification | None = None
