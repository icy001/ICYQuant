from datetime import datetime, timezone

from services.replay import (
    ReplayCheckpoint,
)


def test_checkpoint():
    checkpoint = ReplayCheckpoint(
        event_count=1000,
        created_at=datetime.now(
            timezone.utc
        )
    )

    assert checkpoint.event_count == 1000