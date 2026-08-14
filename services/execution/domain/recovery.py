from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryStatus(str, Enum):
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RecoveryResult:

    status: RecoveryStatus

    consumer_id: str

    stream_id: str

    sequence: int

    error: str | None = None
