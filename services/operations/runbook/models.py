"""Runbook model (Commit 27 Part 1.5, spec sections 3-4).

Runbook 本质上是:

    Incident
        ↓
    匹配 Runbook
        ↓
    执行标准流程

runbook_id + version 必须成为审计信息:

    RB-RECON-001 / 1.2.0

即使 Runbook 后来更新到 1.3.0，历史事故仍然可以还原当时的操作流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunbookSeverity(str, Enum):

    STANDARD = "STANDARD"

    ELEVATED = "ELEVATED"

    CRITICAL = "CRITICAL"

    EMERGENCY = "EMERGENCY"


@dataclass(frozen=True)
class Runbook:

    runbook_id: str

    name: str

    description: str

    severity: RunbookSeverity

    version: str

    enabled: bool = True
