from services.order.version import Version


def test_next_version():
    version = Version()
    assert version.value == 1
    assert version.next().value == 2


def test_version_equality():
    v1 = Version(1)
    v2 = Version(1)
    v3 = Version(2)
    assert v1 == v2
    assert v1 != v3


def test_version_chaining():
    version = Version()
    assert version.next().next().value == 3