"""Control command model and command fingerprint (Commit 29 Part 1.1 §4, §12, §29-30).

A ``ControlCommand`` describes a single control intent, e.g.::

    command_id:    CMD-001
    command_type:  TRADING
    resource:      trading
    action:        pause
    requested_by:  ops-001
    target:        ControlTarget(service="oms", instance="oms-primary", environment="production")

``command_id`` belongs to the Control Plane; ``request_id`` (on the request)
belongs to Governance; the two are never merged (§7).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any

from .state import ControlState
from .target import ControlTarget


@dataclass(frozen=True)
class ControlCommand:
    command_id: str = ""
    command_type: str | None = None
    resource: str = ""
    action: str = ""
    requested_by: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    target: ControlTarget | None = None
    created_at: datetime | None = None
    correlation_id: str = ""
    state: ControlState = ControlState.RECEIVED

    def with_state(self, state: ControlState) -> "ControlCommand":
        """Return a copy of the command carrying a new lifecycle state (§14)."""
        return replace(self, state=state)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def command_fingerprint(command: ControlCommand) -> str:
    """Canonical SHA-256 fingerprint of a control command (§30).

    Covers ``resource``, ``action``, ``target``, ``parameters`` and
    ``requested_by`` so a resubmitted idempotency key carrying a *different*
    command is detected as a conflict instead of returning a stale result (§29).
    """
    payload = {
        "resource": command.resource,
        "action": command.action,
        "target": asdict(command.target) if command.target is not None else None,
        "parameters": command.parameters,
        "requested_by": command.requested_by,
    }
    encoded = _canonical_json(payload).encode()
    return hashlib.sha256(encoded).hexdigest()
