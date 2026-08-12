"""
MitigationPlan — an ordered set of control actions for one incident.

A plan may run its actions sequentially or in best-effort/parallel fashion.
With ``fail_fast`` (default) a failed action stops the plan (spec section 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .action import MitigationAction


@dataclass
class MitigationPlan:

    incident_id: str

    actions: list[MitigationAction] = field(default_factory=list)

    parallel: bool = False

    fail_fast: bool = True

    def add(self, action: MitigationAction) -> None:
        self.actions.append(action)
