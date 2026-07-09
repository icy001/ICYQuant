from services.reconciliation.snapshot_engine import PositionSnapshot, SnapshotEngine


def test_position_snapshot_creation():
    snapshot = PositionSnapshot(symbol="NVDA", quantity=100)
    assert snapshot.symbol == "NVDA"
    assert snapshot.quantity == 100


def test_snapshot_engine_create():
    engine = SnapshotEngine()
    snapshot = engine.create("AAPL", 50)
    assert snapshot.symbol == "AAPL"
    assert snapshot.quantity == 50
