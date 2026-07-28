from dataclasses import dataclass


@dataclass
class RecoveryResult:
    aggregate_id: str
    replayed_events: int
    success: bool