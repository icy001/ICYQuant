"""Approval workflow (Commit 27 Part 1.5, spec sections 11-13, 29-30).

普通:

    WARNING -> Operator -> Runbook -> Action

重大:

    CRITICAL -> Runbook -> Approval -> Control Plane

紧急:

    EMERGENCY -> Emergency Control -> Immediate Safety Action -> Audit

是否允许自动执行由 Control Plane 的策略决定，而不是 Runbook 自己决定。

角色分离（spec section 30）:

    Observer            -> 查看 Incident
    Operator            -> 执行标准 Runbook
    Incident Commander  -> 批准重大操作
    Control Operator    -> 执行 Kill / Pause / Failover
    Administrator       -> 修改 Runbook / Policy
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from ..incident import IncidentSeverity


def _severity_value(severity) -> int:
    """把 int / IncidentSeverity 统一转换为整数值。"""

    if isinstance(severity, IncidentSeverity):
        return int(severity)

    return int(severity)


def requires_approval(
    severity,
    action: str,
) -> bool:
    """Approval rule（spec section 13）。

        KILL_TRADING    -> 总是需要授权
        FAILOVER_VENUE  -> 总是需要授权
        PAUSE_TRADING   -> CRITICAL 及以上（>= 3）需要授权
        其他            -> 不需要授权
    """

    if action == "KILL_TRADING":
        return True

    if action == "FAILOVER_VENUE":
        return True

    if action == "PAUSE_TRADING":
        return _severity_value(severity) >= 3

    return False


@dataclass(frozen=True)
class ApprovalRequest:

    approval_id: str

    incident_id: str

    action: str

    requested_by: str

    requested_at: datetime

    reason: str

    approved_by: str | None = None

    approved_at: datetime | None = None

    approved: bool = False


class ApprovalWorkflow:

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
    ):

        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self._requests = {}

    def request(
        self,
        incident_id: str,
        action: str,
        requested_by: str,
        reason: str,
        approval_id: str | None = None,
    ) -> ApprovalRequest:

        approval = ApprovalRequest(
            approval_id=approval_id or (
                f"APR-{uuid4().hex[:12]}"
            ),
            incident_id=incident_id,
            action=action,
            requested_by=requested_by,
            requested_at=self._clock(),
            reason=reason,
        )

        self._requests[approval.approval_id] = approval

        return approval

    def get(
        self,
        approval_id: str,
    ) -> ApprovalRequest | None:

        return self._requests.get(approval_id)

    def approve(
        self,
        approval_id: str,
        approved_by: str,
        reason: str = "approved",
    ) -> ApprovalRequest:
        """显式授权（spec section 29）：必须提供批准人。"""

        if not approved_by.strip():
            raise ValueError("approval requires approved_by")

        request = self._requests[approval_id]

        if request.approved:
            return request

        updated = replace(
            request,
            approved=True,
            approved_by=approved_by,
            approved_at=self._clock(),
            reason=request.reason,
        )

        self._requests[approval_id] = updated

        return updated

    def reject(
        self,
        approval_id: str,
        rejected_by: str,
        reason: str = "rejected",
    ) -> ApprovalRequest:

        if not rejected_by.strip():
            raise ValueError("rejection requires rejected_by")

        request = self._requests[approval_id]

        if request.approved:
            return request

        updated = replace(
            request,
            approved=False,
            approved_by=rejected_by,
            approved_at=self._clock(),
            reason=f"{request.reason} | {reason}",
        )

        self._requests[approval_id] = updated

        return updated

    def pending(
        self,
        incident_id: str | None = None,
    ) -> tuple[ApprovalRequest, ...]:

        return tuple(
            request
            for request in self._requests.values()
            if not request.approved
            and (
                incident_id is None
                or request.incident_id == incident_id
            )
        )

    def is_approved(
        self,
        approval_id: str,
    ) -> bool:

        request = self._requests.get(approval_id)

        return bool(request and request.approved)
