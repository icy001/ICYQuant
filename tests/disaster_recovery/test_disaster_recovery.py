from services.disaster_recovery import *


def test_disaster_recovery():
    service = DisasterRecoveryService(
        BackupManager(
            BackupRepository()
        ),
        RestoreEngine(),
        FailoverController()
    )

    snapshot = BackupSnapshot(
        "B001",
        "TRADING_DB",
        1000,
        "CREATED"
    )

    result = service.backup(
        snapshot
    )

    assert result.snapshot_id == "B001"

    restored = service.restore(
        snapshot
    )

    assert restored.status == "RESTORED"

    failover = Failover(
        "REGION_A",
        "REGION_B",
        "PENDING"
    )

    failed_over = service.failover(
        failover
    )

    assert failed_over.status == "COMPLETED"
