from datetime import datetime

from services.portfolio import (
    PortfolioSnapshot,
    RecoveryRepository,
    RecoveryValidator,
    RecoveryExecutor,
    PortfolioRecoveryEngine,
)


def test_recovery():
    repository = RecoveryRepository()

    engine = PortfolioRecoveryEngine(
        RecoveryValidator(),
        RecoveryExecutor(),
        repository,
    )

    snapshot = PortfolioSnapshot(
        snapshot_id="SNAP-001",
        portfolio_id="PORT-001",
        created_at=datetime.utcnow(),
        data={"cash": 1000},
    )

    result = engine.recover(
        "RECOVERY-001",
        snapshot,
    )

    assert result.status == "SUCCESS"