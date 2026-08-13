"""Runbook step (Commit 27 Part 1.5, spec sections 5-6).

    CHECK      -> 确认系统状态
    ACTION     -> 执行操作
    APPROVAL   -> 等待授权
    WAIT       -> 等待系统稳定
    VALIDATION -> 验证结果

例如一个标准流程:

    1 CHECK
    2 CHECK
    3 ACTION
    4 APPROVAL
    5 ACTION
    6 WAIT
    7 VALIDATION
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StepType(str, Enum):

    CHECK = "CHECK"

    ACTION = "ACTION"

    APPROVAL = "APPROVAL"

    WAIT = "WAIT"

    VALIDATION = "VALIDATION"


@dataclass(frozen=True)
class RunbookStep:

    step_id: str

    order: int

    name: str

    step_type: StepType

    description: str

    required: bool = True

    timeout_seconds: int = 60
