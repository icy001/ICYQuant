"""Approval — governance approval model (Commit 28 Part 1.1).

与 Commit 27 的 Runbook Approval 区分：
    Runbook Approval  解决"事故处理流程中的某一步需要批准"。
    Governance Approval 解决"组织层面的权限和政策是否允许这次批准"。

正式形成上下层关系：
    Runbook -> Approval Request -> Governance -> Policy Evaluation
    -> Approval -> Control Plane
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ApprovalState(str, Enum):
    """Lifecycle states of a governance approval."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Approval:
    """A governance approval for a resource+action request."""

    approval_id: str
    resource: str
    action: str
    requested_by: str
    state: ApprovalState = ApprovalState.PENDING
