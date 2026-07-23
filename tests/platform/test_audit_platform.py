from services.platform.audit import (
    DecisionTrace,
)


def test_trace():

    trace = DecisionTrace(
        "CIO",
        "BUY",
        "alpha",
        0.9
    )

    assert trace.agent == "CIO"