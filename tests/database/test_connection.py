import pytest


def test_database_engine():
    try:
        from services.database import (
            engine,
        )
        assert engine is not None
    except ImportError:
        pytest.skip(
            "psycopg not installed, "
            "skipping PostgreSQL test"
        )