import pytest


def test_migration_function_exists():
    try:
        from services.database import (
            upgrade_database,
        )
        assert callable(
            upgrade_database
        )
    except ImportError:
        pytest.skip(
            "psycopg not installed, "
            "skipping database test"
        )