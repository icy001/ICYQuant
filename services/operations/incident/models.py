"""Incident auxiliary models (Commit 27 Part 1.4, spec sections 23-25, 30-31).

Incident -> Control Request，而不是 Incident -> 直接执行 Kill。

对于 GLOBAL_KILL 属于极高风险操作，第一版默认:

    CATASTROPHIC
        ↓
    Control Request
        ↓
    Explicit Authorization
        ↓
    Kill

避免 Incident Engine 自己拥有全局交易终止权限。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncidentControlRequest:

    incident_id: str

    action: str

    reason: str

    requested_by: str

    requires_confirmation: bool = True


#: Incident Recovery Gate 至少检查的项目 (spec section 31)。
RECOVERY_GATE_CHECKS = (
    "service_health",
    "risk_state",
    "position_state",
    "ledger_state",
    "reconciliation",
    "execution",
    "venue",
)


@dataclass(frozen=True)
class RecoveryCheck:

    name: str

    passed: bool


class RecoveryGate:
    """恢复交易之前的确定性闸门。

    任何一项检查 FAIL（或缺失）都意味着:

        Incident != RESOLVED
    """

    def evaluate(
        self,
        results: dict[str, bool],
    ) -> bool:

        for name in RECOVERY_GATE_CHECKS:
            if not results.get(name, False):
                return False

        return True

    def checks(
        self,
        results: dict[str, bool],
    ) -> tuple[RecoveryCheck, ...]:

        return tuple(
            RecoveryCheck(
                name=name,
                passed=results.get(name, False),
            )
            for name in RECOVERY_GATE_CHECKS
        )
