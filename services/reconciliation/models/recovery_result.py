from __future__ import annotations

from dataclasses import dataclass

from .status import ReconciliationLifecycle


@dataclass(frozen=True)
class RecoveryResult:
    reconciliation_id: str
    lifecycle: ReconciliationLifecycle
    repaired: bool
    verified: bool
    repair_id: str | None
    reason: str
