from services.database import (
    load_database_settings,
)


def test_database_settings():
    settings = load_database_settings()
    assert settings.host
    assert (
        settings.port
        ==
        5432
    )
    assert (
        "postgresql"
        in
        settings.url
    )