"""Audit — immutable governance audit evidence (Commit 28 Part 1.1).

Governance Audit 回答"谁被允许做了什么？为什么允许？依据什么 Policy？
有没有 Approval？"，与 Incident Audit（事故发生了什么）职责不同，
两者最终通过 incident_id 关联。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GovernanceAuditEvent:
    """An immutable record of a governance decision."""

    event_id: str
    timestamp: datetime
    principal_id: str
    resource: str
    action: str
    effect: str
    reason: str
    policy_id: str | None = None
    incident_id: str | None = None
    approval_id: str | None = None
