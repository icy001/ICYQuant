from services.observability import (
    ErrorTracker,
)


def test_error_tracking():
    tracker = ErrorTracker()
    context = tracker.capture(
        ValueError(
            "test"
        )
    )
    assert (
        context.error_id.startswith(
            "err-"
        )
    )
    assert context.timestamp