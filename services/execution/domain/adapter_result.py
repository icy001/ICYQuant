from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AdapterOrderStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AdapterSubmissionResult:
    external_order_id: str

    status: AdapterOrderStatus

    message: str | None = None
