from services.distributed_lock import *


def test_distributed_lock():
    service = DistributedLockService(
        LockCoordinator(
            LockManager(
                LockRepository()
            )
        )
    )

    result = service.execute(
        LockRequest(
            "NVDA_POSITION",
            "POSITION_SERVICE"
        ),
        lambda: "UPDATED"
    )

    assert result == "UPDATED"
