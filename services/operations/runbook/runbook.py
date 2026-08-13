"""Runbook definition and validation (Commit 27 Part 1.5, spec sections 34-35).

Runbook 注册时必须检查:

    runbook_id / name / version / steps 非空
    不能出现两个 Step order = 3
    不能没有任何 VALIDATION
    Emergency Runbook 不能缺少 Approval / Control
"""

from __future__ import annotations

from dataclasses import dataclass

from .action import RunbookAction
from .condition import RunbookCondition
from .models import Runbook, RunbookSeverity
from .step import RunbookStep, StepType


@dataclass(frozen=True)
class RunbookDefinition:

    runbook_id: str

    name: str

    description: str

    severity: RunbookSeverity

    version: str

    steps: tuple[RunbookStep, ...]

    actions: tuple[RunbookAction, ...] = ()

    conditions: tuple[RunbookCondition, ...] = ()

    enabled: bool = True

    def action_for_step(
        self,
        step: RunbookStep,
    ) -> RunbookAction | None:
        """把 ACTION Step 关联到 RunbookAction（默认 step_id 相同）。"""

        for action in self.actions:
            if action.action_id == step.step_id:
                return action

        return None

    def step(
        self,
        step_id: str,
    ) -> RunbookStep | None:

        for step in self.steps:
            if step.step_id == step_id:
                return step

        return None

    def by_order(self) -> tuple[RunbookStep, ...]:

        return tuple(
            sorted(
                self.steps,
                key=lambda s: s.order,
            )
        )


class RunbookValidator:

    def validate(
        self,
        runbook: Runbook | RunbookDefinition,
        steps: tuple[RunbookStep, ...] | list[RunbookStep] | None = None,
    ) -> bool:
        """校验 Runbook（spec sections 34-35）。

        失败抛 ValueError；通过返回 True。
        """

        if not runbook.runbook_id:
            raise ValueError("runbook_id required")

        if not runbook.name:
            raise ValueError("name required")

        if not runbook.version:
            raise ValueError("version required")

        if steps is None:
            if isinstance(runbook, RunbookDefinition):
                steps = runbook.steps
            else:
                raise ValueError("runbook must contain steps")

        steps = tuple(steps)

        if not steps:
            raise ValueError("runbook must contain steps")

        orders = [step.order for step in steps]

        if len(orders) != len(set(orders)):
            raise ValueError("duplicate step order")

        if min(orders) != 1 or max(orders) != len(orders):
            raise ValueError("step order must be contiguous from 1")

        step_ids = [step.step_id for step in steps]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError("duplicate step_id")

        types = {step.step_type for step in steps}

        if StepType.VALIDATION not in types:
            raise ValueError(
                "runbook must contain at least one VALIDATION step"
            )

        if runbook.severity is RunbookSeverity.EMERGENCY:
            if StepType.APPROVAL not in types:
                raise ValueError(
                    "emergency runbook must contain APPROVAL step"
                )

            if StepType.ACTION not in types:
                raise ValueError(
                    "emergency runbook must contain ACTION step"
                )

        return True
