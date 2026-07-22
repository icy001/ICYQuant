from services.data import (
    DependencyContainer,
)


def test_container():

    container = DependencyContainer()

    container.register(
        "test",
        object(),
    )

    assert container.resolve(
        "test",
    ) is not None