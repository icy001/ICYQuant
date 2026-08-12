"""
MitigationAction — one atomic control action against the trading stack.

Every action carries an idempotency key ``incident_id:action_type:version`` so
network retries can never duplicate a control action (spec section 15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .action_type import MitigationActionType


def build_idempotency_key(
    incident_id: str,
    action_type: MitigationActionType,
    action_version: str = "v1",
) -> str:
    return f"{incident_id}:{action_type.value}:{action_version}"


@dataclass
class MitigationAction:

    incident_id: str

    action_type: MitigationActionType

    action_id: UUID = field(default_factory=uuid4)

    parameters: dict[str, Any] = field(default_factory=dict)

    requested_by: str = "system"

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            self.idempotency_key = build_idempotency_key(
                self.incident_id,
                self.action_type,
            )
