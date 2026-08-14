"""Control request model and validation (Commit 29 Part 1.1 §6-7, §32).

Command and Request are kept separate::

    ControlRequest  (request_id      -> Governance)
    ControlCommand  (command_id      -> Control Plane)

A request enters the Control Plane only after validation — a request missing
any critical field (``request_id``, ``command_id``, ``idempotency_key``,
``resource``, ``action``, ``target``, ``requested_by``) is rejected and never
reaches the dispatcher (§32).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .command import ControlCommand
from .errors import InvalidControlRequest

_COMMAND_REQUIRED_FIELDS = (
    "command_id",
    "resource",
    "action",
    "requested_by",
    "target",
)


@dataclass(frozen=True)
class ControlRequest:
    request_id: str = ""
    command: ControlCommand | None = None
    submitted_at: datetime | None = None
    idempotency_key: str = ""
    source: str = ""


def _missing(value) -> bool:
    return value is None or value == ""


def validate_request(request: ControlRequest) -> None:
    """Validate a control request before it enters the dispatcher (§32).

    Missing critical fields cause an explicit ``InvalidControlRequest``
    (fail closed); such a request never reaches the dispatcher.
    """
    missing: list[str] = []
    if _missing(request.request_id):
        missing.append("request_id")
    if _missing(request.idempotency_key):
        missing.append("idempotency_key")
    if _missing(request.source):
        missing.append("source")
    if request.submitted_at is None:
        missing.append("submitted_at")
    if request.command is None:
        missing.append("command")
    else:
        for field_name in _COMMAND_REQUIRED_FIELDS:
            if _missing(getattr(request.command, field_name)):
                missing.append(f"command.{field_name}")
    if missing:
        raise InvalidControlRequest(
            "control request missing required fields: " + ", ".join(missing)
        )
