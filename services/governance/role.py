"""Role — governance role definition and standard roles (Commit 28 Part 1.1).

角色回答"什么角色？"。标准角色映射遵循 Least Privilege 与
Separation of Duties：Administrator 不自动等于 Control Operator。
"""

from __future__ import annotations

from dataclasses import dataclass

STANDARD_ROLE_IDS: tuple[str, ...] = (
    "OBSERVER",
    "OPERATOR",
    "INCIDENT_COMMANDER",
    "RISK_OPERATOR",
    "CONTROL_OPERATOR",
    "AUDITOR",
    "ADMINISTRATOR",
)


@dataclass(frozen=True)
class Role:
    """A named governance role."""

    role_id: str
    name: str
    description: str


# Standard role -> permission mapping (Commit 28 Part 1.1, section 21).
# trading:kill is NOT granted to the ordinary OPERATOR.
STANDARD_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "OBSERVER": (
        "incident:read",
        "runbook:read",
        "trading:read",
        "recovery:read",
        "audit:read",
    ),
    "OPERATOR": (
        "incident:read",
        "runbook:read",
        "trading:read",
        "recovery:read",
        "audit:read",
        "incident:update",
        "runbook:execute",
        "recovery:execute",
    ),
    "INCIDENT_COMMANDER": (
        "incident:read",
        "runbook:read",
        "trading:read",
        "recovery:read",
        "audit:read",
        "incident:update",
        "runbook:execute",
        "recovery:execute",
        "incident:escalate",
        "runbook:approve",
    ),
    "RISK_OPERATOR": (
        "trading:read",
        "runbook:read",
        "recovery:read",
        "runbook:execute",
        "recovery:execute",
    ),
    "CONTROL_OPERATOR": (
        "trading:pause",
        "trading:resume",
        "trading:failover",
        "trading:kill",
    ),
    "AUDITOR": (
        "audit:read",
        "incident:read",
    ),
    "ADMINISTRATOR": (
        "policy:read",
        "policy:update",
        "role:read",
        "role:update",
    ),
}


def build_standard_roles() -> tuple[Role, ...]:
    """Build the first batch of standard production governance roles."""
    return (
        Role(
            "OBSERVER",
            "Observer",
            "Read-only observation of incidents, runbooks, trading and recovery.",
        ),
        Role(
            "OPERATOR",
            "Operator",
            "Handles incidents and executes runbook steps.",
        ),
        Role(
            "INCIDENT_COMMANDER",
            "Incident Commander",
            "Owns incident escalation and runbook approvals.",
        ),
        Role(
            "RISK_OPERATOR",
            "Risk Operator",
            "Executes risk-related recovery actions.",
        ),
        Role(
            "CONTROL_OPERATOR",
            "Control Operator",
            "Executes trading controls: pause, resume, failover, kill.",
        ),
        Role(
            "AUDITOR",
            "Auditor",
            "Read-only access to audit evidence.",
        ),
        Role(
            "ADMINISTRATOR",
            "Administrator",
            "Manages governance policy and roles.",
        ),
    )
