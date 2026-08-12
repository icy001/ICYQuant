"""
ExecutionControlDecision — the granular outcome of Execution Control
(Commit 26 Part 1.4, spec section 4).

New / Cancel / Reduce / Emergency Flatten are deliberately separated,
because "no trading" must never mean "no risk control".
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import ExecutionState


@dataclass(frozen=True)
class ExecutionControlDecision:

    execution_id: str

    state: ExecutionState

    allow_new_orders: bool

    allow_cancel_orders: bool

    allow_reduce_orders: bool

    allow_emergency_flatten: bool

    reason: str

    @property
    def allow_any_orders(self) -> bool:
        return (
            self.allow_new_orders
            or self.allow_cancel_orders
            or self.allow_reduce_orders
            or self.allow_emergency_flatten
        )
