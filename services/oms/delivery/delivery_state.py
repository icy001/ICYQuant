"""DeliveryState enum."""
from __future__ import annotations

from enum import Enum, auto


class DeliveryState(Enum):
    """State of a delivery attempt."""

    PENDING = auto()
    SENT = auto()
    ACKNOWLEDGED = auto()
    RETRYING = auto()
    UNKNOWN = auto()
    FAILED = auto()

    @property
    def label(self) -> str:
        return self.name.title()

    @property
    def is_terminal(self) -> bool:
        return self in (DeliveryState.ACKNOWLEDGED, DeliveryState.FAILED)

    @property
    def is_unknown(self) -> bool:
        return self == DeliveryState.UNKNOWN
