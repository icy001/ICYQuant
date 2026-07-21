from services.portfolio import (
    SnapshotRepository,
    PortfolioSnapshotEngine,
)


def test_snapshot_creation():
    repository = SnapshotRepository()

    engine = PortfolioSnapshotEngine(
        repository,
    )

    snapshot = engine.create(
        "SNAP-001",
        "PORT-001",
        {
            "cash": 100000,
        },
    )

    assert repository.load(
        "SNAP-001"
    ) == snapshot