"""
OrderAdmissionRequest — the first formal step that brings a trading order
into the Control Plane (spec section 3).

An order can no longer reach the OMS just by passing the Risk Engine: it must
pass through Order Admission, which chains Risk → Control Gateway →
Position Effect → Final Admission Decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from services.control_plane.gateway.context import (
    ControlContext,
)


@dataclass(frozen=True)
class OrderAdmissionRequest:

    context: ControlContext

    symbol: str

    side: str

    quantity: float

    order_type: str

    is_reduce_only: bool = False

    request_id: UUID = field(
        default_factory=uuid4
    )

    created_at: datetime = field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )

    metadata: dict = field(
        default_factory=dict
    )
