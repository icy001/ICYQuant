from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionVenueType(str, Enum):
    BROKER = "BROKER"
    EXCHANGE = "EXCHANGE"
    SIMULATOR = "SIMULATOR"


@dataclass(frozen=True)
class ExecutionVenue:
    venue_id: str
    name: str
    venue_type: ExecutionVenueType
    enabled: bool = True

    def validate(self) -> None:
        if not self.venue_id:
            raise ValueError("venue_id is required")

        if not self.name:
            raise ValueError("venue name is required")
