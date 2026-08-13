"""Permission — resource + action permission model (Commit 28 Part 1.1).

权限回答"可以做什么？"。采用 resource + action 模型，
例如 incident:read、trading:pause、trading:kill。

Permission 只回答"你有没有资格申请"，不直接决定 Allow；
最终是否允许由 Policy + Context 决定。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    """A permission binding a resource and an action."""

    permission_id: str
    resource: str
    action: str


# Standard permissions (Commit 28 Part 1.1, section 20).
STANDARD_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("incident:read", "incident", "read"),
    ("incident:update", "incident", "update"),
    ("incident:escalate", "incident", "escalate"),
    ("runbook:read", "runbook", "read"),
    ("runbook:execute", "runbook", "execute"),
    ("runbook:approve", "runbook", "approve"),
    ("trading:read", "trading", "read"),
    ("trading:pause", "trading", "pause"),
    ("trading:resume", "trading", "resume"),
    ("trading:kill", "trading", "kill"),
    ("trading:failover", "trading", "failover"),
    ("recovery:read", "recovery", "read"),
    ("recovery:execute", "recovery", "execute"),
    ("audit:read", "audit", "read"),
    ("policy:read", "policy", "read"),
    ("policy:update", "policy", "update"),
    ("role:read", "role", "read"),
    ("role:update", "role", "update"),
)


def build_standard_permissions() -> tuple[Permission, ...]:
    """Build the first batch of standard production governance permissions."""
    return tuple(
        Permission(permission_id, resource, action)
        for permission_id, resource, action in STANDARD_PERMISSIONS
    )
