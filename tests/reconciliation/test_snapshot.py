import pytest

from services.contracts.dto import PositionDTO
from services.reconciliation.snapshot.snapshot_service import SnapshotService


class TestSnapshotService:
    def test_create_snapshot(self):
        service = SnapshotService()
        positions = [PositionDTO(user_id="u1", symbol="AAPL", quantity=100.0)]
        snapshot = service.create_snapshot(positions, [], [], [])
        assert snapshot.snapshot_id is not None
        assert len(snapshot.positions) == 1

    def test_get_recent_snapshots(self):
        service = SnapshotService()
        for i in range(15):
            service.create_snapshot([PositionDTO(user_id="u1", symbol=f"SYMBOL{i}", quantity=100.0)], [], [], [])
        recent = service.get_recent_snapshots(limit=10)
        assert len(recent) == 10
