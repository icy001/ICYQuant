from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID, uuid4


@dataclass
class Snapshot:
    snapshot_id: UUID = field(default_factory=uuid4)
    ledger_version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    state: Dict = field(default_factory=dict)
    last_event_id: Optional[UUID] = None


class SnapshotManager:
    def __init__(self, snapshot_interval: int = 1000):
        self.snapshot_interval = snapshot_interval
        self.snapshots: Dict[int, Snapshot] = {}
        self._event_count = 0

    def should_snapshot(self) -> bool:
        return self._event_count > 0 and self._event_count % self.snapshot_interval == 0

    def take_snapshot(self, ledger_state: Dict, last_event_id: UUID) -> Snapshot:
        snapshot = Snapshot(
            ledger_version=self._event_count,
            state=ledger_state,
            last_event_id=last_event_id
        )
        self.snapshots[self._event_count] = snapshot
        return snapshot

    def get_latest_snapshot(self) -> Optional[Snapshot]:
        if not self.snapshots:
            return None
        latest_version = max(self.snapshots.keys())
        return self.snapshots[latest_version]

    def record_event(self) -> None:
        self._event_count += 1


@dataclass
class LedgerSnapshot:
    balances: dict[
        str,
        Decimal,
    ] = field(
        default_factory=dict
    )

    def apply(
        self,
        account: str,
        delta: Decimal,
    ) -> None:
        current = self.balances.get(
            account,
            Decimal("0"),
        )

        self.balances[
            account
        ] = current + delta