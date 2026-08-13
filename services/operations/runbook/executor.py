"""Runbook executor (Commit 27 Part 1.5, spec sections 28, 31-32).

第一版执行器只负责 Step State：

    Runbook
        ↓
    Action
        ↓
    Control Request
        ↓
    Authorization
        ↓
    Control Plane

它不直接执行任何危险操作。

不允许"跳步骤后无记录"（spec section 32）：

    SKIPPED
        ↓
    reason
    actor
    timestamp

否则事故复盘无法判断：是系统没执行，还是人主动跳过了？
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from .runbook import RunbookDefinition
from .step import RunbookStep


class StepStatus(str, Enum):

    PENDING = "PENDING"

    PASSED = "PASSED"

    FAILED = "FAILED"

    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class StepExecutionRecord:

    step_id: str

    status: StepStatus

    operator: str

    timestamp: datetime

    reason: str = ""

    result: str | None = None


@dataclass
class RunbookExecution:

    incident_id: str

    runbook_id: str

    runbook_version: str

    records: dict[str, StepExecutionRecord] = field(
        default_factory=dict
    )

    started_at: datetime | None = None

    completed_at: datetime | None = None

    def status(self, step_id: str) -> StepStatus:

        record = self.records.get(step_id)

        return record.status if record else StepStatus.PENDING

    def completed(self, step_id: str) -> bool:

        record = self.records.get(step_id)

        if record is None:
            return False

        return record.status in (
            StepStatus.PASSED,
            StepStatus.SKIPPED,
        )

    @property
    def passed_steps(self) -> tuple[StepExecutionRecord, ...]:

        return tuple(
            record
            for record in self.records.values()
            if record.status is StepStatus.PASSED
        )

    @property
    def skipped_steps(self) -> tuple[StepExecutionRecord, ...]:

        return tuple(
            record
            for record in self.records.values()
            if record.status is StepStatus.SKIPPED
        )

    @property
    def failed_steps(self) -> tuple[StepExecutionRecord, ...]:

        return tuple(
            record
            for record in self.records.values()
            if record.status is StepStatus.FAILED
        )

    def events(self) -> tuple[StepExecutionRecord, ...]:

        return tuple(
            sorted(
                self.records.values(),
                key=lambda r: r.timestamp,
            )
        )


class RunbookExecutor:

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
    ):

        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

    def begin(
        self,
        incident_id: str,
        runbook: RunbookDefinition,
    ) -> RunbookExecution:

        return RunbookExecution(
            incident_id=incident_id,
            runbook_id=runbook.runbook_id,
            runbook_version=runbook.version,
            started_at=self._clock(),
        )

    def execute_step(
        self,
        execution: RunbookExecution,
        step: RunbookStep,
        operator: str = "operator",
        result: str = "PASSED",
        reason: str = "",
    ) -> bool:
        """记录一个 Step 的完成状态（spec section 28）。

        required=False 的可选步骤不参与门槛，记录为 SKIPPED。
        返回 True 表示步骤已记录。
        """

        if not step.required:
            return self.skip_step(
                execution,
                step,
                operator=operator,
                reason=reason or "optional step not executed",
            )

        if step.step_id in execution.records:
            return False

        execution.records[step.step_id] = StepExecutionRecord(
            step_id=step.step_id,
            status=StepStatus.PASSED,
            operator=operator,
            timestamp=self._clock(),
            reason=reason,
            result=result,
        )

        return True

    def skip_step(
        self,
        execution: RunbookExecution,
        step: RunbookStep,
        operator: str,
        reason: str,
    ) -> bool:
        """跳步必须留下审计记录（spec section 32）。

        reason / actor / timestamp 三者缺一不可。
        """

        if not reason.strip():
            raise ValueError(
                f"skipping step {step.step_id} requires a reason"
            )

        if step.step_id in execution.records:
            return False

        execution.records[step.step_id] = StepExecutionRecord(
            step_id=step.step_id,
            status=StepStatus.SKIPPED,
            operator=operator,
            timestamp=self._clock(),
            reason=reason,
        )

        return True

    def fail_step(
        self,
        execution: RunbookExecution,
        step: RunbookStep,
        operator: str,
        reason: str,
        result: str = "FAILED",
    ) -> bool:

        if step.step_id in execution.records:
            return False

        execution.records[step.step_id] = StepExecutionRecord(
            step_id=step.step_id,
            status=StepStatus.FAILED,
            operator=operator,
            timestamp=self._clock(),
            reason=reason,
            result=result,
        )

        return True

    def complete(
        self,
        execution: RunbookExecution,
    ) -> RunbookExecution:

        execution.completed_at = self._clock()

        return execution

    def completed(
        self,
        execution: RunbookExecution,
        step_id: str,
    ) -> bool:

        return execution.completed(step_id)

    def required_steps_passed(
        self,
        execution: RunbookExecution,
        runbook: RunbookDefinition,
    ) -> bool:
        """所有 required Step 都已 PASSED（SKIPPED 不计入门槛）。"""

        for step in runbook.steps:
            if not step.required:
                continue

            record = execution.records.get(step.step_id)

            if record is None or record.status is not StepStatus.PASSED:
                return False

        return True
