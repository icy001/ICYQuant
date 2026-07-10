from services.metrics import (
    Counter,
)


def test_counter():
    counter = Counter(
        "test"
    )

    counter.inc()

    counter.inc(
        2
    )

    assert (
        counter.get()
        ==
        3
    )