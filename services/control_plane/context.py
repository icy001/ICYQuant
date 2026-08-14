"""Control authorization context (Commit 29 Part 1.2 §2).

The Control Plane passes a full, self-contained authorization context to
Governance so that the governance layer never needs to reach into the
internal representation of a ``ControlCommand``. Governance answers
ALLOW / DENY / REQUIRE_APPROVAL purely from this context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .request import ControlRequest


@dataclass(frozen=True)
class ControlAuthorizationContext:
    """Immutable authorization context handed to the ``ControlAuthorizer`` (§2).

    Fields mirror the three-layer ID model: ``request_id`` identifies the
    governance-visible request while ``command_id`` identifies the control
    plane command. ``correlation_id`` threads through Request -> Decision
    -> Approval -> Grant -> Command -> Execution -> Audit (§26).
    """

    request_id: str
    command_id: str
    principal_id: str
    resource: str
    action: str
    target: Any
    parameters: dict[str, Any]
    submitted_at: datetime
    correlation_id: str

    @classmethod
    def from_request(cls, request: ControlRequest) -> "ControlAuthorizationContext":
        """Build the context from a validated control request.

        The mapping is deliberately flat: governance consumes
        ``principal_id`` / ``resource`` / ``action`` / ``target`` /
        ``parameters`` without depending on command internals.
        """
        command = request.command
        return cls(
            request_id=request.request_id,
            command_id=command.command_id,
            principal_id=command.requested_by,
            resource=command.resource,
            action=command.action,
            target=command.target,
            parameters=command.parameters,
            submitted_at=request.submitted_at,
            correlation_id=command.correlation_id,
        )
