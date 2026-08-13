"""Runbook action (Commit 27 Part 1.5, spec sections 9-10, 29).

Runbook 不直接执行 Control：

    Runbook
        ↓
    Control Request
        ↓
    Authorization
        ↓
    Control Plane
        ↓
    Execution

Operations 永远没有绕过 Control Plane 的权限。

每个 Action 定义:

    control_action  -> 请求 Control Plane 的动作（PAUSE_TRADING / KILL_TRADING ...）
    requires_approval -> 是否需要显式授权
    reason_required   -> 是否必须提供原因
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunbookAction:

    action_id: str

    name: str

    control_action: str

    requires_approval: bool = True

    reason_required: bool = True
