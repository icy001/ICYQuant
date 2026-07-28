from services.recovery import *


def test_event_recovery():
    repository = EventRepository()

    repository.append(
        EventRecord(
            "EV001",
            "POSITION_UPDATE",
            {
                "NVDA": 100
            },
            100
        )
    )

    service = RecoveryService(
        RecoveryManager(
            EventReader(repository),
            ReplayEngine()
        )
    )

    result = service.recover(
        ReplayRequest(
            "PORT001",
            0,
            200
        )
    )

    assert result.success is True

    assert result.replayed_events == 1