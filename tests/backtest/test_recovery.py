from datetime import datetime

from services.backtest import (
    BacktestSnapshot,
    CheckpointManager,
    StatePersistence,
    RecoveryContext,
    RecoveryEngine,
)


def test_recovery():

    manager = CheckpointManager()

    snapshot = BacktestSnapshot(
        "SNAP-001",
        "WF-001",
        datetime.utcnow(),
        {
            "step": 10,
        },
    )

    manager.save(
        snapshot
    )

    engine = RecoveryEngine(
        StatePersistence(),
        manager,
    )

    state = engine.recover(
        RecoveryContext(
            "WF-001",
            "SNAP-001",
        )
    )

    assert state["step"] == 10