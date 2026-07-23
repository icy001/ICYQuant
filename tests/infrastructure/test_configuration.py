from infrastructure.config import (
    EnvironmentProfile,
)


def test_environment():

    profile = EnvironmentProfile()

    assert profile.exists(
        "production"
    )