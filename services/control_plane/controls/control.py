"""
ControlAction — one registered control and its lifecycle metadata.

A ControlAction is *not* the execution of a control (that is performed by the
Control Plane through the Execution Adapter); it is the declarative gate that
the Institutional Control Gateway evaluates against every trading request.

Expiration (spec section 16):

    Temporary controls (e.g. REDUCE_ONLY for 30 minutes) carry an
    ``expires_at``.  The gateway automatically ignores an expired temporary
    control.  KILL_SWITCH is the explicit exception: it must never auto-recover
    through a plain TTL — it requires an explicit, authorized clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .control_type import ControlType
from .scope import ControlScope


@dataclass(frozen=True)
class ControlAction:
    control_type: ControlType

    scope: ControlScope

    target: str

    reason: str

    control_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    expires_at: datetime | None = None

    metadata: dict = field(default_factory=dict)


def is_expired(control: ControlAction) -> bool:
    """Is this control past its ``expires_at`` window?

    A control without ``expires_at`` never expires.  Note that KILL_SWITCH is
    intentionally *not* exempted here — the gateway keeps the exemption at the
    evaluation layer so that ``is_expired`` stays a pure, reusable predicate.
    """
    if control.expires_at is None:
        return False

    return datetime.now(timezone.utc) >= control.expires_at
