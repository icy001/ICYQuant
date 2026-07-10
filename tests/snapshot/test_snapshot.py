from uuid import uuid4

from services.snapshot import (
    PortfolioSnapshot,
)


def test_snapshot_creation():
    snapshot = PortfolioSnapshot(
        snapshot_id=uuid4(),
        event_id=uuid4(),
        created_at=None,
        state={
            "cash": 1000
        }
    )

    assert snapshot.state["cash"] == 1000