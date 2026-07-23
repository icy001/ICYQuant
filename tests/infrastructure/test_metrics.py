from infrastructure.metrics import Counter


def test_counter():

    counter = Counter()

    counter.increment()

    assert counter.get() == 1